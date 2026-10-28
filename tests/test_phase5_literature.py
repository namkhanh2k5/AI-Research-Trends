"""Phase 5 audit primitives; fixtures never masquerade as research results."""

from __future__ import annotations

import math
import re
import shutil
from pathlib import Path

import pandas as pd
import pytest

from ai_research_trends.analysis.reference_eda import (
    reference_age_subset, reference_concentration, top_subarea_references,
)
from ai_research_trends.ml.feasibility import (
    candidate_frequency, candidate_pool, coverage_per_query, eligibility_by,
    leave_one_query_out_frequency, nested_query_subset, query_eligibility,
    ranking_metrics, recall_at_k, sample_unobserved, split_visible_hidden, validate_graph,
)
from ai_research_trends.ml.literature_audit import run_audit
from ai_research_trends.ml.validate_literature_audit import verify_audit


ROOT = Path(__file__).resolve().parents[1]
LOCAL_AUDIT = ROOT / "data/analysis/phase5_literature_pilot_20261028_v4"
PROCESSED = ROOT / "data/processed/openalex_stratified/stratified_20261019T155909Z"


@pytest.fixture
def works() -> pd.DataFrame:
    text = "An abstract with enough words and characters to be a usable research description."
    return pd.DataFrame([
        {"work_id": "W1", "title": "Training work", "abstract": text,
         "publication_date": "2021-03-01", "publication_year": 2021, "work_type": "article",
         "primary_subfield_id": "1702", "reference_list_status": "present"},
        {"work_id": "W2", "title": "Evaluation work", "abstract": text,
         "publication_date": "2023-07-01", "publication_year": 2023, "work_type": "preprint",
         "primary_subfield_id": "1707", "reference_list_status": "present"},
        {"work_id": "W3", "title": None, "abstract": None,
         "publication_date": "2024-01-01", "publication_year": 2024, "work_type": "article",
         "primary_subfield_id": "1702", "reference_list_status": "empty"},
    ])


@pytest.fixture
def edges() -> pd.DataFrame:
    return pd.DataFrame([
        ("W1", "A"), ("W1", "B"), ("W1", "W2"),
        ("W2", "A"), ("W2", "C"), ("W2", "W1"),
    ], columns=["citing_work_id", "referenced_work_id"])


def test_reference_graph_and_query_eligibility(works: pd.DataFrame, edges: pd.DataFrame) -> None:
    validate_graph(works, edges)
    result = query_eligibility(works, edges, minimum_references=2).set_index("work_id")
    assert result.loc["W1", "eligible"] and result.loc["W2", "eligible"]
    assert not result.loc["W3", "eligible"]
    assert result.loc["W3", "matched_references"] == 0
    assert result.loc["W3", "reference_list_status"] == "empty"
    grouped = eligibility_by(result.reset_index(), "publication_year")
    assert grouped.sample_works.sum() == 3
    duplicate = pd.concat([edges, edges.iloc[[0]]], ignore_index=True)
    with pytest.raises(ValueError, match="duplicate"):
        validate_graph(works, duplicate)
    unknown = pd.concat([edges, pd.DataFrame([("missing", "A")], columns=edges.columns)])
    with pytest.raises(ValueError, match="not in"):
        validate_graph(works, unknown)


def test_dates_and_missing_metadata_are_not_invented(works: pd.DataFrame,
                                                      edges: pd.DataFrame) -> None:
    bad = works.copy()
    bad.loc[0, "publication_date"] = "2022-03-01"
    result = query_eligibility(bad, edges, minimum_references=2).set_index("work_id")
    assert not result.loc["W1", "valid_date"]
    assert not result.loc["W1", "eligible"]
    assert result.loc["W3", "reference_list_status"] == "empty"


def test_candidate_pool_temporal_screening(works: pd.DataFrame, edges: pd.DataFrame) -> None:
    frequency = candidate_frequency(edges, {"W1"})
    assert candidate_pool(frequency, 1) == {"A", "B", "W2"}
    assert candidate_pool(frequency, 2) == set()
    with pytest.raises(ValueError):
        candidate_pool(frequency, 0)
    dates = works.set_index("work_id").publication_date
    detail = coverage_per_query(works.loc[works.work_id.eq("W2")], edges,
                                {"A", "W1", "C"}, dates).iloc[0]
    assert detail.observed_references == 3
    assert detail.pool_hits_id == 3
    assert detail.known_time_valid_hits == 1  # W1
    assert detail.unknown_date_hits == 2  # A and C
    early = coverage_per_query(works.loc[works.work_id.eq("W1")], edges,
                               {"W2"}, dates).iloc[0]
    assert early.known_future_hits == 1
    assert early.screened_pool_hits == 0
    assert early.screened_overlap_coverage == 0
    assert coverage_per_query(works.iloc[0:0], edges, set(), dates).empty


