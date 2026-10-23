"""RQ1: exact OpenAlex aggregate trends and separate exploratory text matches."""

from __future__ import annotations

import math

import pandas as pd


def annual_growth(counts: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, float]]:
    """Compute observed 2020–2025 changes; never infer a 2019 baseline."""
    required = {"year", "work_count"}
    if not required.issubset(counts) or counts["year"].duplicated().any():
        raise ValueError("Population year counts require unique year/work_count rows")
    result = counts[["year", "work_count"]].sort_values("year").reset_index(drop=True).copy()
    if result["year"].tolist() != list(range(2020, 2026)) or (result["work_count"] < 0).any():
        raise ValueError("Expected six complete, nonnegative 2020–2025 population counts")
    previous = result["work_count"].shift(1)
    result["absolute_yoy_change"] = result["work_count"].diff().astype("Int64")
    result["yoy_growth_percent"] = ((result["work_count"] - previous) / previous * 100).where(previous > 0)
    baseline = int(result.loc[0, "work_count"])
    result["index_2020_100"] = 100 * result["work_count"] / baseline if baseline > 0 else math.nan
    last = int(result.loc[len(result) - 1, "work_count"])
    metrics = {
        "total_change": last - baseline,
        "total_growth_percent": (last / baseline - 1) * 100 if baseline else math.nan,
        "cagr_percent": ((last / baseline) ** (1 / 5) - 1) * 100 if baseline and last else math.nan,
    }
    return result, metrics


def population_and_native_trends(
    population: pd.DataFrame, primary_series: str
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, float]]:
    """Use exact compatible non-retracted series; retain overlap explicitly."""
    if primary_series not in set(population["series"]):
        raise ValueError(f"Missing approved primary series {primary_series}")
    population_base = population.loc[population["series"] == primary_series]
    trends, metrics = annual_growth(population_base)
    trends["series"] = primary_series
    trends["source_scope"] = "complete OpenAlex primary non-retracted aggregate"
    primary_by_year = trends.set_index("year")["work_count"]
    native = population.loc[
        population["series"].str.endswith("_primary_non_retracted")
        & (population["series"] != primary_series)
    ].copy()
    if native.empty or any(len(group) != 6 for _, group in native.groupby("series")):
        raise ValueError("Supported native-topic series are incomplete")
    if native.duplicated(["series", "year"]).any():
        raise ValueError("Duplicate native-topic aggregate key")
    native["primary_population_count"] = native["year"].map(primary_by_year)
    if native["primary_population_count"].isna().any() or (native["work_count"] > native["primary_population_count"]).any():
        raise ValueError("Native-topic numerators are incompatible with primary population")
    native["share_of_primary_percent"] = 100 * native["work_count"] / native["primary_population_count"]
    native = native.sort_values(["series", "year"]).reset_index(drop=True)
    native["yoy_growth_percent"] = native.groupby("series")["work_count"].pct_change(fill_method=None) * 100
    first = native.groupby("series")["work_count"].transform("first")
    native["index_2020_100"] = (100 * native["work_count"] / first).where(first > 0)
    native["methodology"] = "overlapping OpenAlex-native topics; not a partition"
    return trends, native, metrics


def emerging_sample_trends(works: pd.DataFrame, memberships: pd.DataFrame) -> pd.DataFrame:
    """Count observed rule matches, retaining per-year sample/text denominators."""
    custom = memberships.loc[memberships["analytical_layer"] == "custom_emerging", ["work_id", "category"]]
    if custom.duplicated(["work_id", "category"]).any():
        raise ValueError("Duplicate custom category membership")
    years = works.set_index("work_id")["publication_year"]
    custom = custom.assign(year=custom["work_id"].map(years))
    if custom["year"].isna().any():
        raise ValueError("Custom membership references an unknown work")
    categories = sorted(custom["category"].unique())
    rows = []
    for year, cohort in works.groupby("publication_year", observed=True):
        for category in categories:
            matched = int(((custom["year"] == year) & (custom["category"] == category)).sum())
            rows.append({"year": int(year), "analytical_layer": "custom_emerging",
                         "category": category, "matched_sample_works": matched,
                         "sample_year_denominator": len(cohort),
                         "abstract_available_works": int(cohort["has_abstract"].sum()),
                         "usable_text_works": int(cohort["has_usable_text"].sum()),
                         "observed_sample_percent": 100 * matched / len(cohort),
                         "scope": "sample-based exploratory text-rule matches; not a population count"})
    return pd.DataFrame(rows)
