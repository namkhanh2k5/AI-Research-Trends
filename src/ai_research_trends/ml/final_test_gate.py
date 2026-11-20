"""Single-use 2025 temporal hold-out test of the frozen topic-placement model.

The frozen protocol kept 2025 sealed until two human raters signed off. That
review was withdrawn by a recorded amendment; model, threshold, classes and
metrics are unchanged. A project-level registry receipt blocks a second run.
"""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import yaml
from sklearn.metrics import confusion_matrix, f1_score, precision_recall_fscore_support

from ai_research_trends.ml.final_experiments import SEED, metric_row, text_features
from ai_research_trends.ml.final_inference import TopicPlacementService
from ai_research_trends.ml.final_open_set import bootstrap_open_set, score_predictions
from ai_research_trends.ml.topic_final_validation import open_set_metrics
from ai_research_trends.ml.topic_pilot import clean_text
from ai_research_trends.ml.validate_integrated_data import verify_run
from ai_research_trends.preprocessing.validate_tables import file_sha256

AMENDMENT = Path("config/final_test_2025_amendment.yaml")
FROZEN_PROTOCOL = Path("config/finalization_p3_frozen_evaluation.yaml")
REGISTRY = Path("data/analysis/finalization_p3_final_test_registry.json")
LABEL_FREE_COLUMNS = ["work_id", "version_group", "title", "abstract", "publication_year", "dataset_origin"]


def verify_authorization(amendment_path: Path, frozen_protocol: Path, model_dir: Path) -> dict:
    """Check the approved amendment and frozen hashes before *any* test-table read."""
    amendment = yaml.safe_load(amendment_path.read_text()) if amendment_path.is_file() else {}
    if amendment.get("status") != "approved" or amendment.get("allow_final_test_execution") is not True:
        raise PermissionError("No approved amendment authorizes opening the 2025 final test")
    if amendment.get("amends_sha256") != file_sha256(frozen_protocol):
        raise ValueError("Frozen protocol changed after the amendment")
    frozen = yaml.safe_load(frozen_protocol.read_text())
    for key, path in (("model_manifest_sha256", model_dir / "manifest.json"),
                      ("model_binary_sha256", model_dir / "model.joblib")):
        if not (frozen.get(key) == amendment.get(key) == file_sha256(path)):
            raise ValueError(f"Model differs from the frozen protocol: {key}")
    return {"amendment_sha256": file_sha256(amendment_path),
            "frozen_protocol_sha256": amendment["amends_sha256"], "frozen": frozen}


def preflight(test_path: Path) -> int:
    """Validate the 2025 table using label-free columns only."""
    if "primary_topic_id" not in pq.read_schema(test_path).names:
        raise ValueError("2025 table lacks the label column")
    frame = pd.read_parquet(test_path, columns=LABEL_FREE_COLUMNS)
    if frame.empty or not frame.publication_year.eq(2025).all():
        raise ValueError("Final-test year mismatch")
    if frame.dataset_origin.ne("original_analytical_sample").any():
        raise ValueError("Targeted expansion entered the 2025 test")
    if frame.work_id.duplicated().any() or frame.version_group.duplicated().any():
        raise ValueError("Duplicate work or version group in the 2025 test")
    if frame.title.map(clean_text).eq("").any() or frame.abstract.map(clean_text).eq("").any():
        raise ValueError("2025 test contains unusable title or abstract")
    return len(frame)


def macro_f1_interval(truth: np.ndarray, pred: np.ndarray, classes: list[str], draws: int = 500) -> list[float]:
    rng = np.random.default_rng(SEED)
    values = []
    for _ in range(draws):
        ix = rng.integers(0, len(truth), len(truth))
        values.append(f1_score(truth[ix], pred[ix], labels=classes, average="macro", zero_division=0))
    return [float(x) for x in np.quantile(values, [.025, .975])]


def compute_metrics(score: np.ndarray, pred: np.ndarray, truth: np.ndarray,
                    classes: list[str], threshold: float) -> tuple[dict, pd.DataFrame, pd.DataFrame]:
    selected = set(classes)
    within = np.isin(truth, classes)
    closed = metric_row(truth[within], pred[within], classes)
    closed["macro_f1_bootstrap_95"] = macro_f1_interval(truth[within], pred[within], classes)
    precision, recall, f1, support = precision_recall_fscore_support(
        truth[within], pred[within], labels=classes, zero_division=0)
    per_class = pd.DataFrame({"topic_id": classes, "support": support.astype(int),
                              "precision": precision, "recall": recall, "f1": f1})
    confusion = pd.DataFrame(confusion_matrix(truth[within], pred[within], labels=classes),
                             index=classes, columns=classes)
    opened = open_set_metrics(score, pred, truth, selected, threshold)
    accepted = score >= threshold
    opened["accepted_correct_precision_all"] = float(opened["correct_accepted_in"] / max(1, int(accepted.sum())))
    opened["overall_acceptance_rate"] = float(accepted.mean())
    opened["bootstrap_95"] = bootstrap_open_set(score, pred, truth, selected, threshold)
    return {"closed_set": closed, "open_set": opened}, per_class, confusion


