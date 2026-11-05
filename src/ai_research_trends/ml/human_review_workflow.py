"""Prepare, validate and later analyze genuinely independent blind human reviews."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import pandas as pd
import yaml
from sklearn.metrics import cohen_kappa_score

from ai_research_trends.analysis.rq6_topic_labels import wilson_interval
from ai_research_trends.preprocessing.validate_tables import file_sha256


RESPONSE_COLUMNS={"example_id","best_topic","second_plausible_topic","reviewer_note"}
SCOPE_COLUMNS={"reviewer_id","topic_id","scope_judgment","clarity_judgment",
               "overlap_notes","recommended_action","reviewer_explanation"}
SPECIAL={"NONE","UNCLEAR"}


def validate_blind_sheet(frame: pd.DataFrame, allowed: set[str]) -> dict:
    required={"example_id","title","abstract","randomized_topic_options"}|RESPONSE_COLUMNS
    if not required.issubset(frame.columns): raise ValueError("Blind sheet lacks response or paper fields")
    if any("openalex" in str(col).lower() or "prediction" in str(col).lower() for col in frame.columns):
        raise ValueError("Blind sheet leaks source labels or model predictions")
    if frame.example_id.duplicated().any() or frame.example_id.isna().any():
        raise ValueError("Blind example IDs must be unique")
    if frame[["best_topic","second_plausible_topic"]].notna().any().any():
        raise ValueError("Blind sheet already contains topic answers")
    orders=[]
    for value in frame.randomized_topic_options:
        # The frozen Phase 6B sheet stores human-readable options separated by
        # pipes, not a JSON array. Inspect only the displayed topic identifiers.
        options=[part.strip().split(" — ",1)[0] for part in str(value).split(" | ")]
        if len(options)!=len(allowed) or set(options)!=allowed:
            raise ValueError("Randomized options differ from frozen catalogue")
        orders.append(tuple(options))
    if len(set(orders))<2: raise ValueError("Topic option order is not varied")
    return {"valid":True,"examples":len(frame),"options":len(allowed),"distinct_orders":len(set(orders))}


def prepare(source_dir: Path, catalogue_path: Path, output_dir: Path) -> dict:
    if output_dir.exists(): raise FileExistsError("Human-review package already exists")
    catalogue=yaml.safe_load(catalogue_path.read_text())
    metadata_path=Path(catalogue["source_metadata_csv"])
    if file_sha256(metadata_path)!=catalogue["source_metadata_sha256"]:
        raise ValueError("Verified topic metadata changed")
    metadata=pd.read_csv(metadata_path)
    allowed=set(catalogue["catalogue_b"])
    sheets={name:source_dir/f"blind_{name}.csv" for name in ("calibration","evaluation")}
    audits={name:validate_blind_sheet(pd.read_csv(path),allowed) for name,path in sheets.items()}
    key_hashes={name:file_sha256(source_dir/f"restricted_key_{name}.csv") for name in sheets}
    output_dir.mkdir(parents=True,exist_ok=False)
    scope=metadata.loc[metadata.short_id.isin(allowed),
                       ["short_id","name","description","subfield_id"]].copy()
    scope=scope.rename(columns={"short_id":"topic_id","name":"official_name",
                                "description":"official_description","subfield_id":"parent_subfield"})
    scope["catalogue_overlap_note"]=scope.topic_id.map({key:value["overlap"]
                                                          for key,value in catalogue["scope_review"].items()})
    for col in sorted(SCOPE_COLUMNS-{"topic_id"}): scope[col]=""
    packages={}
    for reviewer in ("reviewer_a","reviewer_b"):
        folder=output_dir/reviewer;folder.mkdir()
        for name,path in sheets.items(): shutil.copyfile(path,folder/f"blind_{name}.csv")
        form=scope.copy();form["reviewer_id"]=reviewer
        form.to_csv(folder/"scope_review_form.csv",index=False)
        packages[reviewer]={name:file_sha256(folder/f"blind_{name}.csv") for name in sheets}
        packages[reviewer]["scope_form_sha256"]=file_sha256(folder/"scope_review_form.csv")
    manifest={"status":"prepared_pending_real_human_annotation","calibration":audits["calibration"],
              "evaluation":audits["evaluation"],"catalogue_sha256":file_sha256(catalogue_path),
              "topic_metadata_sha256":file_sha256(metadata_path),"restricted_key_hashes_not_copied":key_hashes,
              "package_checksums":packages,"rater_isolation":"separate folders; distribute separately",
              "ratings_received":0,"human_statistics":"not_measured"}
    (output_dir/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
    return manifest


def validate_package(output_dir: Path) -> dict:
    manifest=json.loads((output_dir/"manifest.json").read_text())
    if manifest.get("status")!="prepared_pending_real_human_annotation":
        raise ValueError("Unexpected review package status")
    for reviewer,entries in manifest["package_checksums"].items():
        for name in ("calibration","evaluation"):
            path=output_dir/reviewer/f"blind_{name}.csv"
            if file_sha256(path)!=entries[name]: raise ValueError("Blind package checksum changed")
        if file_sha256(output_dir/reviewer/"scope_review_form.csv")!=entries["scope_form_sha256"]:
            raise ValueError("Scope form checksum changed")
        if any((output_dir/reviewer).glob("restricted_key*")):
            raise ValueError("Restricted answer key exposed in reviewer package")
    return {"valid":True,"reviewers":2,"calibration_examples":manifest["calibration"]["examples"],
            "evaluation_examples":manifest["evaluation"]["examples"],
            "human_statistics":"pending"}


def validate_ratings(ratings: pd.DataFrame, blind: pd.DataFrame,
                     reviewer: str, allowed: set[str]) -> pd.DataFrame:
    if reviewer not in ("reviewer_a","reviewer_b"):
        raise ValueError("Reviewer must be one of the two isolated anonymous IDs")
    if not {"example_id","best_topic"}.issubset(ratings.columns):
        raise ValueError("Ratings need example_id and best_topic")
    if ratings.example_id.duplicated().any() or set(ratings.example_id)!=set(blind.example_id):
        raise ValueError("Reviewer ratings incomplete, duplicated or contain unknown IDs")
    converted=ratings.copy()
    canonical={f"https://openalex.org/{topic}":topic for topic in allowed}
    converted["best_topic"]=converted.best_topic.map(lambda value:canonical.get(value,value))
    if not converted.best_topic.isin(allowed|SPECIAL).all():
        raise ValueError("Invalid or missing best_topic choice")
    if "second_plausible_topic" in converted:
        second=converted.second_plausible_topic.dropna().map(lambda value:canonical.get(value,value))
        if not second.isin(allowed|SPECIAL).all():
            raise ValueError("Invalid second plausible topic")
    converted["reviewer_id"]=reviewer
    return converted.sort_values("example_id").reset_index(drop=True)


def human_agreement(a: pd.DataFrame,b: pd.DataFrame,answer_key: pd.DataFrame|None=None) -> dict:
    if set(a.example_id)!=set(b.example_id) or a.example_id.duplicated().any() or b.example_id.duplicated().any():
        raise ValueError("Ratings do not cover the same unique blind examples")
    merged=a[["example_id","best_topic"]].merge(b[["example_id","best_topic"]],on="example_id",
                                                suffixes=("_a","_b"),validate="one_to_one")
    n=len(merged);same=int(merged.best_topic_a.eq(merged.best_topic_b).sum())
    low,high=wilson_interval(same,n)
    result={"examples":n,"raw_agreement":same/n,"agreement_wilson_95":[low,high],
            "cohen_kappa_including_none_unclear":float(cohen_kappa_score(merged.best_topic_a,merged.best_topic_b)),
            "disagreement_examples":n-same,"none_or_unclear_a":int(merged.best_topic_a.isin(SPECIAL).sum()),
            "none_or_unclear_b":int(merged.best_topic_b.isin(SPECIAL).sum())}
    if answer_key is not None:
        joined=merged.merge(answer_key[["example_id","openalex_primary_topic"]],on="example_id",validate="one_to_one")
        if len(joined)!=n: raise ValueError("Restricted key does not cover all examples")
        gold=joined.openalex_primary_topic.map(lambda value:str(value).removeprefix("https://openalex.org/"))
        result["openalex_label_accepted_by_both"]=int((joined.best_topic_a.eq(gold)
            & joined.best_topic_b.eq(gold)).sum())
        result["both_disagree_with_openalex"]=int((~joined.best_topic_a.eq(gold)
            & ~joined.best_topic_b.eq(gold)).sum())
    return result


def main(argv: list[str]|None=None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest="command",required=True)
    make=sub.add_parser("prepare")
    make.add_argument("--source-dir",type=Path,default=Path("data/analysis/phase6/validation"))
    make.add_argument("--catalogue",type=Path,default=Path("config/phase6b_catalogue.yaml"))
    make.add_argument("--output-dir",type=Path,required=True)
    check=sub.add_parser("verify");check.add_argument("package_dir",type=Path)
    submit=sub.add_parser("validate-ratings")
    submit.add_argument("--ratings",type=Path,required=True)
    submit.add_argument("--blind",type=Path,required=True)
    submit.add_argument("--reviewer",choices=["reviewer_a","reviewer_b"],required=True)
    submit.add_argument("--catalogue",type=Path,default=Path("config/phase6b_catalogue.yaml"))
    args=parser.parse_args(argv)
    if args.command=="prepare": result=prepare(args.source_dir,args.catalogue,args.output_dir)
    elif args.command=="verify": result=validate_package(args.package_dir)
    else:
        allowed=set(yaml.safe_load(args.catalogue.read_text())["catalogue_b"])
        frame=validate_ratings(pd.read_csv(args.ratings),pd.read_csv(args.blind),args.reviewer,allowed)
        result={"valid":True,"reviewer":args.reviewer,"complete_ratings":len(frame),
                "note":"Validation only; this command does not copy or publish private ratings"}
    print(json.dumps(result,indent=2))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
