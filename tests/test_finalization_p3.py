"""Offline regressions for the frozen Phase 3 experiment and inference gates."""

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from ai_research_trends.ml.final_experiments import (
    metric_row, paired_bootstrap, stratified_expansion_fraction, text_features,
)
from ai_research_trends.ml.final_diagnostics import summarize_groups
from ai_research_trends.ml.final_inference import TopicPlacementService, select_champion
from ai_research_trends.ml.final_open_set import bootstrap_open_set, score_predictions
from ai_research_trends.ml.final_test_gate import evaluate_once, verify_human_gate
from ai_research_trends.ml.verify_final_ml import verify_experiment
from ai_research_trends.preprocessing.validate_tables import file_sha256
from ai_research_trends.ml.topic_final_validation import (
    open_set_metrics, select_rejection_threshold,
)


def _frame():
    return pd.DataFrame({
        "work_id": ["W1", "W2", "W3"], "version_group": ["G1", "G2", "G3"],
        "title": ["Alpha", "Beta", "Gamma"],
        "abstract": ["An alpha abstract", "A beta abstract", "A gamma abstract"],
        "publication_year": [2020, 2020, 2021],
        "primary_topic_id": ["T1", "T1", "T2"],
    })


def test_text_features_reject_missing_and_identity_leakage():
    frame = text_features(_frame())
    assert frame.loc[0, "text"] == "Alpha\nAn alpha abstract"
    with pytest.raises(ValueError, match="unusable"):
        text_features(_frame().assign(abstract=[None, "x", "y"]))
    bad = _frame()
    bad.loc[1, "version_group"] = "G1"
    with pytest.raises(ValueError, match="Duplicate"):
        text_features(bad)
    with pytest.raises(ValueError, match="required"):
        text_features(_frame().drop(columns="publication_year"))


def test_expansion_fraction_is_reproducible_and_stratified():
    expansion = pd.concat([_frame(), _frame().assign(
        work_id=["W4", "W5", "W6"], version_group=["G4", "G5", "G6"]
    )], ignore_index=True)
    a = stratified_expansion_fraction(expansion, 1 / 3)
    b = stratified_expansion_fraction(expansion, 1 / 3)
    pd.testing.assert_frame_equal(a, b)
    assert set(a.work_id).issubset(set(expansion.work_id))
    assert len(stratified_expansion_fraction(expansion, 0)) == 0
    assert len(stratified_expansion_fraction(expansion, 1)) == len(expansion)
    with pytest.raises(ValueError, match="Unsupported"):
        stratified_expansion_fraction(expansion, .5)


def test_paired_bootstrap_and_metric_denominator():
    truth = np.array(["a", "a", "b", "b"])
    good = truth.copy()
    poor = np.array(["a", "a", "a", "a"])
    assert metric_row(truth, good, ["a", "b"])["macro_f1"] == 1
    first = paired_bootstrap(truth, good, poor, ["a", "b"], 30)
    assert first == paired_bootstrap(truth, good, poor, ["a", "b"], 30)
    assert first["macro_f1_difference_95"][1] >= 0
    with pytest.raises(ValueError, match="differ"):
        paired_bootstrap(truth, good[:2], poor, ["a", "b"])


def test_calibration_threshold_and_open_set_denominators():
    score = np.array([.8, .7, .1, .2, .3])
    inside = np.array([True, True, False, False, False])
    threshold = select_rejection_threshold(score, inside, .2)
    assert (score[~inside] >= threshold).mean() <= .2
    truth = np.array(["a", "a", "OTHER", "OTHER", "OTHER"])
    pred = np.array(["a", "a", "a", "a", "a"])
    result = open_set_metrics(score, pred, truth, {"a"}, threshold)
    assert result["in_catalogue"] == 2
    assert result["outside_catalogue"] == 3
    assert bootstrap_open_set(score, pred, truth, {"a"}, threshold, 20) == (
        bootstrap_open_set(score, pred, truth, {"a"}, threshold, 20)
    )
    with pytest.raises(ValueError, match="both"):
        select_rejection_threshold(score[:2], inside[:2])


def test_open_set_score_methods_reject_unknown():
    with pytest.raises(ValueError, match="unknown"):
        score_predictions(object(), ["text"], "unknown", {"a"})


def test_champion_uses_predeclared_macro_f1_and_tie_break():
    closed = {"metrics": {f"expanded_{name}": {"macro_f1": score} for name, score in
              (("complement_nb", .7), ("logistic_regression", .875), ("linear_svm", .88))}}
    opened = {"methods": {name: {"evaluation": {"out_false_acceptance_rate": rate},
                              "inference_ms_per_work": 1.0} for name, rate in
              (("nb_probability", .1), ("lr_raw_probability", .15), ("svm_margin", .22))}}
    assert select_champion(closed, opened) == ("logistic_regression", "lr_raw_probability")
    closed["metrics"]["expanded_logistic_regression"]["macro_f1"] = .85
    assert select_champion(closed, opened) == ("linear_svm", "svm_margin")