def test_leave_one_query_out_and_determinism(edges: pd.DataFrame) -> None:
    ids = {"W1", "W2"}
    frequency = candidate_frequency(edges, ids)
    without_w1 = leave_one_query_out_frequency(frequency, edges, "W1", ids)
    assert without_w1.loc["A"] == 1
    assert "B" not in without_w1.index
    with pytest.raises(ValueError, match="permitted"):
        leave_one_query_out_frequency(frequency, edges, "other", ids)
    with pytest.raises(ValueError, match="exactly"):
        leave_one_query_out_frequency(frequency + 1, edges, "W1", ids)
    small = nested_query_subset(["W3", "W1", "W2", "W4"], .5, 42)
    assert len(small) == 2
    assert small.issubset(nested_query_subset(["W4", "W2", "W1", "W3"], .75, 42))
    visible, hidden = split_visible_hidden({"A", "B", "C", "D"}, seed=7, query_id="W1")
    assert visible.isdisjoint(hidden) and visible | hidden == {"A", "B", "C", "D"}
    assert (visible, hidden) == split_visible_hidden(["D", "C", "B", "A"], seed=7, query_id="W1")
    negatives = sample_unobserved({"A", "B", "C", "D"}, {"A", "B"}, count=2,
                                  seed=7, query_id="W1")
    assert set(negatives) == {"C", "D"}
    assert negatives == sample_unobserved(["D", "C", "B", "A"], ["B", "A"],
                                           count=2, seed=7, query_id="W1")
    with pytest.raises(ValueError, match="fewer"):
        sample_unobserved({"A"}, {"A"}, count=1, seed=7, query_id="W1")


def test_metrics_distinguish_pool_and_generation_recall() -> None:
    metrics = ranking_metrics(["X", "A", "C"], {"A", "B"}, {"A", "C", "X"}, k=2)
    assert metrics["pool_coverage"] == .5
    assert metrics["conditional_recall_at_k"] == 1.0
    assert metrics["end_to_end_recall_at_k"] == .5
    assert metrics["mrr_all_observed"] == .5
    assert 0 < metrics["ndcg_at_k_all_observed"] < 1
    assert recall_at_k(["X", "A"], {"A", "B"}, 2) == .5
    assert math.isnan(ranking_metrics([], [], set())["pool_coverage"])
    with pytest.raises(ValueError, match="unique"):
        ranking_metrics(["A", "A"], {"A"}, {"A"})
    with pytest.raises(ValueError, match="outside"):
        ranking_metrics(["B"], {"A"}, {"A"})


def test_rq5_concentration_age_and_subareas(works: pd.DataFrame,
                                             edges: pd.DataFrame) -> None:
    frequency, lorenz, summary = reference_concentration(edges)
    assert summary["observed_reference_edges"] == len(edges)
    assert summary["distinct_referenced_works"] == 5
    assert len(lorenz) == 6
    assert 0 <= summary["gini"] < 1
    assert frequency.sample_citing_works.max() == 2
    ages, age_summary = reference_age_subset(works, edges)
    assert age_summary["matched_age_edges"] == 2
    assert age_summary["future_dated_edges"] == 1
    assert age_summary["valid_age_edges"] == 1
    assert len(ages) == 2
    top, overlap = top_subarea_references(works, edges, top_k=2)
    assert len(top) == 4
    assert len(overlap) == 1
    assert 0 <= overlap.iloc[0].jaccard <= 1
    empty, empty_lorenz, empty_summary = reference_concentration(edges.iloc[0:0])
    assert empty.empty and empty_lorenz.empty and empty_summary == {}


def test_published_phase5_report_figures_resolve() -> None:
    figure_dir = ROOT / "reports/figures/phase5"
    assert {"query_eligibility_by_year.png", "pool_coverage_2023.png",
            "reference_lorenz.png", "references_per_work.png"}.issubset(
                {path.name for path in figure_dir.glob("*.png")})
    for name in ("PHASE5_FEASIBILITY_REPORT.md", "PHASE5_REFERENCE_EDA_REPORT.md"):
        report = ROOT / "reports" / name
        links = re.findall(r"!\[[^]]*\]\((figures/phase5/[^)]+\.png)\)", report.read_text())
        assert len(links) == 2
        assert all((report.parent / link).is_file() for link in links)


def test_audit_rejects_outputs_inside_source(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    with pytest.raises(ValueError, match="immutable Phase 3 source"):
        run_audit(processed_dir=source, plan=tmp_path / "plan.json",
                  population=tmp_path / "population.json", config=tmp_path / "config.yaml",
                  output_dir=source / "new", report_dir=tmp_path / "reports",
                  published_figure_dir=tmp_path / "figures")


@pytest.mark.skipif(not (LOCAL_AUDIT / "manifest.json").is_file(),
                    reason="Git-ignored local Phase 5 audit is unavailable")
def test_real_audit_checksums_and_published_outputs(tmp_path: Path) -> None:
    result = verify_audit(LOCAL_AUDIT, PROCESSED, ROOT / "reports",
                          ROOT / "reports/figures/phase5")
    assert result == {"valid": True, "decision": "REVISE", "source_tables_verified": 3,
                      "outputs_verified": 25, "published_reports_verified": 3,
                      "published_figures_verified": 4}
    report_dir = tmp_path / "reports"
    report_dir.mkdir()
    for name in ("PHASE5_FEASIBILITY_REPORT.md", "PHASE5_REFERENCE_EDA_REPORT.md",
                 "PHASE5_ML_PILOT_REPORT.md"):
        shutil.copyfile(ROOT / "reports" / name, report_dir / name)
    (report_dir / "PHASE5_FEASIBILITY_REPORT.md").write_text("tampered", encoding="utf-8")
    with pytest.raises(ValueError, match="Published report differs"):
        verify_audit(LOCAL_AUDIT, PROCESSED, report_dir, ROOT / "reports/figures/phase5")
