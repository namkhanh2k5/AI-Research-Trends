"""Publish only small, non-identifying Phase 1 aggregate audit artifacts."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import pandas as pd
import yaml

from ai_research_trends.analysis.label_drift import verify_drift_evidence
from ai_research_trends.crawling.verify_ml_expansion import verify
from ai_research_trends.preprocessing.validate_tables import file_sha256


def publish(gap_dir: Path, drift_dir: Path, plan_path: Path,
            collection_manifest: Path, quality_dir: Path, output_dir: Path,
            catalogue_path: Path) -> dict:
    if output_dir.exists(): raise FileExistsError("Published aggregate directory already exists")
    collection=verify(collection_manifest)
    drift=verify_drift_evidence(drift_dir/"manifest.json")
    gap_manifest=json.loads((gap_dir/"manifest.json").read_text())
    if file_sha256(gap_dir/"data_gap.csv")!=gap_manifest["data_gap_sha256"]:
        raise ValueError("Gap audit checksum changed")
    quality=json.loads((quality_dir/"manifest.json").read_text())
    if quality["status"]!="complete" or quality["source_manifest_sha256"]!=file_sha256(collection_manifest):
        raise ValueError("Quality audit and collection provenance differ")
    for name,detail in quality["outputs"].items():
        if file_sha256(quality_dir/name)!=detail["sha256"]: raise ValueError(f"Quality checksum changed: {name}")
    plan=json.loads(plan_path.read_text())
    catalogue=yaml.safe_load(catalogue_path.read_text())
    metadata=pd.read_csv(catalogue["source_metadata_csv"])
    output_dir.mkdir(parents=True,exist_ok=False)
    files={}

    def save_table(name: str, frame: pd.DataFrame) -> None:
        path=output_dir/name;frame.to_csv(path,index=False)
        files[name]={"rows":len(frame),"sha256":file_sha256(path),"bytes":path.stat().st_size}

    def copy_aggregate(source: Path, name: str) -> None:
        shutil.copyfile(source,output_dir/name)
        path=output_dir/name
        files[name]={"sha256":file_sha256(path),"bytes":path.stat().st_size}

    copy_aggregate(gap_dir/"data_gap.csv","data_gap.csv")
    for name in ("topic_support.csv","by_year.csv","by_type.csv","by_language.csv"):
        copy_aggregate(quality_dir/name,name)
    copy_aggregate(drift_dir/"summary.json","label_drift_summary.json")
    copy_aggregate(drift_dir/"transitions.csv","label_drift_transitions.csv")
    strata=pd.DataFrame(plan["strata"])
    save_table("collection_quotas_by_topic_year.csv",strata[[
        "source_group","topic_id","year","source_population_count","planned_records",
        "seed","expected_pages"]].sort_values(["source_group","topic_id","year"],na_position="last"))
    save_table("collection_quotas_by_year.csv",strata.groupby("year",as_index=False).agg(
        planned_records=("planned_records","sum"),planned_pages=("expected_pages","sum")))
    local=pd.read_csv(quality_dir/"record_audit.csv")
    save_table("source_group_yield.csv",local.groupby("source_group",as_index=False).agg(
        acquired=("work_id","size"),eligible=("ml_training_eligible","sum"),
        selected_labels=("is_selected","sum")))
    save_table("text_quality.csv",local.groupby("text_quality_status",as_index=False).agg(
        records=("work_id","size")))
    review=metadata.loc[metadata.short_id.isin(catalogue["catalogue_b"]),[
        "short_id","name","description","subfield_id"]].copy()
    review["provisional_scope_reason"]=review.short_id.map(
        {key:value["reason"] for key,value in catalogue["scope_review"].items()})
    review["neighbor_overlap"]=review.short_id.map(
        {key:value["overlap"] for key,value in catalogue["scope_review"].items()})
    support=pd.read_csv(quality_dir/"topic_support.csv").set_index("topic_id")
    review["original_usable_examples"]=review.short_id.map(support.original_usable_train)
    review["new_usable_examples"]=review.short_id.map(support.newly_usable_train)
    review["independent_human_review_required"]=True
    review["independent_human_approval"]="pending"
    save_table("human_topic_review_queue.csv",review.sort_values("short_id"))
    manifest={"status":"complete","purpose":"small GitHub-reviewable aggregates only",
              "no_record_level_abstracts_or_heldout_labels":True,
              "source_gap_manifest_sha256":file_sha256(gap_dir/"manifest.json"),
              "source_drift_manifest_sha256":file_sha256(drift_dir/"manifest.json"),
              "source_plan_sha256":file_sha256(plan_path),
              "source_collection_manifest_sha256":file_sha256(collection_manifest),
              "source_quality_manifest_sha256":file_sha256(quality_dir/"manifest.json"),
              "verified_raw_records":collection["raw_records"],
              "verified_drift_responses":drift["verified_responses"],
              "files":files}
    (output_dir/"reproducibility_manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
    return manifest


def main(argv: list[str]|None=None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gap-dir",type=Path,required=True)
    parser.add_argument("--drift-dir",type=Path,required=True)
    parser.add_argument("--plan",type=Path,required=True)
    parser.add_argument("--collection-manifest",type=Path,required=True)
    parser.add_argument("--quality-dir",type=Path,required=True)
    parser.add_argument("--output-dir",type=Path,required=True)
    parser.add_argument("--catalogue",type=Path,default=Path("config/phase6b_catalogue.yaml"))
    args=parser.parse_args(argv)
    result=publish(args.gap_dir,args.drift_dir,args.plan,args.collection_manifest,
                   args.quality_dir,args.output_dir,args.catalogue)
    print(json.dumps({"status":result["status"],"files":len(result["files"]),
                      "verified_raw_records":result["verified_raw_records"]},indent=2))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
