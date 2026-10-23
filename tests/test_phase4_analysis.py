"""Offline, controlled tests of Phase 4 denominators, inference and networks."""

from __future__ import annotations

import math
import hashlib
import json

import numpy as np
import pandas as pd
import pytest

from ai_research_trends.analysis.citation_impact import citation_tables
from ai_research_trends.analysis.collaboration_analysis import pair_edges, graph_summary
from ai_research_trends.analysis.descriptive import analytical_subset_audit, numeric_summary
from ai_research_trends.analysis.load_data import safe_work_join
from ai_research_trends.analysis.open_access_analysis import OA_ORDER, oa_binary_descriptives, oa_descriptives, oa_models
from ai_research_trends.analysis.publication_trends import annual_growth, emerging_sample_trends, population_and_native_trends
from ai_research_trends.analysis.statistical_tests import benjamini_hochberg, ols_hc3
from ai_research_trends.analysis.validation import verify_run


def test_growth_uses_five_intervals_and_no_2020_baseline() -> None:
    frame = pd.DataFrame({"year": range(2020, 2026), "work_count": [100, 110, 100, 120, 150, 200]})
    result, metrics = annual_growth(frame)
    assert pd.isna(result.iloc[0].yoy_growth_percent)
    assert result.iloc[1].absolute_yoy_change == 10
    assert math.isclose(result.iloc[1].yoy_growth_percent, 10)
    assert result.iloc[-1].index_2020_100 == 200
    assert math.isclose(metrics["cagr_percent"], (2 ** 0.2 - 1) * 100)
    with pytest.raises(ValueError, match="six complete"):
        annual_growth(frame.iloc[1:])


def test_native_topic_series_overlap_without_being_summed() -> None:
    rows = []
    names = ["study_population_primary_non_retracted"] + [
        f"{name}_primary_non_retracted" for name in
        ("computer_vision", "explainable_ai", "multimodal_machine_learning_applications",
         "natural_language_processing", "reinforcement_learning")
    ]
    for series in names:
        for year in range(2020, 2026):
            rows.append({"series": series, "year": year,
                         "work_count": 100 if series.startswith("study_") else 60})
    growth, native, _ = population_and_native_trends(pd.DataFrame(rows), names[0])
    assert growth.work_count.sum() == 600
    assert native.groupby("year").work_count.sum().eq(300).all()
    assert native.share_of_primary_percent.eq(60).all()
    assert native.methodology.str.contains("overlapping").all()


def test_citation_summary_retains_zero_and_outlier() -> None:
    result = numeric_summary(pd.Series([0, 1, 2, 1000, None]))
    assert result["n"] == 4 and result["denominator"] == 5
    assert result["max"] == 1000 and result["zero_percent"] == 25
    assert result["mean"] > result["median"]


def test_work_join_rejects_many_to_many_inflation() -> None:
    works = pd.DataFrame({"work_id": ["W1", "W2"]})
    bridge = pd.DataFrame({"work_id": ["W1", "W1"], "topic": ["A", "B"]})
    with pytest.raises(ValueError, match="not unique"):
        safe_work_join(works, bridge)
    joined = safe_work_join(works, pd.DataFrame({"work_id": ["W1"], "count": [2]}))
    assert len(joined) == 2 and joined.work_id.nunique() == 2


def test_emerging_counts_use_sample_year_denominator_not_population() -> None:
    works = pd.DataFrame({"work_id": ["W1", "W2", "W3"], "publication_year": [2020, 2020, 2021],
                          "has_abstract": [True, False, True], "has_usable_text": [True, True, True]})
    members = pd.DataFrame({"work_id": ["W1", "W1"], "analytical_layer": ["custom_emerging"] * 2,
                            "category": ["large_language_models", "retrieval_augmented_generation"]})
    result = emerging_sample_trends(works, members)
    row = result.query("year == 2020 and category == 'large_language_models'").iloc[0]
    assert row.matched_sample_works == 1 and row.sample_year_denominator == 2
    assert row.abstract_available_works == 1 and row.observed_sample_percent == 50


