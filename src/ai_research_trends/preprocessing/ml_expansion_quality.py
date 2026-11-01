"""Audit new historical OpenAlex records without changing Phase 2/3 datasets."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

import pandas as pd
import yaml

from ai_research_trends.config import FIXED_CORPUS, validate_corpus_work
from ai_research_trends.crawling.openalex_client import canonical_work_id
from ai_research_trends.crawling.verify_ml_expansion import verify
from ai_research_trends.ml.topic_pilot import clean_text, title_key
from ai_research_trends.preprocessing.text import reconstruct_abstract
from ai_research_trends.preprocessing.validate_tables import file_sha256


def identity_keys(doi: object, title: object) -> set[str]:
    """Use DOI and sufficiently specific normalized title, never model labels."""
    keys=set()
    if isinstance(doi,str) and doi.strip():
        value=doi.strip().casefold().removeprefix("https://doi.org/").removeprefix("http://doi.org/")
        keys.add("doi:"+value)
    if isinstance(title,str):
        key=title_key(title)
        if len(key)>=20: keys.add("title:"+key)
    return keys


def text_quality(work: dict) -> tuple[str,str|None,int]:
    """Explicit text audit; malformed abstracts are quarantined from ML, not raw storage."""
    title=clean_text(work.get("title"))
    if not title: return "missing_title",None,0
    try:
        abstract=reconstruct_abstract(work.get("abstract_inverted_index"))
    except ValueError:
        return "malformed_abstract",None,0
    if not abstract: return "missing_abstract",None,0
    abstract=clean_text(abstract)
    words=len(abstract.split())
    if re.search(r"(?i)^\s*(abstract (not available|unavailable)|no abstract available)\s*$",abstract):
        return "boilerplate_abstract",abstract,words
    if words<30: return "short_abstract",abstract,words
    return "usable",abstract,words


def audit_records(records: list[dict], original: pd.DataFrame, catalogue: dict,
                  gap: pd.DataFrame, metadata: pd.DataFrame|None=None) -> tuple[pd.DataFrame,dict[str,pd.DataFrame],dict]:
    """Produce local row audit and aggregate tables from verified acquisition evidence."""
    if original.work_id.duplicated().any(): raise ValueError("Original Work IDs are not unique")
    selected=set(catalogue["catalogue_b"])
    original_ids=set(original.work_id)
    train=original.loc[original.publication_year.between(2020,2023)]
    heldout=original.loc[original.publication_year.between(2024,2025)]
    train_identity=set().union(*(identity_keys(row.doi,row.title) for row in train.itertuples()))
    heldout_identity=set().union(*(identity_keys(row.doi,row.title) for row in heldout.itertuples()))
    entries=[]
    for record in records:
        work=record["work"];provenance=record["provenance"]
        wid=canonical_work_id(work["id"])
        corpus=validate_corpus_work(work,FIXED_CORPUS,require_non_retracted=True)
        if not corpus.valid or work["publication_year"] not in range(2020,2024):
            raise ValueError(f"Acquired record violates historical corpus: {wid}: {corpus.errors}")
        topic=(work.get("primary_topic") or {}).get("id")
        if not isinstance(topic,str) or not re.fullmatch(r"https://openalex\.org/T\d+",topic):
            raise ValueError(f"Missing or invalid primary topic: {wid}")
        expected=provenance["source_query"]["filter"]
        if "primary_topic.id:" in expected and topic.split("/")[-1]!=expected.rsplit("primary_topic.id:",1)[-1]:
            raise ValueError(f"Primary topic does not match requested stratum: {wid}")
        status,abstract,word_count=text_quality(work)
        title=clean_text(work.get("title"))
        entries.append({"work_id":wid,"publication_year":work["publication_year"],
                        "publication_date":work["publication_date"],"work_type":work["type"],
                        "language":work.get("language"),"doi":work.get("doi"),"title":title,
                        "abstract":abstract,"abstract_word_count":word_count,"text_quality_status":status,
                        "primary_topic_id":topic,"primary_topic_name":(work.get("primary_topic") or {}).get("display_name"),
                        "top_three_topic_ids":json.dumps([item.get("id") for item in (work.get("topics") or [])[:3]]),
                        "is_selected":topic.split("/")[-1] in selected,
                        "source_group":provenance["source_group"],
                        "retrieved_at_utc":provenance["retrieved_at_utc"],
                        "collection_run_id":provenance["collection_run_id"]})
    audit=pd.DataFrame(entries).sort_values(["publication_date","work_id"]).reset_index(drop=True)
    if audit.work_id.duplicated().any(): raise ValueError("Interim expansion Work IDs are duplicated")
    if metadata is not None:
        names=metadata.set_index("topic_id").name.to_dict()
        audit["official_topic_name"] = audit.primary_topic_id.map(names)
        audit["topic_name_consistent"] = audit.apply(
            lambda row: None if pd.isna(row.official_topic_name) or pd.isna(row.primary_topic_name)
            else row.official_topic_name==row.primary_topic_name,axis=1)
    else:
        audit["official_topic_name"]=None
        audit["topic_name_consistent"]=None
    seen_new=set();reasons=[]
    for row in audit.itertuples():
        keys=identity_keys(row.doi,row.title)
        if row.work_id in original_ids:
            reason="original_work_id_overlap"
        elif keys & heldout_identity:
            reason="heldout_doi_or_title_overlap"
        elif keys & train_identity:
            reason="original_training_version_overlap"
        elif keys & seen_new:
            reason="new_version_overlap"
        elif row.text_quality_status!="usable":
            reason=row.text_quality_status
        else:
            reason="eligible"
        seen_new.update(keys)
        reasons.append(reason)
    audit["exclusion_reason"]=reasons
    audit["ml_training_eligible"]=audit.exclusion_reason.eq("eligible")
    audit["ml_role"]=audit.is_selected.map({True:"selected_training",False:"out_of_catalogue_training"})
    audit.loc[~audit.ml_training_eligible,"ml_role"]="excluded_preserve_raw"
    original_counts=gap.set_index("short_id").usable_training_works.to_dict()
    topic_rows=[]
    for short in catalogue["catalogue_b"]:
        subset=audit.loc[audit.primary_topic_id.eq(f"https://openalex.org/{short}")]
        new=int(subset.ml_training_eligible.sum())
        old=int(original_counts[short]);target=225
        topic_rows.append({"topic_id":short,"original_usable_train":old,
                           "newly_usable_train":new,"combined_usable_train":old+new,
                           "target":target,"remaining_gap":max(0,target-old-new),
                           "raw_new_records":len(subset),
                           "missing_abstract_new":int(subset.text_quality_status.eq("missing_abstract").sum()),
                           "excluded_versions_or_identity":int(subset.exclusion_reason.isin([
                               "original_work_id_overlap","heldout_doi_or_title_overlap",
                               "original_training_version_overlap","new_version_overlap"]).sum())})
    topic_table=pd.DataFrame(topic_rows)
    by_year=(audit.groupby("publication_year",as_index=False)
             .agg(raw_new_records=("work_id","size"),usable_new=("ml_training_eligible","sum"),
                  selected_new=("is_selected","sum")))
    by_type=(audit.groupby("work_type",as_index=False)
             .agg(raw_new_records=("work_id","size"),usable_new=("ml_training_eligible","sum")))
    by_language=(audit.assign(language=audit.language.fillna("<missing>"))
                 .groupby("language",as_index=False).agg(raw_new_records=("work_id","size"),
                                                        usable_new=("ml_training_eligible","sum")))
    summary={"raw_unique_new_ids":len(audit),"overlap_original_work_ids":int(audit.work_id.isin(original_ids).sum()),
             "eligible_new_total":int(audit.ml_training_eligible.sum()),
             "eligible_selected_new":int((audit.ml_training_eligible & audit.is_selected).sum()),
             "eligible_outside_new":int((audit.ml_training_eligible & ~audit.is_selected).sum()),
             "exclusion_reasons":dict(Counter(audit.exclusion_reason)),
             "text_quality_counts":dict(Counter(audit.text_quality_status)),
             "original_selected_usable":int(topic_table.original_usable_train.sum()),
             "expanded_selected_usable":int(topic_table.combined_usable_train.sum()),
             "remaining_topic_gaps":int(topic_table.remaining_gap.sum())}
    summary["primary_topic_name_mismatches_known_metadata"]=int(audit.topic_name_consistent.eq(False).sum())
    summary["primary_topic_name_unassessed"]=int(audit.topic_name_consistent.isna().sum())
    return audit,{"topic_support":topic_table,"by_year":by_year,
                  "by_type":by_type,"by_language":by_language},summary


def main(argv: list[str]|None=None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest",type=Path,required=True)
    parser.add_argument("--processed-dir",type=Path,default=Path("data/processed/openalex_stratified/stratified_20261019T155909Z"))
    parser.add_argument("--catalogue",type=Path,default=Path("config/phase6b_catalogue.yaml"))
    parser.add_argument("--gap-csv",type=Path,required=True)
    parser.add_argument("--output-dir",type=Path,required=True)
    args=parser.parse_args(argv)
    if args.output_dir.exists(): parser.error("Output exists; choose a versioned directory")
    result=verify(args.manifest)
    manifest=json.loads(args.manifest.read_text())
    with Path(manifest["interim_jsonl_path"]).open() as handle:
        records=[json.loads(line) for line in handle]
    if len(records)!=result["unique_work_ids"]: raise ValueError("Verifier count differs from interim rows")
    works_path=args.processed_dir/"works.parquet"
    original=pd.read_parquet(works_path,columns=["work_id","publication_year","doi","title"])
    catalogue=yaml.safe_load(args.catalogue.read_text())
    gap=pd.read_csv(args.gap_csv)
    metadata=pd.read_csv(catalogue["source_metadata_csv"])
    if file_sha256(Path(catalogue["source_metadata_csv"]))!=catalogue["source_metadata_sha256"]:
        raise ValueError("Official topic metadata checksum mismatch")
    audit,tables,summary=audit_records(records,original,catalogue,gap,metadata)
    args.output_dir.mkdir(parents=True,exist_ok=False)
    audit_path=args.output_dir/"record_audit.csv";audit.to_csv(audit_path,index=False)
    outputs={"record_audit.csv":{"rows":len(audit),"sha256":file_sha256(audit_path)}}
    for name,table in tables.items():
        path=args.output_dir/f"{name}.csv";table.to_csv(path,index=False)
        outputs[path.name]={"rows":len(table),"sha256":file_sha256(path)}
    processing={"status":"complete","source_manifest_sha256":file_sha256(args.manifest),
                "source_work_sha256":file_sha256(works_path),"gap_sha256":file_sha256(args.gap_csv),
                "catalogue_sha256":file_sha256(args.catalogue),"outputs":outputs,"summary":summary,
                "leakage_policy":"2024-25 Work ID/DOI/title identities only; never held-out labels",
                "note":"Staging audit only; not an updated Phase 3 analytical sample"}
    (args.output_dir/"manifest.json").write_text(json.dumps(processing,indent=2)+"\n")
    print(json.dumps(summary,indent=2))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
