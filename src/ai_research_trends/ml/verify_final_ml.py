"""Read-only checksum and split-scope verification for Phase 3 ML runs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from ai_research_trends.ml.validate_integrated_data import verify_run as verify_integrated
from ai_research_trends.preprocessing.validate_tables import file_sha256


def verify_experiment(run_dir: Path,integrated: Path,
                      compare_dir: Path|None=None) -> dict:
    manifest=json.loads((run_dir/"manifest.json").read_text())
    if manifest.get("status")!="complete" or manifest.get("final_2025_test")!="SEALED":
        raise ValueError("Experiment incomplete or 2025 seal lost")
    verify_integrated(integrated)
    if file_sha256(integrated/"split_manifest.json")!=manifest["source_manifest_sha256"]:
        raise ValueError("Experiment source manifest changed")
    for name,entry in manifest["files"].items():
        path=run_dir/name
        if not path.is_file() or file_sha256(path)!=entry["sha256"] or path.stat().st_size!=entry["bytes"]:
            raise ValueError(f"Experiment artifact corrupt: {name}")
    result=json.loads((run_dir/"results.json").read_text())
    if result.get("final_2025_test")!="SEALED":raise ValueError("Results improperly claim final test")
    if "validation_predictions.parquet" in manifest["files"]:
        pred=pd.read_parquet(run_dir/"validation_predictions.parquet")
        valid=pd.read_parquet(integrated/"validation_2024.parquet",columns=["work_id","selected_catalogue"])
        expected=set(valid.loc[valid.selected_catalogue,"work_id"])
        if set(pred.work_id)!=expected or pred.work_id.duplicated().any():
            raise ValueError("Closed-set prediction universe changed")
    else:
        preds=list(run_dir.glob("*_predictions.parquet"))
        if not preds:raise ValueError("Open-set run lacks local prediction audit")
        keys=[set(pd.read_parquet(path,columns=["work_id"]).work_id) for path in preds]
        if any(key!=keys[0] for key in keys[1:]):
            raise ValueError("Open-set methods used different evaluation papers")
        if result["evaluation_rows"]!=len(keys[0]):raise ValueError("Open-set denominator differs")
    comparison=None
    if compare_dir is not None:
        other=json.loads((compare_dir/"results.json").read_text())
        keys=("metrics","ablation","learning_curve","feature_ablation","per_class")
        comparison={key:result[key]==other[key] for key in keys if key in result}
        if not comparison or not all(comparison.values()):
            raise ValueError("Rerun metrics differ")
    return {"valid":True,"files_verified":len(manifest["files"]),
            "final_2025_test":"SEALED","deterministic_metrics":comparison}


def main(argv: list[str]|None=None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir",type=Path)
    parser.add_argument("--integrated",type=Path,default=Path("data/processed/ml_topic_classification/finalization_p2_20261101_v3"))
    parser.add_argument("--compare-dir",type=Path)
    args=parser.parse_args(argv)
    print(json.dumps(verify_experiment(args.run_dir,args.integrated,args.compare_dir),indent=2));return 0


if __name__=="__main__":raise SystemExit(main())
