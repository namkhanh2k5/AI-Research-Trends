"""Offline regressions for the single-use, amendment-authorized 2025 test gate."""

import json
from pathlib import Path

import joblib
import pandas as pd
import pytest
import yaml
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC

from ai_research_trends.ml import final_test_gate
from ai_research_trends.preprocessing.validate_tables import file_sha256

CLASSES = ["https://openalex.org/T1", "https://openalex.org/T2", "https://openalex.org/T3"]
THRESHOLD = -0.5
WORDS = {"https://openalex.org/T1": "image segmentation pixels convolution",
         "https://openalex.org/T2": "translation language tokens grammar",
         "https://openalex.org/T3": "graph nodes edges message passing",
         "https://openalex.org/T9": "robot arm torque motor"}


class FakeService:
    def __init__(self, model_dir: Path, web_dir: Path):
        self.config = {"threshold": THRESHOLD, "classes": CLASSES, "score_method": "svm_margin",
                       "model_version": "fake_v1"}
        self.model = joblib.load(model_dir / "model.joblib")


def _rows(year: int = 2025) -> pd.DataFrame:
    rows = []
    for index in range(24):
        topic = list(WORDS)[index % 4]
        rows.append({"work_id": f"W{index}", "version_group": f"G{index}", "title": f"Study {index}",
                     "abstract": f"{WORDS[topic]} experiment number {index}", "publication_year": year,
                     "dataset_origin": "original_analytical_sample", "primary_topic_id": topic})
    return pd.DataFrame(rows)


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setattr(final_test_gate, "TopicPlacementService", FakeService)
    monkeypatch.setattr(final_test_gate, "verify_run", lambda path: {"valid": True})
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    model = Pipeline([("tfidf", TfidfVectorizer()), ("model", LinearSVC(random_state=0))])
    model.fit([WORDS[topic] for topic in CLASSES] * 3, CLASSES * 3)
    joblib.dump(model, model_dir / "model.joblib")
    integrated = tmp_path / "integrated"
    integrated.mkdir()
    test_path = integrated / "test_2025_sealed.parquet"
    _rows().to_parquet(test_path, index=False)
    (integrated / "split_manifest.json").write_text(json.dumps(
        {"outputs": {"test_2025_sealed.parquet": {"sha256": file_sha256(test_path)}}}))
    (model_dir / "manifest.json").write_text(json.dumps({"source_paths": {"integrated": str(integrated)}}))
    frozen = tmp_path / "frozen.yaml"
    frozen.write_text(yaml.safe_dump({
        "model_manifest_sha256": file_sha256(model_dir / "manifest.json"),
        "model_binary_sha256": file_sha256(model_dir / "model.joblib"),
        "integrated_manifest_sha256": file_sha256(integrated / "split_manifest.json"),
        "rejection_threshold": THRESHOLD, "class_order": CLASSES, "allow_final_test_execution": False}))
    amendment = tmp_path / "amendment.yaml"
    amendment.write_text(yaml.safe_dump({
        "status": "approved", "allow_final_test_execution": True, "amends_sha256": file_sha256(frozen),
        "model_manifest_sha256": file_sha256(model_dir / "manifest.json"),
        "model_binary_sha256": file_sha256(model_dir / "model.joblib")}))
    return {"amendment": amendment, "model": model_dir, "test": test_path, "frozen": frozen,
            "registry": tmp_path / "registry.json", "tmp": tmp_path}


def _run(s, output="run_v1"):
    return final_test_gate.evaluate_once(s["amendment"], s["model"], s["tmp"], s["test"], s["frozen"],
                                         s["tmp"] / output, s["registry"])


def test_gate_refuses_without_approved_amendment(setup):
    setup["amendment"].unlink()
    with pytest.raises(PermissionError, match="No approved amendment"):
        _run(setup)
    assert not setup["registry"].exists() and not (setup["tmp"] / "run_v1").exists()


def test_gate_rejects_changed_frozen_protocol(setup):
    setup["frozen"].write_text(setup["frozen"].read_text() + "edited: true\n")
    with pytest.raises(ValueError, match="Frozen protocol changed"):
        _run(setup)
    assert not setup["registry"].exists()


def test_label_free_preflight_failure_does_not_consume_registry(setup):
    _rows(year=2024).to_parquet(setup["test"], index=False)
    manifest = setup["test"].parent / "split_manifest.json"
    manifest.write_text(json.dumps({"outputs": {"test_2025_sealed.parquet": {"sha256": file_sha256(setup["test"])}}}))
    frozen = yaml.safe_load(setup["frozen"].read_text())
    frozen["integrated_manifest_sha256"] = file_sha256(manifest)
    setup["frozen"].write_text(yaml.safe_dump(frozen))
    amendment = yaml.safe_load(setup["amendment"].read_text())
    amendment["amends_sha256"] = file_sha256(setup["frozen"])
    setup["amendment"].write_text(yaml.safe_dump(amendment))
    with pytest.raises(ValueError, match="year mismatch"):
        _run(setup)
    assert not setup["registry"].exists()


def test_single_run_writes_results_and_blocks_any_second_run(setup):
    result = _run(setup)
    output = setup["tmp"] / "run_v1"
    assert result["status"] == "complete" and result["test_rows"] == 24
    assert result["closed_set"]["n"] == 18 and result["open_set"]["outside_catalogue"] == 6
    assert len(result["closed_set"]["macro_f1_bootstrap_95"]) == 2
    assert {"in_acceptance_rate", "out_false_acceptance_rate", "auroc_in_vs_out",
            "end_to_end_correct_placement", "bootstrap_95"} <= set(result["open_set"])
    for name, digest in result["files_sha256"].items():
        assert file_sha256(output / name) == digest
    assert pd.read_csv(output / "per_class.csv").topic_id.tolist() == CLASSES
    receipt = json.loads(setup["registry"].read_text())
    assert receipt["status"] == "complete" and receipt["result_sha256"] == file_sha256(output / "result.json")
    with pytest.raises(FileExistsError, match="never overwrite"):
        _run(setup)
    with pytest.raises(FileExistsError, match="registry"):
        _run(setup, output="run_v2")
    assert not (setup["tmp"] / "run_v2").exists()
