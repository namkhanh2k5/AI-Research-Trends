"""Read-only validation of RQ6 aggregate tables and published figures."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from ai_research_trends.preprocessing.validate_tables import file_sha256
from ai_research_trends.analysis.phase6_artifacts import resolve_historical_path


def verify(run_dir: Path, published_dir: Path|None=None) -> dict:
    if not run_dir.exists():
        run_dir = resolve_historical_path(run_dir / "manifest.json").parent
    manifest=json.loads((run_dir/"manifest.json").read_text())
    if manifest.get("status")!="complete" or "no 2025 labels" not in manifest.get("source_scope",""):
        raise ValueError("RQ6 run incomplete or test-label policy missing")
    for label,entry in manifest["inputs"].items():
        path=Path(entry["path"])
        if not path.is_file() or file_sha256(path)!=entry["sha256"]:
            raise ValueError(f"RQ6 source checksum mismatch: {label}")
    for name,entry in manifest["outputs"].items():
        path=run_dir/name
        if not path.is_file() or path.stat().st_size!=entry["bytes"] or file_sha256(path)!=entry["sha256"]:
            raise ValueError(f"RQ6 output checksum mismatch: {name}")
        if published_dir and file_sha256(published_dir/name)!=entry["sha256"]:
            raise ValueError(f"Published RQ6 artifact differs: {name}")
    support=pd.read_csv(run_dir/"topic_support.csv")
    if len(support)!=14 or support.topic_id.duplicated().any():
        raise ValueError("RQ6 selected-topic support incomplete")
    if published_dir:
        pub=json.loads((published_dir/"manifest.json").read_text())
        if pub["source_manifest_sha256"]!=file_sha256(run_dir/"manifest.json") or not pub["no_2025_label_distribution"]:
            raise ValueError("Published RQ6 manifest mismatches private run")
    return {"valid":True,"read_only":True,"topics":len(support),
            "csv_tables":sum(name.endswith(".csv") for name in manifest["outputs"]),
            "figures_png":sum(name.endswith(".png") for name in manifest["outputs"]),
            "published_match":published_dir is not None}


def main(argv: list[str]|None=None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir",type=Path)
    parser.add_argument("--published-dir",type=Path)
    args=parser.parse_args(argv)
    print(json.dumps(verify(args.run_dir,args.published_dir),indent=2))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
