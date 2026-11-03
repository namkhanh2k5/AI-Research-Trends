"""Read-only integrity and split-isolation validator for Phase 2 ML tables."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from ai_research_trends.ml.integrate_topic_data import validate_splits
from ai_research_trends.preprocessing.validate_tables import file_sha256


def verify_run(run_dir: Path, compare_dir: Path|None=None) -> dict:
    manifest_path=run_dir/"split_manifest.json"
    manifest=json.loads(manifest_path.read_text())
    if manifest.get("status")!="complete" or manifest.get("complete") is not True:
        raise ValueError("Phase 2 integration run incomplete")
    for label,entry in manifest["inputs"].items():
        path=Path(entry["path"])
        if not path.is_file() or file_sha256(path)!=entry["sha256"]:
            raise ValueError(f"Changed or missing Phase 2 input: {label}")
    for name,entry in manifest["outputs"].items():
        path=run_dir/name
        if not path.is_file() or path.stat().st_size!=entry["bytes"] or file_sha256(path)!=entry["sha256"]:
            raise ValueError(f"Phase 2 output integrity failure: {name}")
    reps=pd.read_parquet(run_dir/"ml_papers.parquet")
    audit=pd.read_parquet(run_dir/"source_record_audit.parquet")
    for frame in (reps,audit,pd.read_parquet(run_dir/"excluded.parquet")):
        locked=frame.loc[frame.split.eq("test")]
        if locked[["primary_topic_id","topic_score"]].notna().any().any():
            raise ValueError("Locked 2025 labels leaked into a general development table")
    checks=validate_splits(reps,audit)
    if checks!=manifest["validation"]:
        raise ValueError("Manifest validation diagnostics changed")
    for split,name in (("train","train"),("validation","validation_2024"),("test","test_2025_sealed")):
        frame=pd.read_parquet(run_dir/f"{name}.parquet",
                              columns=["work_id","version_group","split","dataset_origin"])
        expected=reps.loc[reps.usable_for_ml & reps.split.eq(split),["work_id","version_group"]]
        if set(frame.work_id)!=set(expected.work_id) or not frame.split.eq(split).all():
            raise ValueError(f"Model split differs from canonical representatives: {name}")
        if split!="train" and frame.dataset_origin.eq("targeted_ml_expansion").any():
            raise ValueError("Expansion contaminated a held-out split")
    groups=pd.read_parquet(run_dir/"version_groups.parquet")
    if len(groups)!=len(reps) or groups.version_group.duplicated().any():
        raise ValueError("Version-group inventory inconsistent")
    if len(audit)!=sum(manifest["input_rows"].values()):
        raise ValueError("Source audit lost input records")
    same=None
    if compare_dir:
        other=json.loads((compare_dir/"split_manifest.json").read_text())
        same={name:entry["sha256"]==other["outputs"].get(name,{}).get("sha256")
              for name,entry in manifest["outputs"].items()}
        if not all(same.values()): raise ValueError("Deterministic rerun output hashes differ")
    return {"valid":True,"read_only":True,"source_rows":len(audit),
            "canonical_groups":len(reps),"train":checks["eligible_training"],
            "validation_2024":checks["eligible_validation"],
            "test_2025_sealed_total_only":checks["sealed_test_total"],
            "output_files_verified":len(manifest["outputs"]),
            "deterministic_compare":same}


def main(argv: list[str]|None=None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir",type=Path)
    parser.add_argument("--compare-dir",type=Path)
    args=parser.parse_args(argv)
    print(json.dumps(verify_run(args.run_dir,args.compare_dir),indent=2))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
