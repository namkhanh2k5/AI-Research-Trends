"""Reviewer-facing Phase 6B aggregate evidence stays consistent with reports."""

import json
from pathlib import Path

import pandas as pd

from ai_research_trends.preprocessing.validate_tables import file_sha256


ROOT=Path(__file__).resolve().parents[1]
PUBLIC=ROOT/"reports"/"phase6b"


def test_public_summary_matches_catalogue_and_decision_text():
    summary=json.loads((PUBLIC/"summary.json").read_text())
    report=(ROOT/"reports"/"PHASE6B_FINAL_TOPIC_VALIDATION_REPORT.md").read_text()
    assert summary["test_2025"]=="sealed_not_evaluated"
    assert summary["human_semantic_validation"]=="pending"
    assert summary["catalogue_sha256"]==file_sha256(ROOT/"config"/"phase6b_catalogue.yaml")
    assert summary["metadata_sha256"]==file_sha256(ROOT/"config"/"phase6b_topic_metadata.csv")
    assert summary["outputs_verified"]==34
    assert "REVISE" in report and "2025 final test remains sealed" in report
    evaluation=summary["open_set"]["svm_max_decision"]["evaluation"]
    assert f'{100*evaluation["in_acceptance_rate"]:.1f}%' in report
    assert f'{100*evaluation["out_false_acceptance_rate"]:.1f}%' in report
    assert f'{100*evaluation["end_to_end_correct_placement"]:.1f}%' in report


def test_public_csvs_are_aggregate_only_and_match_summary():
    summary=json.loads((PUBLIC/"summary.json").read_text())
    scope=pd.read_csv(PUBLIC/"scope_review.csv")
    assert len(scope)==20 and scope.catalogue_b.sum()==14
    assert scope.loc[scope.catalogue_b,"train_2020_2023"].sum()==summary["catalogues"]["B"]["train_rows"]
    assert scope.loc[scope.catalogue_b,"validation_2024"].sum()==summary["catalogues"]["B"]["validation_rows"]
    for path in PUBLIC.glob("*.csv"):
        table=pd.read_csv(path)
        assert not {"work_id","title","abstract","doi","example_id"}&set(table.columns)
        assert len(table)>0
