"""RQ5 descriptions of references observed in the fixed detailed sample."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd


def reference_concentration(references: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Use distinct sampled citing works, not global OpenAlex citation counts."""
    counts = references.groupby("referenced_work_id").citing_work_id.nunique().sort_values(
        ascending=False, kind="stable")
    values = np.sort(counts.to_numpy(dtype=np.int64))
    if not len(values):
        return pd.DataFrame(columns=["referenced_work_id", "sample_citing_works"]), pd.DataFrame(
            columns=["reference_fraction", "edge_fraction"]), {}
    cumulative = np.cumsum(values)
    lorenz = pd.DataFrame({"reference_fraction": np.arange(len(values) + 1) / len(values),
                           "edge_fraction": np.r_[0, cumulative / cumulative[-1]]})
    n = len(values)
    gini = (2 * np.sum(np.arange(1, n + 1) * values) / (n * cumulative[-1]) - (n + 1) / n)
    measures = {"distinct_referenced_works": n, "observed_reference_edges": int(cumulative[-1]),
                "gini": float(gini),
                "top_1_percent_share": float(counts.iloc[:math.ceil(n * .01)].sum() / cumulative[-1]),
                "top_5_percent_share": float(counts.iloc[:math.ceil(n * .05)].sum() / cumulative[-1])}
    table = counts.rename("sample_citing_works").rename_axis("referenced_work_id").reset_index()
    return table, lorenz, measures


def reference_age_subset(works: pd.DataFrame, references: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Age is observable only when the referenced ID is also in the sample."""
    dates = works.set_index("work_id").publication_date
    known = references.loc[references.referenced_work_id.isin(dates.index)].copy()
    known["citing_date"] = pd.to_datetime(known.citing_work_id.map(dates))
    known["referenced_date"] = pd.to_datetime(known.referenced_work_id.map(dates))
    known["age_years"] = (known.citing_date - known.referenced_date).dt.days / 365.2425
    known["future_dated"] = known.age_years.lt(0)
    valid = known.loc[~known.future_dated]
    meta = works.set_index("work_id")[["primary_subfield_id", "work_type"]]
    known["citing_subfield"] = known.citing_work_id.map(meta.primary_subfield_id)
    known["citing_work_type"] = known.citing_work_id.map(meta.work_type)
    stats = {"matched_age_edges": len(known), "missing_candidate_date_edges": len(references) - len(known),
             "future_dated_edges": int(known.future_dated.sum()),
             "valid_age_edges": len(valid),
             "median_age_years": float(valid.age_years.median()) if len(valid) else float("nan"),
             "within_five_years_percent": 100 * float(valid.age_years.le(5).mean()) if len(valid) else float("nan")}
    return known, stats


def top_subarea_references(works: pd.DataFrame, references: pd.DataFrame,
                           *, top_k: int = 20) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Primary-subfield lists; one work can cite a reference once per subfield."""
    if top_k < 1:
        raise ValueError("top_k must be positive")
    edges = references.merge(works[["work_id", "primary_subfield_id"]], left_on="citing_work_id",
                             right_on="work_id", how="left", validate="many_to_one")
    counts = edges.groupby(["primary_subfield_id", "referenced_work_id"]).citing_work_id.nunique()
    ranked = counts.rename("sample_citing_works").reset_index().sort_values(
        ["primary_subfield_id", "sample_citing_works", "referenced_work_id"],
        ascending=[True, False, True], kind="stable")
    ranked["rank"] = ranked.groupby("primary_subfield_id").cumcount() + 1
    ranked = ranked.loc[ranked["rank"].le(top_k)].copy()
    titles = works.set_index("work_id").title
    ranked["title_if_in_sample"] = ranked.referenced_work_id.map(titles)
    areas = sorted(ranked.primary_subfield_id.dropna().unique())
    overlap = []
    for left_index, left in enumerate(areas):
        for right in areas[left_index + 1:]:
            a = set(ranked.loc[ranked.primary_subfield_id.eq(left), "referenced_work_id"])
            b = set(ranked.loc[ranked.primary_subfield_id.eq(right), "referenced_work_id"])
            overlap.append({"subfield_a": left, "subfield_b": right,
                            "top_k": top_k, "intersection": len(a & b), "union": len(a | b),
                            "jaccard": len(a & b) / len(a | b) if a | b else float("nan")})
    return ranked, pd.DataFrame(overlap)