def test_final_test_cannot_read_sealed_table(tmp_path: Path):
    frozen = tmp_path / "frozen.yaml"
    frozen.write_text("allow_final_test_execution: false\nhuman_review: pending\n")
    nonexistent_test = tmp_path / "missing_2025.parquet"
    with pytest.raises(PermissionError, match="does not authorize"):
        evaluate_once(tmp_path / "gate.json", tmp_path / "model", tmp_path / "web",
                      nonexistent_test, tmp_path / "catalogue.yaml", tmp_path / "reviews",
                      frozen, tmp_path / "output")
    assert not nonexistent_test.exists()
    assert not (tmp_path / "output").exists()
    with pytest.raises(PermissionError):
        verify_human_gate(tmp_path / "gate.json", tmp_path / "model",
                          tmp_path / "catalogue.yaml", tmp_path / "reviews", frozen)


def test_model_loader_rejects_corrupt_bundle_before_deserialization(tmp_path: Path):
    model_dir = tmp_path / "bundle"
    model_dir.mkdir()
    (model_dir / "frozen_config.json").write_text("{}")
    (model_dir / "manifest.json").write_text(json.dumps({
        "status": "complete", "final_2025_test": "SEALED",
        "files": {"frozen_config.json": {"sha256": "0" * 64}},
    }))
    with pytest.raises(ValueError, match="checksum mismatch"):
        TopicPlacementService(model_dir, tmp_path / "unread_web")


def test_diagnostic_groups_only_emit_aggregate_errors():
    frame = pd.DataFrame({"bucket": ["short", "short", "long"],
                          "correct": [True, False, False],
                          "work_id": ["private-1", "private-2", "private-3"]})
    result = summarize_groups(frame, "bucket")
    assert result == [
        {"group": "long", "n": 1, "errors": 1, "error_rate": 1.0},
        {"group": "short", "n": 2, "errors": 1, "error_rate": .5},
    ]
    assert "private-1" not in str(result)


def test_local_verified_runs_and_inference_when_available():
    """Integration smoke uses real local artifacts, but is optional on GitHub clones."""
    root = Path.cwd()
    integrated = root / "data/processed/ml_topic_classification/finalization_p2_20261101_v3"
    closed = root / "data/analysis/finalization_p3_models_20261101_v1"
    opened = root / "data/analysis/finalization_p3_open_set_20261101_v1"
    bundle = root / "models/finalization_p3/topic_placement_v2"
    web = root / "data/analysis/finalization_p2_web_data_20261101_v3"
    if not all(path.is_dir() for path in (integrated, closed, opened, bundle, web)):
        pytest.skip("Git-ignored local research artifacts unavailable")
    assert verify_experiment(closed, integrated)["valid"]
    assert verify_experiment(opened, integrated)["valid"]
    service = TopicPlacementService(bundle, web)
    sample = pd.read_parquet(integrated / "validation_2024.parquet", columns=[
        "title", "abstract", "selected_catalogue", "publication_year"
    ])
    assert sample.publication_year.eq(2024).all()
    for inside in (True, False):
        row = sample.loc[sample.selected_catalogue.eq(inside)].iloc[0]
        result = service.explore_research_draft(row.title, row.abstract)
        assert result["suggestion"]["requires_user_confirmation"] is True
        assert result["suggestion"]["automatic_placement"] is False
        assert result["data_scope"]["training_expansion"] == "not included in research landscape statistics"
    row = sample.iloc[0]
    chosen = service.config["classes"][0].rsplit("/", 1)[-1]
    manual = service.explore_research_draft(row.title, row.abstract, selected_topic_id=chosen)
    assert manual["selection_source"] == "manual"
    assert manual["topic_brief"] is not None
    with pytest.raises(ValueError, match="Abstract requires"):
        service.place_research_draft("Valid title", "short")
    with pytest.raises(KeyError):
        service.explore_research_draft(row.title, row.abstract, selected_topic_id="T999999999")


def test_published_development_figures_and_markdown_links():
    root = Path(__file__).resolve().parents[1]
    gallery = root / "reports/figures/finalization_p3"
    manifest = json.loads((gallery / "manifest.json").read_text())
    assert manifest["status"] == "complete"
    assert manifest["source_scope"].startswith("2024 development")
    assert len(manifest["files"]) >= 9
    for name, record in manifest["files"].items():
        path = gallery / name
        assert path.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
        assert path.stat().st_size == record["bytes"] and record["bytes"] > 1000
        assert file_sha256(path) == record["sha256"]
    for markdown in [root / "README.md", *root.glob("reports/FINALIZATION_P3_*.md")]:
        content = markdown.read_text()
        for relative in re.findall(r"\]\(([^)]+\.png)\)", content):
            assert (markdown.parent / relative).is_file(), f"Broken figure link: {markdown}: {relative}"


def test_local_aggregate_diagnostic_manifest_when_available():
    root = Path(__file__).resolve().parents[1]
    run = root / "data/analysis/finalization_p3_diagnostics_20261101_v3"
    if not run.is_dir():
        pytest.skip("Git-ignored development diagnostics unavailable")
    manifest = json.loads((run / "manifest.json").read_text())
    assert manifest["status"] == "complete"
    assert file_sha256(root / "src/ai_research_trends/ml/final_diagnostics.py") == manifest["code_sha256"]
    for name, entry in manifest["files"].items():
        assert file_sha256(run / name) == entry["sha256"]
    result = json.loads((run / "results.json").read_text())
    assert result["source_scope"].startswith("2024 original-sample")
    assert result["year_specific_limitation"].endswith("2025 is sealed")
    assert result["n"] == sum(row["n"] for row in result["margin_quartiles"])
    assert result["errors"] == sum(row["errors"] for row in result["margin_quartiles"])