def _write_json(path: Path, payload: dict) -> None:
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, prefix=".final_test_receipt_",
                                     delete=False) as stream:
        json.dump(payload, stream, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
        temporary = Path(stream.name)
    temporary.replace(path)


def evaluate_once(amendment_path: Path, model_dir: Path, web_dir: Path, test_path: Path,
                  frozen_protocol: Path, output_dir: Path, registry_path: Path | None = None) -> dict:
    if output_dir.exists():
        raise FileExistsError("Final test already has this output; never overwrite")
    auth = verify_authorization(amendment_path, frozen_protocol, model_dir)
    registry_path = registry_path or REGISTRY
    if registry_path.exists():
        raise FileExistsError("Project-level final-test registry already exists; manual audit required")
    # Every check that does not need labels runs before the registry receipt,
    # so a configuration error cannot consume the single permitted attempt.
    service = TopicPlacementService(model_dir, web_dir)
    threshold = float(service.config["threshold"])
    if threshold != float(auth["frozen"]["rejection_threshold"]):
        raise ValueError("Model threshold differs from the frozen protocol")
    if service.config["classes"] != auth["frozen"]["class_order"]:
        raise ValueError("Model classes differ from the frozen protocol")
    integrated = Path(json.loads((model_dir / "manifest.json").read_text())["source_paths"]["integrated"])
    if file_sha256(integrated / "split_manifest.json") != auth["frozen"]["integrated_manifest_sha256"]:
        raise ValueError("Integrated dataset differs from the frozen protocol")
    verify_run(integrated)
    expected = json.loads((integrated / "split_manifest.json").read_text())["outputs"]["test_2025_sealed.parquet"]["sha256"]
    if file_sha256(test_path) != expected:
        raise ValueError("2025 test checksum changed")
    rows = preflight(test_path)
    attempt = {"status": "attempt_started", "started_at_utc": datetime.now(timezone.utc).isoformat(),
               "amendment_sha256": auth["amendment_sha256"],
               "frozen_protocol_sha256": auth["frozen_protocol_sha256"],
               "model_manifest_sha256": file_sha256(model_dir / "manifest.json"),
               "test_sha256": expected, "test_rows": rows, "output_dir": str(output_dir)}
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(registry_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise FileExistsError("Project-level final-test registry already exists; manual audit required") from exc
    with os.fdopen(fd, "w") as stream:
        json.dump(attempt, stream, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    # Labels are read only after the attempt is recorded. A failed attempt keeps its receipt.
    test = text_features(pd.read_parquet(test_path))
    classes = service.config["classes"]
    score, pred = score_predictions(service.model, test.text.tolist(), service.config["score_method"], set(classes))
    truth = test.primary_topic_id.to_numpy()
    metrics, per_class, confusion = compute_metrics(score, pred, truth, classes, threshold)
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".final_test_stage_", dir=output_dir.parent) as temp:
        stage = Path(temp)
        pd.DataFrame({"work_id": test.work_id, "true_topic": truth, "predicted_topic": pred,
                      "score": score, "accepted": score >= threshold}).to_parquet(stage / "predictions.parquet", index=False)
        per_class.to_csv(stage / "per_class.csv", index=False)
        confusion.to_csv(stage / "confusion.csv")
        result = {"status": "complete", "evaluated_once_at_utc": datetime.now(timezone.utc).isoformat(),
                  "model_version": service.config["model_version"], "score_method": service.config["score_method"],
                  "threshold": threshold, "test_sha256": expected, "test_rows": len(test),
                  "amendment_sha256": auth["amendment_sha256"],
                  "frozen_protocol_sha256": auth["frozen_protocol_sha256"],
                  "label_source": "OpenAlex primary-topic silver labels; not human semantic truth",
                  **metrics,
                  "files_sha256": {name: file_sha256(stage / name) for name in
                                   ("predictions.parquet", "per_class.csv", "confusion.csv")}}
        (stage / "result.json").write_text(json.dumps(result, indent=2) + "\n")
        stage.replace(output_dir)
    _write_json(registry_path, {**attempt, "status": "complete",
                                "completed_at_utc": result["evaluated_once_at_utc"],
                                "result_sha256": file_sha256(output_dir / "result.json")})
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute-once", action="store_true", required=True)
    parser.add_argument("--amendment", type=Path, default=AMENDMENT)
    parser.add_argument("--frozen-protocol", type=Path, default=FROZEN_PROTOCOL)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--web-dir", type=Path, required=True)
    parser.add_argument("--test-path", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--registry", type=Path, default=REGISTRY)
    args = parser.parse_args(argv)
    result = evaluate_once(args.amendment, args.model_dir, args.web_dir, args.test_path,
                           args.frozen_protocol, args.output_dir, args.registry)
    print(json.dumps({"status": result["status"], "closed_set": result["closed_set"],
                      "open_set": {k: v for k, v in result["open_set"].items() if k != "bootstrap_95"}}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
