"""Leakage-conscious, ID-level feasibility measures for literature discovery."""

from __future__ import annotations

import hashlib
import math
from typing import Iterable

import numpy as np
import pandas as pd


def validate_graph(works: pd.DataFrame, references: pd.DataFrame) -> None:
    """Reject grain and foreign-key errors before any citation analysis."""
    if works.work_id.isna().any() or not works.work_id.is_unique:
        raise ValueError("works must have unique nonnull Work IDs")
    if references[["citing_work_id", "referenced_work_id"]].isna().any().any():
        raise ValueError("reference edges must have nonnull IDs")
    if references.duplicated(["citing_work_id", "referenced_work_id"]).any():
        raise ValueError("duplicate reference edges")
    if not references.citing_work_id.isin(works.work_id).all():
        raise ValueError("reference citing ID is not in the sampled works")


def query_eligibility(works: pd.DataFrame, references: pd.DataFrame,
                      *, minimum_references: int = 10) -> pd.DataFrame:
    """Define usable text as >=50 characters and >=8 whitespace-separated words."""
    validate_graph(works, references)
    result = works[["work_id", "publication_year", "publication_date", "work_type",
                    "primary_subfield_id", "title", "abstract", "reference_list_status"]].copy()
    counts = references.groupby("citing_work_id").size()
    result["matched_references"] = result.work_id.map(counts).fillna(0).astype("int32")
    result["valid_title"] = result.title.fillna("").str.strip().ne("")
    abstract = result.abstract.fillna("").str.strip()
    result["usable_abstract"] = abstract.str.len().ge(50) & abstract.str.split().str.len().ge(8)
    dates = pd.to_datetime(result.publication_date, errors="coerce")
    result["valid_date"] = (dates.notna() & dates.dt.year.eq(result.publication_year) &
                            dates.between(pd.Timestamp("2020-01-01"), pd.Timestamp("2025-12-31")))
    for threshold in (5, 10, 15):
        result[f"refs_ge_{threshold}"] = result.matched_references.ge(threshold)
        result[f"eligible_{threshold}"] = (result.valid_title & result.usable_abstract &
                                              result.valid_date & result[f"refs_ge_{threshold}"])
    if minimum_references not in (5, 10, 15):
        result["eligible"] = (result.valid_title & result.usable_abstract & result.valid_date &
                              result.matched_references.ge(minimum_references))
    else:
        result["eligible"] = result[f"eligible_{minimum_references}"]
    return result.drop(columns=["title", "abstract"])


def eligibility_by(frame: pd.DataFrame, group: str) -> pd.DataFrame:
    """One row per stratum with explicit missing/empty reference-list states."""
    rows = []
    for value, part in frame.groupby(group, dropna=False, sort=True):
        rows.append({group: value, "sample_works": len(part),
                     "valid_title": int(part.valid_title.sum()),
                     "usable_abstract": int(part.usable_abstract.sum()),
                     "reference_list_present": int(part.reference_list_status.eq("present").sum()),
                     "reference_list_empty": int(part.reference_list_status.eq("empty").sum()),
                     "reference_list_missing": int(part.reference_list_status.eq("missing").sum()),
                     "refs_ge_5": int(part.refs_ge_5.sum()),
                     "refs_ge_10": int(part.refs_ge_10.sum()),
                     "refs_ge_15": int(part.refs_ge_15.sum()),
                     "eligible_5": int(part.eligible_5.sum()),
                     "eligible_10": int(part.eligible_10.sum()),
                     "eligible_15": int(part.eligible_15.sum()),
                     "eligible_percent": 100 * float(part.eligible.mean())})
    return pd.DataFrame(rows)


def candidate_frequency(references: pd.DataFrame, historical_query_ids: Iterable[str]) -> pd.Series:
    """Count distinct permitted citing queries per referenced Work ID."""
    ids = set(historical_query_ids)
    edges = references.loc[references.citing_work_id.isin(ids)]
    return edges.groupby("referenced_work_id").citing_work_id.nunique().sort_index().astype("int32")


def candidate_pool(frequency: pd.Series, minimum_citers: int) -> set[str]:
    if minimum_citers < 1:
        raise ValueError("minimum_citers must be positive")
    return set(frequency.index[frequency.ge(minimum_citers)])


