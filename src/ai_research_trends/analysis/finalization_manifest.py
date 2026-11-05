"""Verify and bind the completed local Finalization Phase 2 runs."""

from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from ai_research_trends.analysis.topic_population import verify as verify_topic_population
from ai_research_trends.analysis.phase6_artifacts import resolve_historical_path
from ai_research_trends.analysis.validate_rq6 import verify as verify_rq6
from ai_research_trends.analysis.web_data import verify as verify_web
from ai_research_trends.ml.human_review_workflow import validate_package
from ai_research_trends.ml.validate_integrated_data import verify_run as verify_integrated
from ai_research_trends.preprocessing.validate_tables import file_sha256


def bind(integrated: Path, rerun: Path, rq6: Path, published: Path, human: Path,
         topic_population: Path, web: Path, output: Path) -> dict:
    if output.exists(): raise FileExistsError(output)
    checks={"integration":verify_integrated(integrated,rerun),
            "rq6":verify_rq6(rq6,published),"human_package":validate_package(human),
            "topic_population":verify_topic_population(topic_population),"web":verify_web(web)}
    inputs={name:{"path":str(path),"sha256":file_sha256(path)} for name,path in {
        "integrated":integrated/"split_manifest.json","integration_rerun":rerun/"split_manifest.json",
        "rq6":rq6/"manifest.json","rq6_published":published/"manifest.json",
        "human":human/"manifest.json","topic_population":topic_population/"manifest.json",
        "web":web/"manifest.json"}.items()}
    git_sha=subprocess.run(["git","rev-parse","HEAD"],capture_output=True,text=True,check=True).stdout.strip()
    code_paths=[Path("src/ai_research_trends/ml/integrate_topic_data.py"),
                Path("src/ai_research_trends/analysis/rq6_topic_labels.py"),
                Path("src/ai_research_trends/analysis/web_data.py"),
                Path("src/ai_research_trends/analysis/topic_population.py")]
    result={"status":"complete","complete":True,"run_id":output.stem,
        "created_at_utc":datetime.now(timezone.utc).isoformat(),
        "repository_head_at_run":git_sha,"code_sha256":{str(path):file_sha256(path) for path in code_paths},
        "source_collection_run_ids":json.loads((integrated/"split_manifest.json").read_text())["source_run_ids"],
        "run_manifests":inputs,"checks":checks,"source_rows":checks["integration"]["source_rows"],
        "training_rows":checks["integration"]["train"],
        "validation_2024_rows":checks["integration"]["validation_2024"],
        "sealed_2025_rows_count_only":checks["integration"]["test_2025_sealed_total_only"],
        "api_requests_new_topic_snapshot":checks["topic_population"]["queries"],
        "human_ratings_received":json.loads((human/"manifest.json").read_text())["ratings_received"],
        "non_destructive_processing":True,"phase3_4_source_outputs_unchanged":"verified by child manifests"}
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w",dir=output.parent,delete=False,prefix=".finalization_manifest_",suffix=".tmp") as handle:
        json.dump(result,handle,indent=2);handle.write("\n");temp=Path(handle.name)
    temp.replace(output)
    return result


def verify(path: Path) -> dict:
    manifest=json.loads(path.read_text())
    if manifest.get("status")!="complete" or not manifest.get("complete"):
        raise ValueError("Master run is incomplete")
    for name,entry in manifest["run_manifests"].items():
        if file_sha256(resolve_historical_path(entry["path"]))!=entry["sha256"]:
            raise ValueError(f"Child manifest changed: {name}")
    for path_str,digest in manifest["code_sha256"].items():
        if file_sha256(Path(path_str))!=digest:
            raise ValueError(f"Pipeline source changed: {path_str}")
    return {"valid":True,"child_manifests":len(manifest["run_manifests"]),
            "training_rows":manifest["training_rows"],"validation_2024_rows":manifest["validation_2024_rows"],
            "sealed_2025_rows_count_only":manifest["sealed_2025_rows_count_only"]}


def main(argv: list[str]|None=None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest="command",required=True)
    make=sub.add_parser("bind")
    make.add_argument("--integrated",type=Path,required=True)
    make.add_argument("--rerun",type=Path,required=True)
    make.add_argument("--rq6",type=Path,required=True)
    make.add_argument("--published",type=Path,default=Path("reports/finalization_p2"))
    make.add_argument("--human",type=Path,required=True)
    make.add_argument("--topic-population",type=Path,required=True)
    make.add_argument("--web",type=Path,required=True)
    make.add_argument("--output",type=Path,required=True)
    check=sub.add_parser("verify");check.add_argument("manifest",type=Path)
    args=parser.parse_args(argv)
    result=bind(args.integrated,args.rerun,args.rq6,args.published,args.human,args.topic_population,args.web,args.output) if args.command=="bind" else verify(args.manifest)
    print(json.dumps({"status":result.get("status","verified"),"training_rows":result["training_rows"],
                      "validation_2024_rows":result["validation_2024_rows"],
                      "sealed_2025_rows_count_only":result["sealed_2025_rows_count_only"]},indent=2));return 0


if __name__=="__main__": raise SystemExit(main())
