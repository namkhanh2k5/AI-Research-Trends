"""Stable, denominator-explicit descriptive statistics for sampled works."""

from __future__ import annotations

import numpy as np
import pandas as pd


def numeric_summary(values: pd.Series, *, total: int | None = None) -> dict[str, float | int]:
    """Summarize observed numeric values without deleting zeroes or outliers."""
    observed = pd.to_numeric(values, errors="raise").dropna()
    if observed.empty:
        return {"n": 0, "denominator": len(values) if total is None else total,
                "mean": np.nan, "median": np.nan, "std": np.nan, "iqr": np.nan,
                "p90": np.nan, "p95": np.nan, "max": np.nan, "zero_percent": np.nan}
    q25, q75, p90, p95 = observed.quantile([0.25, 0.75, 0.9, 0.95])
    return {
        "n": int(len(observed)), "denominator": len(values) if total is None else total,
        "mean": float(observed.mean()), "median": float(observed.median()),
        "std": float(observed.std(ddof=1)) if len(observed) > 1 else np.nan,
        "iqr": float(q75 - q25), "p90": float(p90), "p95": float(p95),
        "max": float(observed.max()), "zero_percent": float(100 * (observed == 0).mean()),
    }


def grouped_summary(frame: pd.DataFrame, group: str, value: str) -> pd.DataFrame:
    rows = []
    for label, subset in frame.groupby(group, dropna=False, observed=True):
        rows.append({"group_by": group, "group": str(label), "metric": value,
                     **numeric_summary(subset[value], total=len(subset))})
    return pd.DataFrame(rows).sort_values("group", kind="stable").reset_index(drop=True)


def missingness_table(works: pd.DataFrame) -> pd.DataFrame:
    flags = {
        "title": works["title"].isna(), "doi": works["doi"].isna(),
        "abstract": works["abstract"].isna(), "fwci": works["fwci"].isna(),
        "language": works["language"].isna(),
        "institution": ~works["has_institution_affiliation"].astype(bool),
        "country": ~works["has_country_affiliation"].astype(bool),
        "open_access": ~works["has_oa_metadata"].astype(bool),
    }
    rows = []
    for group_by in ("all", "publication_year", "work_type"):
        groups = [("all", works.index)] if group_by == "all" else [
            (str(name), group.index) for name, group in works.groupby(group_by, observed=True)
        ]
        for label, index in groups:
            for field, flag in flags.items():
                missing = int(flag.loc[index].sum())
                rows.append({"group_by": group_by, "group": label, "field": field,
                             "denominator_works": len(index), "missing_works": missing,
                             "missing_percent": 100 * missing / len(index) if len(index) else np.nan})
    return pd.DataFrame(rows)


def analytical_subset_audit(works: pd.DataFrame) -> pd.DataFrame:
    """Show how eligibility restrictions change sample composition by group."""
    masks = {
        "fwci_observed": works["fwci"].notna(),
        "international_status_known": works["international_collaboration"].notna(),
        "institutional_status_known": works["institutional_collaboration"].notna(),
        "usable_text": works["has_usable_text"].astype(bool),
        "oa_metadata_observed": works["has_oa_metadata"].astype(bool),
    }
    rows = []
    for subset, mask in masks.items():
        for group_by in ("all", "publication_year", "work_type", "primary_subfield_id"):
            groups = [("all", works.index)] if group_by == "all" else [
                (str(label), group.index) for label, group in works.groupby(group_by, observed=True)
            ]
            for label, index in groups:
                included = int(mask.loc[index].sum())
                rows.append({"subset": subset, "group_by": group_by, "group": label,
                             "total_sample_works": len(index), "included_works": included,
                             "excluded_works": len(index) - included,
                             "coverage_percent": 100 * included / len(index) if len(index) else np.nan})
    return pd.DataFrame(rows)
