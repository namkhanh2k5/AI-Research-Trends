"""RQ2: citation and FWCI descriptions with explicit complete-case restrictions."""

from __future__ import annotations

import pandas as pd

from ai_research_trends.analysis.descriptive import grouped_summary, numeric_summary
from ai_research_trends.analysis.statistical_tests import spearman_result


def citation_tables(works: pd.DataFrame, memberships: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if works["work_id"].duplicated().any():
        raise ValueError("Citation analysis requires unique works")
    citations = []
    for field in ("cited_by_count", "log1p_citations"):
        citations.append({"group_by": "all", "group": "all", "metric": field,
                          **numeric_summary(works[field], total=len(works))})
        for group in ("publication_year", "work_type", "primary_subfield_id"):
            citations.extend(grouped_summary(works, group, field).to_dict("records"))
    category = memberships[["work_id", "analytical_layer", "category"]].drop_duplicates()
    category = category.merge(works[["work_id", "cited_by_count", "fwci", "work_type"]],
                              on="work_id", how="left", validate="many_to_one")
    if category["cited_by_count"].isna().any():
        raise ValueError("Category relationship points outside the detailed sample")
    for (layer, label), subset in category.groupby(["analytical_layer", "category"]):
        citations.append({"group_by": f"category:{layer}", "group": label,
                          "metric": "cited_by_count", **numeric_summary(subset["cited_by_count"], total=len(subset))})
    fwci_eligible = works.loc[works["fwci"].notna()].copy()
    if (fwci_eligible["work_type"] == "preprint").any():
        raise ValueError("Preprints must not enter FWCI comparisons")
    fwci = [{"group_by": "all_eligible", "group": "article_or_review", "metric": "fwci",
             **numeric_summary(fwci_eligible["fwci"], total=len(works))}]
    for group in ("publication_year", "work_type", "primary_subfield_id"):
        fwci.extend(grouped_summary(fwci_eligible, group, "fwci").to_dict("records"))
    for (layer, label), subset in category.loc[category["fwci"].notna()].groupby(["analytical_layer", "category"]):
        fwci.append({"group_by": f"category:{layer}", "group": label, "metric": "fwci",
                     **numeric_summary(subset["fwci"], total=len(category.loc[
                         (category["analytical_layer"] == layer) & (category["category"] == label)]))})
    tests = [spearman_result(works["publication_age_years"], works["cited_by_count"],
                             "Older sampled works have more observed citations")]
    return pd.DataFrame(citations), pd.DataFrame(fwci), pd.DataFrame(tests)
