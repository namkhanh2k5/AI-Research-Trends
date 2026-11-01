"""Aggregate-only diagnostics of frozen 2024 silver-label predictions."""

from __future__ import annotations

import argparse
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from ai_research_trends.ml.final_experiments import INTEGRATED, paired_bootstrap, text_features
from ai_research_trends.ml.verify_final_ml import verify_experiment
from ai_research_trends.preprocessing.validate_tables import file_sha256


def summarize_groups(frame: pd.DataFrame, column: str) -> list[dict]:
    """Count errors within disjoint groups without emitting work IDs or text."""
    rows = []
    for label, group in frame.groupby(column, dropna=False, sort=True, observed=True):
        rows.append({"group": str(label), "n": len(group),
                     "errors": int((~group.correct).sum()),
                     "error_rate": float((~group.correct).mean())})
    return rows


def analyze(integrated: Path, closed_dir: Path, topic_table: Path,
            output_dir: Path) -> dict:
    if output_dir.exists():
        raise FileExistsError(output_dir)
    verify_experiment(closed_dir, integrated)
    closed = json.loads((closed_dir / "results.json").read_text())
    if closed.get("final_2025_test") != "SEALED":
        raise ValueError("Diagnostic source opened the final test")
    classes = closed["classes"]
    prediction = pd.read_parquet(closed_dir / "validation_predictions.parquet")
    valid = pd.read_parquet(integrated / "validation_2024.parquet")
    valid = valid.loc[valid.primary_topic_id.isin(classes)]
    frame = prediction.merge(valid, on="work_id", validate="one_to_one", suffixes=("", "_source"))
    if len(frame) != len(prediction) or not frame.publication_year.eq(2024).all():
        raise ValueError("2024 diagnostic universe changed")
    if not frame.dataset_origin.eq("original_analytical_sample").all():
        raise ValueError("Targeted expansion entered diagnostic validation")
    if not frame.true_topic.eq(frame.primary_topic_id).all():
        raise ValueError("Prediction labels do not match source silver labels")
    frame = text_features(frame)
    model = joblib.load(closed_dir / "models/expanded_linear_svm.joblib")
    predicted = model.predict(frame.text.tolist())
    if not np.array_equal(predicted, frame.pred_expanded_linear_svm.to_numpy()):
        raise ValueError("Frozen model disagrees with stored development predictions")
    scores = np.asarray(model.decision_function(frame.text.tolist()))
    frame["max_margin"] = scores.max(axis=1)
    frame["correct"] = frame.pred_expanded_linear_svm.eq(frame.true_topic)
    frame["margin_quartile"] = pd.qcut(frame.max_margin, 4, labels=["Q1_low", "Q2", "Q3", "Q4_high"])
    frame["abstract_words"] = frame.abstract_clean.str.split().str.len()
    frame["abstract_length_quartile"] = pd.qcut(
        frame.abstract_words.rank(method="first"), 4,
        labels=["Q1_short", "Q2", "Q3", "Q4_long"]
    )
    frame["language_group"] = frame.language.fillna("<missing>").where(
        frame.language.fillna("<missing>").eq("en"), "other_or_missing"
    )
    topics = pd.read_parquet(topic_table, columns=["work_id", "topic_id", "topic_rank"])
    if topics.duplicated(["work_id", "topic_id"]).any():
        raise ValueError("Topic relationship table has duplicate keys")
    secondary = set(map(tuple, topics.loc[topics.topic_rank.gt(1), ["work_id", "topic_id"]].itertuples(index=False, name=None)))
    errors = frame.loc[~frame.correct].copy()
    errors["prediction_is_secondary"] = [
        (work_id, topic_id) in secondary for work_id, topic_id in
        errors[["work_id", "pred_expanded_linear_svm"]].itertuples(index=False, name=None)
    ]
    changed = {
        "original_wrong_expanded_right": int((frame.pred_original_only_linear_svm.ne(frame.true_topic) & frame.correct).sum()),
        "original_right_expanded_wrong": int((frame.pred_original_only_linear_svm.eq(frame.true_topic) & ~frame.correct).sum()),
        "both_wrong": int((frame.pred_original_only_linear_svm.ne(frame.true_topic) & ~frame.correct).sum()),
    }
    y = frame.true_topic.to_numpy()
    comparisons = {
        name: paired_bootstrap(y, frame.pred_expanded_linear_svm.to_numpy(),
                               frame[f"pred_expanded_{name}"].to_numpy(), classes)
        for name in ("logistic_regression", "complement_nb")
    }
    confusion = (errors.groupby(["true_topic", "pred_expanded_linear_svm"])
                 .size().sort_values(ascending=False).head(12))
    table = pd.DataFrame([{"true_topic": a, "predicted_topic": b, "errors": int(count)}
                          for (a, b), count in confusion.items()])
    result = {
        "status": "complete", "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_scope": "2024 original-sample in-catalogue development only; 2025 sealed",
        "code_sha256": file_sha256(Path(__file__)),
        "n": len(frame), "errors": len(errors),
        "overall_error_rate": float((~frame.correct).mean()),
        "margin_quartiles": summarize_groups(frame, "margin_quartile"),
        "abstract_length_quartiles": summarize_groups(frame, "abstract_length_quartile"),
        "work_type": summarize_groups(frame, "work_type"),
        "language_group": summarize_groups(frame, "language_group"),
        "predicted_topic_as_secondary_among_errors": int(errors.prediction_is_secondary.sum()),
        "errors_with_secondary_information": int(errors.work_id.isin(topics.work_id).sum()),
        "changed_vs_original_svm": changed,
        "paired_model_comparisons": comparisons,
        "year_specific_limitation": "Only 2024 was evaluated; 2025 is sealed",
        "source_sha256": {
            "closed_manifest": file_sha256(closed_dir / "manifest.json"),
            "integrated_manifest": file_sha256(integrated / "split_manifest.json"),
            "topic_relationships": file_sha256(topic_table),
        },
    }
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".final_diag_stage_", dir=output_dir.parent) as temp:
        stage = Path(temp)
        (stage / "results.json").write_text(json.dumps(result, indent=2) + "\n")
        table.to_csv(stage / "top_confusions.csv", index=False)
        manifest = {"status": "complete", "source_sha256": result["source_sha256"],
                    "code_sha256": result["code_sha256"],
                    "files": {p.name: {"sha256": file_sha256(p), "bytes": p.stat().st_size}
                              for p in stage.iterdir() if p.is_file()}}
        (stage / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        stage.replace(output_dir)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--integrated", type=Path, default=INTEGRATED)
    parser.add_argument("--closed-run", type=Path, required=True)
    parser.add_argument("--topic-table", type=Path, default=Path(
        "data/processed/openalex_stratified/stratified_20261019T155909Z/work_topics.parquet"))
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    result = analyze(args.integrated, args.closed_run, args.topic_table, args.output_dir)
    print(json.dumps({key: result[key] for key in ("status", "n", "errors", "source_scope")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
