"""Bounded 2023 retrieval diagnostic; no supervised fitting or reference inputs.

The query text is title + abstract. Its entire observed reference list is hidden
from candidate selection, vectorizer fitting, scoring and popularity features.
References enter only the final proxy evaluation.
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer

from ai_research_trends.analysis.load_data import load_verified_tables
from ai_research_trends.ml.candidate_pool import historical_citers
from ai_research_trends.ml.feasibility import (
    candidate_frequency, query_eligibility, ranking_metrics,
)
from ai_research_trends.preprocessing.validate_tables import file_sha256


def temporal_relation(candidate_date: object, query_date: object) -> str:
    """Exact dates plus conservative same-year classification."""
    candidate = pd.to_datetime(candidate_date, errors="coerce")
    query = pd.to_datetime(query_date, errors="coerce")
    if pd.isna(candidate) or pd.isna(query):
        return "unknown"
    if candidate > query:
        return "future"
    if candidate.year == query.year:
        return "same_year_nonfuture"
    return "earlier_year"


def temporal_coverage(queries: pd.DataFrame, references: pd.DataFrame,
                      metadata: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Count observed reference overlaps by known/unknown exact publication date."""
    metadata = metadata.copy()
    parsed = pd.to_datetime(metadata.publication_date, errors="coerce")
    full_date = metadata.publication_date.fillna("").astype(str).str.fullmatch(r"\d{4}-\d{2}-\d{2}")
    years = pd.to_numeric(metadata.publication_year, errors="coerce") if (
        "publication_year" in metadata) else pd.Series(np.nan, index=metadata.index)
    year_consistent = years.isna() | years.eq(parsed.dt.year)
    metadata["valid_candidate_date"] = parsed.notna() & full_date & year_consistent
    dates = metadata.assign(publication_date=metadata.publication_date.where(
        metadata.valid_candidate_date)).set_index("work_id").publication_date
    qdates = queries.set_index("work_id").publication_date
    edges = references.loc[references.citing_work_id.isin(queries.work_id),
                           ["citing_work_id", "referenced_work_id"]].copy()
    if edges.empty:
        raise ValueError("No held-out evaluation references")
    pool = set(metadata.work_id)
    edges["in_enriched_subset"] = edges.referenced_work_id.isin(pool)
    edges["temporal_relation"] = [
        temporal_relation(dates.get(ref), qdates.get(citer)) if hit else "not_enriched"
        for citer, ref, hit in edges[["citing_work_id", "referenced_work_id",
                                      "in_enriched_subset"]].itertuples(index=False, name=None)]
    counts = edges.temporal_relation.value_counts().to_dict()
    summary = {"evaluation_queries": len(queries), "observed_reference_edges": len(edges),
               "enriched_candidates": len(metadata),
               "candidates_with_valid_exact_date": int(metadata.valid_candidate_date.sum()),
               "candidates_with_missing_date": int(metadata.publication_date.isna().sum()),
               "candidates_with_invalid_or_inconsistent_date": int((
                   metadata.publication_date.notna() & ~metadata.valid_candidate_date).sum()),
               "enriched_subset_overlap_edges": int(edges.in_enriched_subset.sum()),
               "known_earlier_year_edges": counts.get("earlier_year", 0),
               "same_year_nonfuture_edges": counts.get("same_year_nonfuture", 0),
               "known_future_edges": counts.get("future", 0),
               "unknown_date_overlap_edges": counts.get("unknown", 0),
               "outside_enriched_subset_edges": counts.get("not_enriched", 0)}
    summary["conservative_valid_overlap_edges"] = summary["known_earlier_year_edges"]
    summary["exact_date_valid_overlap_edges"] = (summary["known_earlier_year_edges"] +
                                                 summary["same_year_nonfuture_edges"])
    return edges, summary


def _rank(ids: list[str], scores: np.ndarray) -> list[str]:
    return [ids[i] for i in sorted(range(len(ids)), key=lambda i: (-float(scores[i]), ids[i]))]