def _model_fixture() -> pd.DataFrame:
    rows = []
    for status_index, status in enumerate(OA_ORDER):
        for year in range(2020, 2026):
            for kind in ("article", "review", "preprint"):
                for subfield in ("1702", "1707"):
                    for replicate in range(2):
                        citations = status_index * 3 + (year - 2020) * 2 + replicate + (kind == "review")
                        rows.append({"work_id": f"W{len(rows)}", "oa_status": status,
                                     "is_oa": status != "closed", "has_oa_metadata": True,
                                     "publication_year": year, "work_type": kind,
                                     "primary_subfield_id": subfield,
                                     "publication_age_years": 6 - (year - 2020) + replicate * .1,
                                     "cited_by_count": citations,
                                     "log1p_citations": math.log1p(citations),
                                     "fwci": None if kind == "preprint" else float(citations) / 10})
    return pd.DataFrame(rows)


def test_oa_reference_categories_and_complete_case_accounting() -> None:
    works = _model_fixture()
    descriptive, composition = oa_descriptives(works)
    binary = oa_binary_descriptives(works)
    assert descriptive.n.sum() == len(works)
    assert binary.n.sum() == len(works) and set(binary.is_oa) == {True, False}
    assert set(descriptive.oa_status) == set(OA_ORDER)
    assert composition.query("group_by == 'work_type'").works.sum() == len(works)
    coefficients, diagnostics, year = oa_models(works)
    assert set(coefficients.query("model == 'adjusted_status_year' and term.str.startswith('oa_')", engine="python").term) == {
        "oa_hybrid", "oa_bronze", "oa_diamond", "oa_green", "oa_gold"
    }
    assert diagnostics.set_index("model").loc["adjusted_status_year", "complete_cases"] == len(works)
    assert diagnostics.count_variance_to_mean.gt(1).all()
    assert diagnostics.set_index("model").loc["articles_reviews_status_year", "complete_cases"] == len(works) * 2 // 3
    assert year.groupby("publication_year").n.sum().eq(len(works) // 6).all()


def test_regression_result_csv_serialization_retains_terms_and_finite_intervals(tmp_path) -> None:
    coefficients, _, _ = oa_models(_model_fixture())
    path = tmp_path / "model.csv"
    coefficients.to_csv(path, index=False, float_format="%.12g")
    loaded = pd.read_csv(path)
    assert loaded[["model", "term"]].equals(coefficients[["model", "term"]])
    assert np.isfinite(loaded[["estimate_log1p", "ci95_low", "ci95_high"]]).all().all()


def test_fwci_subset_excludes_preprints_and_keeps_category_overlap() -> None:
    works = _model_fixture()
    works["primary_subfield_id"] = "1702"
    works["work_type"] = works["work_type"].astype(str)
    works["publication_age_years"] = works["publication_age_years"].astype(float)
    members = pd.DataFrame({"work_id": [works.iloc[0].work_id, works.iloc[0].work_id],
                            "analytical_layer": ["openalex_native", "custom_emerging"],
                            "category": ["natural_language_processing", "large_language_models"]})
    citation, fwci, tests = citation_tables(works, members)
    assert fwci.query("group_by == 'all_eligible'").iloc[0]["n"] == len(works) * 2 // 3
    assert not fwci.query("group_by == 'work_type'").group.eq("preprint").any()
    assert len(tests) == 1 and citation.query("group_by == 'all' and metric == 'cited_by_count'").iloc[0]["n"] == len(works)
    invalid = works.copy()
    invalid.loc[invalid.work_type.eq("preprint"), "fwci"] = 0.0
    with pytest.raises(ValueError, match="Preprints"):
        citation_tables(invalid, members)


def test_subset_audit_records_exclusions_by_type() -> None:
    works = _model_fixture()
    works["international_collaboration"] = None
    works["institutional_collaboration"] = None
    works["has_usable_text"] = True
    works["has_oa_metadata"] = True
    audit = analytical_subset_audit(works)
    preprints = audit.query("subset == 'fwci_observed' and group_by == 'work_type' and `group` == 'preprint'").iloc[0]
    assert preprints.included_works == 0 and preprints.excluded_works == preprints.total_sample_works
    assert (audit.included_works + audit.excluded_works == audit.total_sample_works).all()


def test_pair_edges_once_per_work_and_complete_coverage_subset() -> None:
    bridge = pd.DataFrame({"work_id": ["W1", "W1", "W1", "W1", "W2", "W2"],
                           "country_code": ["US", "CN", "US", "GB", "CN", "US"]})
    result = pair_edges(bridge, "country_code")
    pair = result.query("source == 'CN' and target == 'US'").iloc[0]
    assert pair.weight_works == 2 == pair.supporting_unique_works
    assert len(result) == 3 and not (result.source == result.target).any()
    complete = pair_edges(bridge, "country_code", complete_work_ids={"W2"})
    assert len(complete) == 1 and complete.iloc[0].weight_works == 1
    graph = graph_summary(result, {"US", "CN", "GB", "FR"}, "fixture")
    assert graph["nodes"] == 4 and graph["edges"] == 3 and graph["connected_components"] == 2


def test_hc3_ols_and_bh_are_finite_and_reproducible() -> None:
    x = np.column_stack([np.ones(40), np.arange(40, dtype=float)])
    y = 1 + 0.25 * x[:, 1] + np.sin(x[:, 1]) * 0.2
    fit_a = ols_hc3(y, x, ["intercept", "trend"])
    fit_b = ols_hc3(y, x, ["intercept", "trend"])
    assert np.array_equal(fit_a.coefficients, fit_b.coefficients)
    assert fit_a.ci_low[1] < fit_a.coefficients[1] < fit_a.ci_high[1]
    assert np.allclose(benjamini_hochberg([0.01, 0.03, 0.2]), [0.03, 0.045, 0.2])
    with pytest.raises(ValueError, match="rank deficient"):
        ols_hc3(y, np.column_stack([x, x[:, 1]]), ["intercept", "trend", "duplicate"])


def test_unknown_affiliation_not_encoded_as_domestic() -> None:
    works = pd.DataFrame({"work_id": ["W1", "W2"], "country_affiliation_complete": [False, True],
                          "authorship_count": [1, 2], "unique_institution_count": [0, 2],
                          "unique_country_count": [0, 2], "has_country_affiliation": [False, True],
                          "has_institution_affiliation": [False, True],
                          "international_collaboration": pd.Series([None, True], dtype="boolean"),
                          "institutional_collaboration": pd.Series([None, True], dtype="boolean"),
                          "publication_year": [2020, 2021], "work_type": ["article", "article"]})
    from ai_research_trends.analysis.collaboration_analysis import collaboration_tables
    summary, _, _, _ = collaboration_tables(
        works, pd.DataFrame(columns=["work_id", "country_code"]),
        pd.DataFrame(columns=["work_id", "institution_id", "institution_name", "country_code"]),
    )
    overall = summary.query("group_by == 'all'").iloc[0]
    assert overall.international_unknown == 1 and overall.international_false == 0
    assert (overall.zero_observed_institutions, overall.multi_observed_institution) == (1, 1)
    assert (overall.zero_observed_countries, overall.multi_observed_country) == (1, 1)


def test_completed_run_verifier_detects_changed_csv(tmp_path) -> None:
    source = tmp_path / "input.json"
    source.write_text("{}")
    table = tmp_path / "results.csv"
    table.write_text("year,count\n2020,1\n")
    digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    (tmp_path / "manifest.json").write_text(json.dumps({
        "status": "complete", "complete": True,
        "inputs": {"source": {"path": str(source), "sha256": digest(source)}},
        "outputs": {"results.csv": {"path": "results.csv", "sha256": digest(table), "rows": 1}},
        "validation": {"fixture": {"status": "PASS"}},
    }))
    assert verify_run(tmp_path)["valid"] is True
    table.write_text("year,count\n2020,2\n")
    with pytest.raises(ValueError, match="checksum mismatch"):
        verify_run(tmp_path)