def coverage_per_query(queries: pd.DataFrame, references: pd.DataFrame,
                       pool: set[str], candidate_dates: pd.Series) -> pd.DataFrame:
    """Report pure ID overlap and known-date screening separately.

    Unknown candidate dates remain unknown; the ID-level overlap is an upper
    bound on time-valid coverage, not a verified historical candidate set.
    """
    query_rows = queries.set_index("work_id")
    edges = references.loc[references.citing_work_id.isin(query_rows.index),
                           ["citing_work_id", "referenced_work_id"]].copy()
    if edges.empty:
        return pd.DataFrame(columns=["work_id", "publication_year", "work_type",
                                     "primary_subfield_id", "observed_references", "pool_hits_id",
                                     "known_future_hits", "known_time_valid_hits",
                                     "unknown_date_hits", "screened_pool_hits",
                                     "id_overlap_coverage", "screened_overlap_coverage"])
    edges["in_pool"] = edges.referenced_work_id.isin(pool)
    edges["candidate_date"] = pd.to_datetime(edges.referenced_work_id.map(candidate_dates))
    edges["query_date"] = pd.to_datetime(edges.citing_work_id.map(query_rows.publication_date))
    edges["known_future"] = edges.in_pool & edges.candidate_date.notna() & (
        edges.candidate_date > edges.query_date)
    edges["known_time_valid"] = edges.in_pool & edges.candidate_date.notna() & (
        edges.candidate_date <= edges.query_date)
    edges["unknown_date"] = edges.in_pool & edges.candidate_date.isna()
    grouped = edges.groupby("citing_work_id").agg(
        observed_references=("referenced_work_id", "size"),
        pool_hits_id=("in_pool", "sum"), known_future_hits=("known_future", "sum"),
        known_time_valid_hits=("known_time_valid", "sum"),
        unknown_date_hits=("unknown_date", "sum"),
    )
    grouped["id_overlap_coverage"] = grouped.pool_hits_id / grouped.observed_references
    grouped["screened_pool_hits"] = grouped.pool_hits_id - grouped.known_future_hits
    grouped["screened_overlap_coverage"] = grouped.screened_pool_hits / grouped.observed_references
    grouped.index.name = "work_id"
    out = grouped.reset_index().merge(
        queries[["work_id", "publication_year", "work_type", "primary_subfield_id"]],
        on="work_id", how="left", validate="one_to_one")
    return out[["work_id", "publication_year", "work_type", "primary_subfield_id",
                "observed_references", "pool_hits_id", "known_future_hits",
                "known_time_valid_hits", "unknown_date_hits", "screened_pool_hits",
                "id_overlap_coverage", "screened_overlap_coverage"]]


def coverage_summary(frame: pd.DataFrame, *, threshold: int, period: str,
                     group_by: str, group: str, pool_size: int) -> dict:
    values = frame.id_overlap_coverage.astype(float)
    return {"minimum_citers": threshold, "period": period, "group_by": group_by,
            "group": group, "pool_size": pool_size, "queries": len(frame),
            "mean_coverage": float(values.mean()) if len(values) else np.nan,
            "median_coverage": float(values.median()) if len(values) else np.nan,
            **{f"p{p}_coverage": float(values.quantile(p / 100)) if len(values) else np.nan
               for p in (10, 25, 75, 90)},
            "zero_coverage_queries": int(values.eq(0).sum()),
            "zero_coverage_percent": 100 * float(values.eq(0).mean()) if len(values) else np.nan,
            "observed_reference_edges": int(frame.observed_references.sum()),
            "id_overlap_edges": int(frame.pool_hits_id.sum()),
            "screened_overlap_edges": int(frame.screened_pool_hits.sum()),
            "known_future_hits": int(frame.known_future_hits.sum()),
            "unknown_date_hits": int(frame.unknown_date_hits.sum())}


def nested_query_subset(query_ids: Iterable[str], fraction: float, seed: int) -> set[str]:
    """Stable nested fractions independent of Pandas row ordering."""
    if not 0 < fraction <= 1:
        raise ValueError("fraction must be in (0, 1]")
    ids = sorted(set(query_ids), key=lambda value: hashlib.sha256(
        f"{seed}:{value}".encode()).hexdigest())
    return set(ids[:max(1, round(len(ids) * fraction))])


