"""RQ3: descriptive and adjusted observational OA–citation associations."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from ai_research_trends.analysis.descriptive import numeric_summary
from ai_research_trends.analysis.statistical_tests import benjamini_hochberg, ols_hc3


OA_ORDER = ("closed", "hybrid", "bronze", "diamond", "green", "gold")


def oa_descriptives(works: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    included = works.loc[works["has_oa_metadata"]].copy()
    if included["oa_status"].isna().any() or not set(included["oa_status"]).issubset(OA_ORDER):
        raise ValueError("Unexpected or absent OA category")
    rows = []
    composition = []
    for label, group in included.groupby("oa_status", observed=True):
        cited = numeric_summary(group["cited_by_count"])
        fwci = numeric_summary(group["fwci"], total=len(group))
        rows.append({"oa_status": label, "n": len(group), "denominator_oa_observed": len(included),
                     "sample_percent": 100 * len(group) / len(included),
                     "mean_citations": cited["mean"], "median_citations": cited["median"],
                     "citation_iqr": cited["iqr"], "zero_citation_percent": cited["zero_percent"],
                     "fwci_n": fwci["n"], "fwci_coverage_percent": 100 * fwci["n"] / len(group),
                     "mean_fwci": fwci["mean"], "median_fwci": fwci["median"]})
        for field in ("publication_year", "work_type", "primary_subfield_id"):
            for value, count in group[field].value_counts(dropna=False).items():
                composition.append({"oa_status": label, "group_by": field,
                                    "group": str(value), "works": int(count),
                                    "oa_status_denominator": len(group),
                                    "within_status_percent": 100 * count / len(group)})
    result = pd.DataFrame(rows)
    if result["n"].sum() != len(included):
        raise ValueError("OA category counts fail to sum to observed denominator")
    return result, pd.DataFrame(composition)


def oa_binary_descriptives(works: pd.DataFrame) -> pd.DataFrame:
    """Additional OA-vs-closed view; do not collapse the six-status primary model."""
    observed = works.loc[works["has_oa_metadata"]]
    rows = []
    for state, group in observed.groupby("is_oa", observed=True):
        citations = numeric_summary(group["cited_by_count"])
        fwci = numeric_summary(group["fwci"], total=len(group))
        rows.append({"is_oa": bool(state), "n": len(group), "denominator_oa_observed": len(observed),
                     "mean_citations": citations["mean"], "median_citations": citations["median"],
                     "zero_citation_percent": citations["zero_percent"],
                     "fwci_n": fwci["n"], "median_fwci": fwci["median"]})
    result = pd.DataFrame(rows)
    if result.n.sum() != len(observed):
        raise ValueError("Binary OA counts do not sum to observed denominator")
    return result


def _design(works: pd.DataFrame, *, specification: str) -> tuple[np.ndarray, list[str], pd.DataFrame]:
    if specification == "unadjusted_binary":
        required = ["is_oa", "log1p_citations", "cited_by_count"]
        frame = works[required].dropna().copy()
        columns = {"oa_open": frame["is_oa"].astype(int).to_numpy(dtype=float)}
    elif specification in {"adjusted_status_year", "articles_reviews_status_year", "adjusted_status_age"}:
        frame = works.copy()
        if specification == "articles_reviews_status_year":
            frame = frame.loc[frame["work_type"].isin(["article", "review"])].copy()
        frame = frame.dropna(subset=["oa_status", "log1p_citations", "publication_year",
                                     "work_type", "primary_subfield_id"])
        if specification == "adjusted_status_age":
            frame = frame.dropna(subset=["publication_age_years"])
        if not set(frame["oa_status"]).issubset(OA_ORDER) or "closed" not in set(frame["oa_status"]):
            raise ValueError("OA model requires six known statuses and a closed reference")
        columns = {f"oa_{label}": (frame["oa_status"] == label).astype(float).to_numpy()
                   for label in OA_ORDER if label != "closed"}
        if specification == "adjusted_status_age":
            columns["publication_age_years"] = frame["publication_age_years"].to_numpy(dtype=float)
        else:
            for year in range(2021, 2026):
                columns[f"year_{year}"] = (frame["publication_year"] == year).astype(float).to_numpy()
        for kind in ("preprint", "review"):
            if kind in set(frame["work_type"]):
                columns[f"type_{kind}"] = (frame["work_type"] == kind).astype(float).to_numpy()
        columns["subfield_1707"] = (frame["primary_subfield_id"] == "1707").astype(float).to_numpy()
    else:
        raise ValueError(f"Unknown prespecified OA model {specification}")
    if len(frame) < 100:
        raise ValueError("Insufficient complete cases for prespecified OA model")
    names = ["intercept", *columns]
    x = np.column_stack([np.ones(len(frame)), *columns.values()])
    return x, names, frame


def oa_models(works: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Fit four prespecified OLS/HC3 analyses; report every retained denominator."""
    results = []
    diagnostics = []
    specs = ("unadjusted_binary", "adjusted_status_year", "articles_reviews_status_year", "adjusted_status_age")
    for spec in specs:
        x, terms, frame = _design(works, specification=spec)
        fit = ols_hc3(frame["log1p_citations"].to_numpy(dtype=float), x, terms)
        oa_terms = [i for i, term in enumerate(terms) if term.startswith("oa_")]
        q = benjamini_hochberg([fit.p_values[i] for i in oa_terms]) if len(oa_terms) > 1 else np.array([fit.p_values[i] for i in oa_terms])
        q_by_index = dict(zip(oa_terms, q, strict=True))
        diagnostics.append({"model": spec, "input_works": len(works), "complete_cases": fit.n,
                            "excluded_works": len(works) - fit.n, "rank": fit.rank,
                            "parameters": len(terms), "condition_number": fit.condition_number,
                            "r_squared": fit.r_squared,
                            "count_variance_to_mean": float(frame["cited_by_count"].var(ddof=1) / frame["cited_by_count"].mean()),
                            "abs_residual_vs_fitted_spearman": fit.residual_abs_fitted_spearman,
                            "outcome": "log1p_citations", "covariance": "HC3",
                            "reference_oa": "closed" if spec != "unadjusted_binary" else "not OA",
                            "reference_year": "2020" if spec.endswith("_year") else "age continuous or unadjusted",
                            "reference_work_type": "article", "reference_subfield": "1702"})
        for index, term in enumerate(terms):
            estimate = float(fit.coefficients[index])
            results.append({"model": spec, "term": term, "n_complete_cases": fit.n,
                            "estimate_log1p": estimate, "se_hc3": float(fit.standard_errors[index]),
                            "ci95_low": float(fit.ci_low[index]), "ci95_high": float(fit.ci_high[index]),
                            "p_value": float(fit.p_values[index]),
                            "q_value_oa_family": float(q_by_index[index]) if index in q_by_index else math.nan,
                            "one_plus_citations_ratio_minus_one": float(np.expm1(estimate)) if term.startswith("oa_") else math.nan,
                            "interpretation": "conditional association in log(1+citations), not causal"})
    # Cohort-specific binary contrasts explicitly show the age/year dependence.
    contrasts = []
    for year, cohort in works.groupby("publication_year", observed=True):
        observed = cohort.loc[cohort["has_oa_metadata"]]
        for state, group in observed.groupby("is_oa", observed=True):
            contrasts.append({"publication_year": int(year), "is_oa": bool(state),
                              "n": len(group), "year_oa_observed_denominator": len(observed),
                              "median_citations": float(group["cited_by_count"].median()),
                              "mean_log1p_citations": float(group["log1p_citations"].mean())})
    return pd.DataFrame(results), pd.DataFrame(diagnostics), pd.DataFrame(contrasts)