def run_diagnostic(*, processed_dir: Path, plan: Path, population: Path,
                   config: Path, enrichment_dir: Path, output_dir: Path) -> dict:
    if output_dir.exists():
        raise FileExistsError(f"Refusing to overwrite diagnostic: {output_dir}")
    manifest = json.loads((enrichment_dir / "manifest.json").read_text())
    if not manifest.get("complete"):
        raise ValueError("Candidate enrichment is incomplete")
    selected_path = enrichment_dir / "selected_training_candidates.csv"
    metadata_path = enrichment_dir / "candidate_metadata.csv"
    if file_sha256(selected_path) != manifest["selection_sha256"] or (
            file_sha256(metadata_path) != manifest["metadata_sha256"]):
        raise ValueError("Candidate selection or metadata checksum mismatch")
    tables, _, _ = load_verified_tables(processed_dir, plan, population, config)
    works, refs = tables["works"], tables["references"]
    if file_sha256(processed_dir / "manifest.json") != manifest["source_phase3_manifest_sha256"]:
        raise ValueError("Enrichment was selected from another Phase 3 source")
    selected = pd.read_csv(selected_path)
    metadata = pd.read_csv(metadata_path)
    history = historical_citers(works, refs, evaluation_year=2023)
    frequency = candidate_frequency(refs, history)
    if not set(selected.work_id).issubset(set(frequency.index)):
        raise ValueError("Enriched IDs are not all historical candidates")
    if any(int(row.historical_citing_works) != int(frequency.loc[row.work_id])
           for row in selected.itertuples(index=False)):
        raise ValueError("Candidate frequency differs from 2020–2022 history")
    if metadata.work_id.duplicated().any() or not set(metadata.work_id).issubset(set(selected.work_id)):
        raise ValueError("Metadata IDs are duplicated or not training-selected")
    eligibility = query_eligibility(works, refs)
    queries = works.loc[works.work_id.isin(
        eligibility.loc[eligibility.eligible & eligibility.publication_year.eq(2023), "work_id"])]
    edges, temporal = temporal_coverage(queries, refs, metadata)
    # A low-ceiling experiment is still a diagnostic, but never a forecast of a full system.
    if len(metadata) < 100 or temporal["exact_date_valid_overlap_edges"] < 100:
        raise ValueError("Enriched subset is too small for a meaningful ranking diagnostic")
    metadata = metadata.copy().sort_values("work_id").reset_index(drop=True)
    metadata["candidate_text"] = (metadata.title.fillna("") + " " +
                                  metadata.abstract.fillna("")).str.strip()
    metadata = metadata.loc[metadata.candidate_text.ne("")].reset_index(drop=True)
    vectorizer = TfidfVectorizer(ngram_range=(1, 2), min_df=2, max_features=100000,
                                dtype=np.float32)
    candidate_matrix = vectorizer.fit_transform(metadata.candidate_text)
    ids = metadata.work_id.tolist()
    candidate_dates = pd.to_datetime(metadata.publication_date, errors="coerce")
    candidate_years = pd.to_numeric(metadata.publication_year, errors="coerce")
    full_dates = metadata.publication_date.fillna("").astype(str).str.fullmatch(
        r"\d{4}-\d{2}-\d{2}")
    candidate_dates = candidate_dates.where(full_dates & (
        candidate_years.isna() | candidate_years.eq(candidate_dates.dt.year)))
    popularity = metadata.historical_citing_works.to_numpy(dtype=float)
    query_text = (queries.title.fillna("") + " " + queries.abstract.fillna("")).tolist()
    query_matrix = vectorizer.transform(query_text)
    targets = refs.groupby("citing_work_id").referenced_work_id.apply(set)
    results: list[dict] = []
    timings_ms: list[float] = []
    for index, query in enumerate(queries.itertuples(index=False)):
        query_date = pd.to_datetime(query.publication_date)
        allowed = np.flatnonzero(candidate_dates.notna() & (candidate_dates <= query_date) &
                                 metadata.work_id.ne(query.work_id))
        valid_ids = [ids[i] for i in allowed]
        if not valid_ids:
            continue
        t0 = time.perf_counter()
        pop = popularity[allowed]
        sim = (query_matrix[index] @ candidate_matrix[allowed].T).toarray().ravel()
        pop_order = _rank(valid_ids, pop)
        text_order = _rank(valid_ids, sim)
        pop_rank = {candidate: rank for rank, candidate in enumerate(pop_order, start=1)}
        text_rank = {candidate: rank for rank, candidate in enumerate(text_order, start=1)}
        fused = np.array([1 / (60 + pop_rank[id_]) + 1 / (60 + text_rank[id_])
                          for id_ in valid_ids])
        rankings = {"historical_popularity": pop_order,
                    "tfidf_title_abstract": text_order,
                    "reciprocal_rank_fusion": _rank(valid_ids, fused)}
        latency_ms = 1000 * (time.perf_counter() - t0)
        timings_ms.append(latency_ms)
        positives = targets.get(query.work_id, set())
        for method, ranked in rankings.items():
            at20 = ranking_metrics(ranked, positives, valid_ids, k=20)
            at50 = ranking_metrics(ranked, positives, valid_ids, k=50)
            results.append({"work_id": query.work_id, "method": method,
                            "observed_references": len(positives),
                            "candidate_universe": len(valid_ids),
                            "available_positives": len(set(positives) & set(valid_ids)),
                            "subset_coverage": at20["pool_coverage"],
                            "candidate_generation_recall_at_20": at20["end_to_end_recall_at_k"],
                            "candidate_generation_recall_at_50": at50["end_to_end_recall_at_k"],
                            "conditional_recall_at_20": at20["conditional_recall_at_k"],
                            "end_to_end_recall_at_20": at20["end_to_end_recall_at_k"],
                            "at_least_one_hit_at_20": bool(set(ranked[:20]) & positives)})
    detail = pd.DataFrame(results)
    if detail.empty:
        raise ValueError("No evaluable 2023 queries")
    summary = detail.groupby("method", sort=True).agg(
        queries=("work_id", "size"),
        mean_subset_coverage=("subset_coverage", "mean"),
        median_subset_coverage=("subset_coverage", "median"),
        mean_recall_at_20=("end_to_end_recall_at_20", "mean"),
        mean_recall_at_50=("candidate_generation_recall_at_50", "mean"),
        mean_conditional_recall_at_20=("conditional_recall_at_20", "mean"),
        queries_with_available_positive=("available_positives", lambda x: int(x.gt(0).sum())),
        queries_with_hit_at_20=("at_least_one_hit_at_20", "sum"),
    ).reset_index()
    output_dir.mkdir(parents=True)
    detail.to_csv(output_dir / "retrieval_queries.csv", index=False,
                  float_format="%.12g", lineterminator="\n")
    summary.to_csv(output_dir / "retrieval_summary.csv", index=False,
                   float_format="%.12g", lineterminator="\n")
    edges.to_csv(output_dir / "temporal_overlap_edges.csv", index=False, lineterminator="\n")
    result = {"status": "complete", "complete": True,
              "created_at_utc": datetime.now(timezone.utc).isoformat(),
              "selection": manifest["selection"],
              "historical_cutoff": "2020–2022 citing works only",
              "evaluation_year": 2023, "query_input": "title and abstract only; all observed references hidden",
              "temporal": temporal,
              "latency_diagnostic": {
                  "scope": "combined scoring and sorting of all three baselines per query; excludes loading and TF-IDF fitting",
                  "queries": len(timings_ms),
                  "median_ms": float(np.median(timings_ms)),
                  "p90_ms": float(np.quantile(timings_ms, .9)),
                  "hardware_dependent": True},
              "enrichment_manifest_sha256": file_sha256(enrichment_dir / "manifest.json"),
              "source_phase3_manifest_sha256": file_sha256(processed_dir / "manifest.json"),
              "outputs": {p.name: {"sha256": file_sha256(p), "bytes": p.stat().st_size}
                          for p in sorted(output_dir.glob("*.csv"))}}
    (output_dir / "manifest.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate bounded, leakage-safe retrieval diagnostics")
    parser.add_argument("--processed-dir", type=Path, default=Path(
        "data/processed/openalex_stratified/stratified_20261019T155909Z"))
    parser.add_argument("--plan", type=Path, default=Path("data/metadata/phase2_sampling_plan.json"))
    parser.add_argument("--population", type=Path, default=Path(
        "data/metadata/population_counts_pre_phase2.json"))
    parser.add_argument("--config", type=Path, default=Path("config/topics.yaml"))
    parser.add_argument("--enrichment-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    result = run_diagnostic(processed_dir=args.processed_dir, plan=args.plan,
                            population=args.population, config=args.config,
                            enrichment_dir=args.enrichment_dir, output_dir=args.output_dir)
    print(json.dumps({"status": result["status"], "temporal": result["temporal"],
                      "output_dir": str(args.output_dir)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
