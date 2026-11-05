"""Published UI aggregate values stay tied to the immutable local source manifests."""

import json
from pathlib import Path

import pandas as pd
import pytest

from ai_research_trends.web.evidence import ROOT, load_published_evidence, verify_available_sources


def test_published_evidence_schema_and_source_hashes():
    evidence = load_published_evidence()
    assert evidence["open_set"]["final_2025_test"] == "SEALED"
    assert evidence["model_comparison"]["validation_in_catalogue"] == 681
    assert evidence["reference_context"]["minimum_historical_citers"] == 2
    checks = verify_available_sources(evidence)
    assert checks["rq6"]  # this aggregate source is intentionally tracked


def test_published_model_values_match_local_originals_when_available():
    evidence = load_published_evidence()
    source = ROOT / evidence["model_comparison"]["source"]
    if not source.exists():
        pytest.skip("Private development metrics absent from clean clone")
    original = json.loads(source.read_text())
    mapping = {"Majority": "majority", "Topic description TF-IDF": "description_match",
               "ComplementNB · expanded": "expanded_complement_nb",
               "Logistic Regression · expanded": "expanded_logistic_regression",
               "Linear SVM · original only": "original_only_linear_svm",
               "Linear SVM · expanded": "expanded_linear_svm"}
    for method in evidence["model_comparison"]["methods"]:
        measured = original["metrics"][mapping[method["name"]]]
        assert method["macro_f1"] == measured["macro_f1"]
        assert method["accuracy"] == measured["accuracy"]
    assert evidence["model_comparison"]["ablation_bootstrap_macro_f1_difference_95"] == (
        original["ablation"]["linear_svm"]["paired_bootstrap"]["macro_f1_difference_95"])


def test_open_set_and_historical_pool_values_match_local_originals_when_available():
    evidence = load_published_evidence()
    source = ROOT / evidence["open_set"]["source"]
    pool = ROOT / evidence["reference_context"]["source"]
    if not source.exists() or not pool.exists():
        pytest.skip("Private development aggregates absent from clean clone")
    opened = json.loads(source.read_text())
    result = opened["methods"]["svm_margin"]["evaluation"]
    assert evidence["open_set"]["outside_false_acceptance"] == result["out_false_acceptance_rate"]
    assert evidence["open_set"]["auroc"] == result["auroc_in_vs_out"]
    assert evidence["open_set"]["end_to_end_correct_placement"] == result["end_to_end_correct_placement"]
    frame = pd.read_csv(pool)
    for strategy, prefix in (("eligible_historical", "original_pool"),
                             ("all_historical", "all_historical_pool")):
        row = frame.loc[(frame.strategy == strategy) & (frame.evaluation_year == 2023)
                        & (frame.minimum_citers == 2) & (frame.group_by == "all")].iloc[0]
        assert evidence["reference_context"][f"{prefix}_candidate_ids"] == row.pool_size
        assert evidence["reference_context"][f"{prefix}_median_id_overlap"] == row.median_coverage
