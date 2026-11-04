"""Temporal, development-only historical venue retrieval baselines and local CLI."""

from __future__ import annotations

import argparse
import json
import re
import time
from collections import Counter, defaultdict
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import normalize

from ai_research_trends.experiments.venue_inventory import INTEGRATED
from ai_research_trends.ml.final_inference import TopicPlacementService
from ai_research_trends.ml.validate_integrated_data import verify_run
from ai_research_trends.preprocessing.validate_tables import file_sha256


MODEL_DIR = Path("models/finalization_p3/topic_placement_v2")
WEB_DIR = Path("data/analysis/finalization_p2_web_data_20261101_v3")


def query_text(title: str, abstract: str) -> str:
    if not isinstance(title, str) or not title.strip() or not isinstance(abstract, str) or not abstract.strip():
        raise ValueError("Title and abstract are both required")
    return " ".join(title.split()) + "\n" + " ".join(abstract.split())


def prepare_dataset(inventory_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    verify_run(INTEGRATED)
    links = pd.read_parquet(inventory_dir / "paper_venue_links.parquet")
    if links.work_id.duplicated().any():
        raise ValueError("Paper–venue link has duplicate Work IDs")
    train = pd.read_parquet(INTEGRATED / "train.parquet")
    development = pd.read_parquet(INTEGRATED / "validation_2024.parquet")
    validate_temporal_frames(train, development)
    cols = ["work_id", "canonical_venue_id", "venue_type", "display_name", "match_status"]
    train = train.merge(links[cols], on="work_id", how="left", validate="one_to_one")
    development = development.merge(links[cols], on="work_id", how="left", validate="one_to_one")
    return train, development, links


def validate_temporal_frames(train: pd.DataFrame, development: pd.DataFrame) -> None:
    if not set(train.version_group).isdisjoint(development.version_group):
        raise ValueError("Train/development version-group leakage")
    if not train.publication_year.between(2020, 2023).all() or not development.publication_year.eq(2024).all():
        raise ValueError("Temporal protocol violated")
    if set(train.work_id).intersection(development.work_id):
        raise ValueError("Train/development Work-ID leakage")


def build_candidate_pool(train: pd.DataFrame, min_support: int = 2) -> tuple[pd.DataFrame, pd.DataFrame]:
    if min_support < 1:
        raise ValueError("Minimum historical support must be positive")
    usable = train.loc[train.canonical_venue_id.notna() &
                       train.venue_type.isin(["journal", "conference"])].copy()
    support = usable.groupby("canonical_venue_id", sort=True).size().rename("support")
    eligible_ids = support.loc[support.ge(min_support)].index
    pool = usable.loc[usable.canonical_venue_id.isin(eligible_ids)].copy()
    venues = (pool.groupby("canonical_venue_id", sort=True)
              .agg(historical_support=("work_id", "size"),
                   venue_type=("venue_type", "first"),
                   display_name=("display_name", "first"))
              .reset_index())
    if venues.canonical_venue_id.duplicated().any():
        raise ValueError("Duplicate candidate venue")
    return pool, venues


def rank_from_scores(scores: dict[str, float], candidate_ids: set[str], top_k: int = 10) -> list[str]:
    if not candidate_ids or top_k < 1:
        return []
    return sorted(candidate_ids, key=lambda v: (-scores.get(v, 0.0), v))[:top_k]


def metrics_for_predictions(actual: list[str | None], predictions: list[list[str]],
                            candidate_ids: set[str]) -> dict:
    if len(actual) != len(predictions):
        raise ValueError("Prediction and ground-truth lengths differ")
    total = len(actual)
    if not total:
        return {"queries": 0, "candidate_coverage": None, "mrr": None}
    ranks = [p.index(a) + 1 if a in p else None for a, p in zip(actual, predictions)]
    return {"queries": total,
            "known_historical_venue": sum(a is not None for a in actual),
            "candidate_coverage": sum(a in candidate_ids for a in actual) / total,
            "no_candidates": sum(not p for p in predictions) / total,
            **{f"recall_at_{k}": sum(r is not None and r <= k for r in ranks) / total
               for k in (1, 3, 5, 10)},
            "mrr_at_10": sum(1 / r for r in ranks if r is not None) / total,
            "conditional_recall_at_5": (
                sum(r is not None and r <= 5 for r, a in zip(ranks, actual) if a in candidate_ids)
                / sum(a in candidate_ids for a in actual)
                if any(a in candidate_ids for a in actual) else None)}


def frozen_topic_routes(texts: list[str]) -> tuple[list[str | None], dict]:
    """Use only frozen title+abstract model outputs, not true OpenAlex query labels."""
    service = TopicPlacementService(MODEL_DIR, WEB_DIR)
    model = service.model
    if service.config["model_family"] == "linear_svm":
        scores = np.asarray(model.decision_function(texts))
    else:
        scores = np.asarray(model.predict_proba(texts))
    maxima = scores.max(axis=1)
    positions = scores.argmax(axis=1)
    threshold = float(service.config["threshold"])
    classes = service.config["classes"]
    routes = [classes[int(i)] if score >= threshold else None
              for i, score in zip(positions, maxima)]
    return routes, {"model_version": service.config["model_version"],
                    "threshold": threshold, "routed_queries": sum(x is not None for x in routes),
                    "model_manifest_sha256": file_sha256(MODEL_DIR / "manifest.json")}


def fit_index(train: pd.DataFrame, venues: pd.DataFrame) -> dict:
    docs = [query_text(t, a) for t, a in zip(train.title, train.abstract)]
    vectorizer = TfidfVectorizer(stop_words="english", min_df=2,
                                 ngram_range=(1, 2), sublinear_tf=True, max_features=100_000)
    matrix = vectorizer.fit_transform(docs)
    ids = venues.canonical_venue_id.tolist()
    venue_index = {value: index for index, value in enumerate(ids)}
    incidence = sparse.csr_matrix((np.ones(len(train)),
        (np.arange(len(train)), [venue_index[v] for v in train.canonical_venue_id])),
        shape=(len(train), len(ids)))
    profiles = normalize(incidence.T @ matrix, norm="l2")
    topic_counts = Counter(zip(train.primary_topic_id, train.canonical_venue_id))
    return {"vectorizer": vectorizer, "matrix": matrix,
            "profiles": profiles, "doc_venues": train.canonical_venue_id.tolist(),
            "venue_ids": ids, "venues": venues.to_dict("records"),
            "topic_venue_counts": dict(topic_counts)}


def rank_text(index: dict, text: str, *, method: str, top_k: int = 10) -> list[str]:
    query = index["vectorizer"].transform([text])
    if query.nnz == 0:
        return []
    ids = index["venue_ids"]
    if method == "v2_tfidf_papers":
        similarities = (index["matrix"] @ query.T).toarray().ravel()
        selected = np.argsort(-similarities, kind="stable")[:100]
        aggregate: dict[str, float] = defaultdict(float)
        for idx in selected:
            score = float(similarities[idx])
            if score <= 0:
                break
            aggregate[index["doc_venues"][idx]] += score
        return rank_from_scores(aggregate, set(aggregate), top_k)
    if method == "v3_venue_profiles":
        scores = (index["profiles"] @ query.T).toarray().ravel()
        ranked = sorted((pair for pair in enumerate(ids) if scores[pair[0]] > 0),
                        key=lambda pair: (-float(scores[pair[0]]), pair[1]))
        return [vid for _, vid in ranked[:top_k]]
    raise ValueError(f"Unknown text baseline: {method}")


def evaluate(inventory_dir: Path, *, min_support: int = 2) -> dict:
    train, dev, links = prepare_dataset(inventory_dir)
    pool, venues = build_candidate_pool(train, min_support)
    if pool.empty:
        raise ValueError("No historically supported venue candidate pool")
    ids = set(venues.canonical_venue_id)
    texts = [query_text(t, a) for t, a in zip(dev.title, dev.abstract)]
    routes, route_meta = frozen_topic_routes(texts)
    support = dict(zip(venues.canonical_venue_id, venues.historical_support))
    topic_counts = Counter(zip(pool.primary_topic_id, pool.canonical_venue_id))
    index = fit_index(pool, venues)
    index_path = inventory_dir / "venue_retrieval_index.joblib"
    joblib.dump(index, index_path, compress=3)
    actual = [v if isinstance(v, str) else None for v in dev.canonical_venue_id]
    predicted: dict[str, list[list[str]]] = {name: [] for name in (
        "v0_popularity", "v1_frozen_topic_frequency", "v2_tfidf_papers", "v3_venue_profiles")}
    started = time.perf_counter()
    for text, topic in zip(texts, routes):
        predicted["v0_popularity"].append(rank_from_scores(support, ids))
        topic_scores = {v: topic_counts[(topic, v)] for v in ids} if topic else {}
        predicted["v1_frozen_topic_frequency"].append(
            rank_from_scores(topic_scores if any(topic_scores.values()) else support, ids))
        predicted["v2_tfidf_papers"].append(rank_text(index, text, method="v2_tfidf_papers"))
        predicted["v3_venue_profiles"].append(rank_text(index, text, method="v3_venue_profiles"))
    elapsed = time.perf_counter() - started
    results = {name: metrics_for_predictions(actual, rows, ids) for name, rows in predicted.items()}
    result = {"protocol": "2020–2023 index; 2024 development only; 2025 sealed untouched",
              "candidate_min_support": min_support, "training_works": len(train),
              "indexed_works": len(pool), "development_queries": len(dev),
              "candidate_venues": len(ids), "candidate_journals": int(venues.venue_type.eq("journal").sum()),
              "candidate_conferences": int(venues.venue_type.eq("conference").sum()),
              "oracle_candidate_coverage": sum(a in ids for a in actual) / len(actual),
              "route": route_meta, "evaluation_seconds": round(elapsed, 3),
              "results": results,
              "caveat": "Historical venue retrieval, not manuscript acceptance prediction; 2024 reused for development"}
    (inventory_dir / "retrieval_metrics.json").write_text(json.dumps(result, indent=2) + "\n")
    rows = []
    for i, work in enumerate(dev.itertuples(index=False)):
        rows.append({"work_id": work.work_id, "actual_venue": actual[i],
                     "actual_venue_type": work.venue_type, "primary_topic_for_audit_only": work.primary_topic_id,
                     "routed_topic_from_frozen_model": routes[i],
                     "actual_venue_in_pool": actual[i] in ids,
                     "historical_support_of_actual": support.get(actual[i], 0),
                     **{name: json.dumps(predicted[name][i]) for name in predicted}})
    pd.DataFrame(rows).to_parquet(inventory_dir / "venue_benchmark_predictions.parquet", index=False)
    return result


def benchmark_breakdown(inventory_dir: Path, *, bootstrap_reps: int = 1000,
                        seed: int = 20261104) -> dict:
    """Development-only subgroup and paired uncertainty audit from frozen predictions."""
    frame = pd.read_parquet(inventory_dir / "venue_benchmark_predictions.parquet")
    methods = [name for name in frame if name.startswith("v") and name in {
        "v0_popularity", "v1_frozen_topic_frequency", "v2_tfidf_papers", "v3_venue_profiles"}]
    for name in methods:
        frame[name + "_hit5"] = [bool(actual and actual in json.loads(pred)[:5])
                                for actual, pred in zip(frame.actual_venue, frame[name])]
    frame["support_bucket"] = pd.cut(frame.historical_support_of_actual,
        bins=[-1, 0, 1, 2, 4, 9, float("inf")],
        labels=["0", "1", "2", "3-4", "5-9", "10+"])
    groups = {}
    for column in ("actual_venue_type", "primary_topic_for_audit_only", "support_bucket"):
        groups[column] = {}
        for value, part in frame.groupby(column, dropna=False, observed=True):
            groups[column][str(value)] = {"queries": len(part),
                "candidate_coverage": float(part.actual_venue_in_pool.mean()),
                **{name + "_recall5": float(part[name + "_hit5"].mean()) for name in methods}}
    rng = np.random.default_rng(seed)
    n = len(frame)
    v0 = frame.v0_popularity_hit5.to_numpy(dtype=float)
    v3 = frame.v3_venue_profiles_hit5.to_numpy(dtype=float)
    differences = np.empty(bootstrap_reps)
    for i in range(bootstrap_reps):
        ix = rng.integers(0, n, size=n)
        differences[i] = (v3[ix] - v0[ix]).mean()
    result = {"development_queries": n, "groups": groups,
        "paired_bootstrap_v3_minus_v0_recall5": {
            "estimate": float(v3.mean() - v0.mean()),
            "ci_95_percentile": [float(x) for x in np.quantile(differences, [.025, .975])],
            "repetitions": bootstrap_reps, "seed": seed,
            "caveat": "Exploratory 2024 development interval; not independent final-test evidence"}}
    (inventory_dir / "retrieval_breakdown.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


class VenueDiscoveryService:
    """Local-only inference over an already verified historical candidate index."""

    def __init__(self, index_path: Path):
        if not index_path.is_file():
            raise FileNotFoundError(index_path)
        self.index = joblib.load(index_path)

    def discover_publication_venues(self, title: str, abstract: str,
                                    top_k: int = 5, selected_topic_id: str | None = None) -> dict:
        text = query_text(title, abstract)
        if not 1 <= top_k <= 10:
            raise ValueError("top_k must be 1–10")
        if selected_topic_id is not None and not re.fullmatch(
            r"(?:https://openalex\.org/)?T\d+", selected_topic_id
        ):
            raise ValueError("Manual topic selection must be an OpenAlex Topic ID")
        ids = self.index["venue_ids"]
        if selected_topic_id:
            topic = (selected_topic_id if selected_topic_id.startswith("https://openalex.org/")
                     else "https://openalex.org/" + selected_topic_id)
            evidence = {v: self.index["topic_venue_counts"].get((topic, v), 0) for v in ids}
            ranked = (rank_from_scores(evidence, {v for v, score in evidence.items() if score > 0}, top_k) if any(evidence.values()) else
                      rank_text(self.index, text, method="v2_tfidf_papers", top_k=top_k))
            method = "manual_topic_frequency" if any(evidence.values()) else "text_fallback"
        else:
            ranked = rank_text(self.index, text, method="v2_tfidf_papers", top_k=top_k)
            method = "historical_text_similarity"
        info = {v["canonical_venue_id"]: v for v in self.index["venues"]}
        venues = [{"venue_id": vid, "venue_name": info[vid]["display_name"],
                   "venue_type": info[vid]["venue_type"], "rank": rank,
                   "historical_support": info[vid]["historical_support"],
                   "evidence": method + "; pre-2024 historical publications",
                   "provenance": "OpenAlex local metadata; Crossref when lookup available"}
                  for rank, vid in enumerate(ranked, 1)]
        return {"status": "candidate_venues_available" if venues else "insufficient_data",
                "input": {"title": title}, "manual_topic_selection": selected_topic_id,
                "venues": venues,
                "limitations": ["Historical publication evidence is not an acceptance prediction.",
                    "Check each venue's current aims, scope and submission rules independently."]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("evaluate")
    run.add_argument("--inventory-dir", type=Path, required=True)
    run.add_argument("--min-support", type=int, default=2)
    infer = sub.add_parser("discover")
    infer.add_argument("--index", type=Path, required=True)
    infer.add_argument("--title", required=True)
    infer.add_argument("--abstract", required=True)
    infer.add_argument("--top-k", type=int, default=5)
    infer.add_argument("--selected-topic-id")
    args = parser.parse_args(argv)
    if args.command == "evaluate":
        result = evaluate(args.inventory_dir, min_support=args.min_support)
    else:
        result = VenueDiscoveryService(args.index).discover_publication_venues(
            args.title, args.abstract, args.top_k, args.selected_topic_id)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
