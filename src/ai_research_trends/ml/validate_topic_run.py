"""Read-only checksum and gate verification for a completed Phase 6B run."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ai_research_trends.preprocessing.validate_tables import file_sha256


def verify_run(run_dir: Path) -> dict:
    manifest_path=run_dir/"manifest.json"
    manifest=json.loads(manifest_path.read_text())
    if manifest.get("status")!="complete": raise ValueError("Run is incomplete")
    if manifest.get("test_2025")!="sealed_not_evaluated":
        raise ValueError("Unexpected 2025 test status in development run")
    if not manifest.get("outputs"): raise ValueError("No hashed outputs in manifest")
    for name,entry in manifest["outputs"].items():
        path=run_dir/Path(entry["path"]).name
        if not path.is_file() or file_sha256(path)!=entry["sha256"] or path.stat().st_size!=entry["bytes"]:
            raise ValueError(f"Missing or changed output: {name}")
    if manifest["catalogues"]["B"]["validation_rows"]>manifest["validation_eligible"]:
        raise ValueError("Invalid validation denominator")
    if manifest["open_set"]["svm_max_decision"]["evaluation"]["total"]>manifest["validation_eligible"]:
        raise ValueError("Invalid open-set denominator")
    return {"status":"PASS","outputs_verified":len(manifest["outputs"]),
            "manifest_sha256":file_sha256(manifest_path),
            "test_2025":manifest["test_2025"],
            "validation_eligible":manifest["validation_eligible"]}


def public_summary(run_dir: Path) -> dict:
    """Extract only aggregate, reviewer-safe measurements from a verified run."""
    verification=verify_run(run_dir)
    manifest=json.loads((run_dir/"manifest.json").read_text())
    return {"run_manifest_sha256":verification["manifest_sha256"],
            "outputs_verified":verification["outputs_verified"],
            "source_manifest_sha256":manifest["source_manifest_sha256"],
            "source_work_sha256":manifest["source_work_sha256"],
            "source_topic_sha256":manifest["source_topic_sha256"],
            "catalogue_sha256":manifest["catalogue_sha256"],
            "metadata_sha256":manifest["metadata_sha256"],
            "development_works":manifest["development_works"],
            "eligible_development":manifest["eligible_development"],
            "train_eligible":manifest["train_eligible"],
            "validation_eligible":manifest["validation_eligible"],
            "duplicate_audit":manifest["duplicate_audit"],
            "near_duplicate_sensitivity":manifest["near_duplicate_sensitivity"],
            "catalogues":manifest["catalogues"],"open_set":manifest["open_set"],
            "human_semantic_validation":manifest["human_semantic_validation"],
            "test_2025":manifest["test_2025"]}


def main(argv: list[str]|None=None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir",type=Path,required=True)
    parser.add_argument("--summary-output",type=Path,
                        help="Optionally write a small aggregate-only JSON; refuses overwrite")
    args=parser.parse_args(argv)
    result=verify_run(args.run_dir)
    if args.summary_output:
        if args.summary_output.exists(): parser.error("Summary output already exists")
        args.summary_output.write_text(json.dumps(public_summary(args.run_dir),indent=2)+"\n")
    print(json.dumps(result,indent=2))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