def leave_one_query_out_frequency(frequency: pd.Series, references: pd.DataFrame,
                                  query_id: str, historical_query_ids: Iterable[str]) -> pd.Series:
    """Remove a training query's complete edge contribution from popularity."""
    historical_ids = set(historical_query_ids)
    if query_id not in historical_ids:
        raise ValueError("query is not in the permitted historical training set")
    expected = candidate_frequency(references, historical_ids)
    if not frequency.sort_index().equals(expected):
        raise ValueError("frequency was not built from exactly the permitted historical queries")
    own = set(references.loc[references.citing_work_id.eq(query_id), "referenced_work_id"])
    result = frequency.copy()
    for reference_id in own.intersection(result.index):
        result.loc[reference_id] -= 1
    if result.lt(0).any():
        raise ValueError("query edges were not in the historical frequency")
    return result[result.gt(0)]


def split_visible_hidden(reference_ids: Iterable[str], *, seed: int,
                         query_id: str, visible_fraction: float = 0.5) -> tuple[set[str], set[str]]:
    """Deterministic split; hidden IDs must never enter visible features."""
    if not 0 < visible_fraction < 1:
        raise ValueError("visible_fraction must be in (0, 1)")
    ordered = sorted(set(reference_ids), key=lambda ref: hashlib.sha256(
        f"{seed}:{query_id}:{ref}".encode()).hexdigest())
    if len(ordered) < 2:
        raise ValueError("at least two references are needed")
    n = min(len(ordered) - 1, max(1, round(len(ordered) * visible_fraction)))
    return set(ordered[:n]), set(ordered[n:])


def sample_unobserved(pool: Iterable[str], observed: Iterable[str], *, count: int,
                      seed: int, query_id: str) -> list[str]:
    """Reproducible implicit negatives, never labeled human-irrelevant."""
    if count < 0:
        raise ValueError("count must be nonnegative")
    excluded = set(observed) | {query_id}
    available = set(pool) - excluded
    if len(available) < count:
        raise ValueError("candidate pool has fewer unobserved works than requested")
    ordered = sorted(available, key=lambda ref: hashlib.sha256(
        f"negative:{seed}:{query_id}:{ref}".encode()).hexdigest())
    return ordered[:count]


def recall_at_k(ranked: Iterable[str], positives: Iterable[str], k: int) -> float:
    target = set(positives)
    if not target:
        return float("nan")
    if k < 1:
        raise ValueError("k must be positive")
    return len(set(list(ranked)[:k]) & target) / len(target)


def ranking_metrics(ranked: Iterable[str], observed_positives: Iterable[str],
                    candidate_pool_ids: Iterable[str], *, k: int = 20) -> dict[str, float]:
    """Proxy ranking metrics with explicit conditional/end-to-end denominators."""
    if k < 1:
        raise ValueError("k must be positive")
    ranking = list(ranked)
    if len(ranking) != len(set(ranking)):
        raise ValueError("ranked candidates must be unique")
    pool = set(candidate_pool_ids)
    if not set(ranking).issubset(pool):
        raise ValueError("ranking contains an ID outside the candidate pool")
    positives = set(observed_positives)
    available = positives & pool
    hits = set(ranking[:k]) & positives
    dcg = sum(1 / math.log2(index + 2) for index, ref in enumerate(ranking[:k])
              if ref in positives)
    ideal = sum(1 / math.log2(index + 2) for index in range(min(k, len(positives))))
    first = next((index + 1 for index, ref in enumerate(ranking) if ref in positives), None)
    return {
        "pool_coverage": len(available) / len(positives) if positives else float("nan"),
        "conditional_recall_at_k": len(hits) / len(available) if available else float("nan"),
        "end_to_end_recall_at_k": len(hits) / len(positives) if positives else float("nan"),
        "ndcg_at_k_all_observed": dcg / ideal if ideal else float("nan"),
        "mrr_all_observed": 1 / first if first is not None else 0.0,
    }
