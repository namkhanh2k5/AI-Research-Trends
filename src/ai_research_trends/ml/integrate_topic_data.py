"""Deterministic, non-destructive integration of original and targeted ML records."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import tempfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path

import pandas as pd
import yaml

from ai_research_trends.crawling.openalex_client import canonical_work_id
from ai_research_trends.crawling.verify_collection import verify_completed_collection
from ai_research_trends.crawling.verify_ml_expansion import verify as verify_expansion
from ai_research_trends.ml.topic_pilot import clean_text, title_key
from ai_research_trends.preprocessing.common import normalize_doi
from ai_research_trends.preprocessing.text import reconstruct_abstract
from ai_research_trends.preprocessing.validate_tables import file_sha256


ORIGINAL=Path("data/processed/openalex_stratified/stratified_20261019T155909Z")
ORIGINAL_MANIFEST=Path("data/raw/openalex_stratified/stratified_20261019T155909Z/manifest.json")
EXPANSION_MANIFEST=Path("data/raw/openalex_ml_expansion/ml_expansion_20261101T052506Z/manifest.json")
CATALOGUE=Path("config/phase6b_catalogue.yaml")
PROTOCOL=Path("docs/FINALIZATION_P2_INTEGRATION_PROTOCOL.md")


def quality_status(title: object, abstract: object, *, malformed: bool=False) -> str:
    if malformed: return "malformed_abstract"
    if not isinstance(title,str) or not clean_text(title): return "missing_title"
    if not isinstance(abstract,str) or not clean_text(abstract): return "missing_abstract"
    if re.fullmatch(r"(?i)\s*(abstract (not available|unavailable)|no abstract available)\s*",abstract):
        return "boilerplate_abstract"
    if len(clean_text(abstract).split())<30: return "short_abstract"
    return "usable"


def split_for_year(year: int) -> str:
    if year in (2020,2021,2022,2023): return "train"
    if year==2024: return "validation"
    if year==2025: return "test"
    raise ValueError(f"Unexpected publication year: {year}")


def source_rows(original: pd.DataFrame, expansion_records: list[dict],
                original_topics: pd.DataFrame) -> pd.DataFrame:
    """Normalize source columns without changing any source artifact."""
    rank=original_topics.loc[original_topics.topic_rank.eq(1),
                             ["work_id","topic_id","topic_score"]]
    if rank.work_id.duplicated().any() or len(rank)!=len(original):
        raise ValueError("Original rank-one topics are incomplete")
    originals=original.merge(rank,on="work_id",validate="one_to_one")
    if not originals.primary_topic_id.eq(originals.topic_id).all():
        raise ValueError("Original primary topic differs from rank-one relationship")
    rows=[]
    for work in originals.itertuples(index=False):
        wid=canonical_work_id(work.work_id)
        date=str(work.publication_date)
        status=quality_status(work.title,work.abstract)
        rows.append({"source_record_key":"original:"+wid,"work_id":wid,
            "dataset_origin":"original_analytical_sample","title":clean_text(work.title) or None,
            "abstract":clean_text(work.abstract) or None,"publication_date":date,
            "publication_year":int(work.publication_year),"work_type":work.work_type,
            "language":work.language if pd.notna(work.language) else None,
            "doi":normalize_doi(work.doi) if pd.notna(work.doi) else None,
            "primary_topic_id":work.primary_topic_id,"topic_score":work.topic_score,
            "collection_run_id":work.collection_run_id,
            "retrieved_at_utc":str(work.retrieved_at_utc),
            "label_snapshot":"original_20261019","text_quality_status":status})
    for record in expansion_records:
        work=record["work"];provenance=record["provenance"]
        wid=canonical_work_id(work["id"])
        year=work.get("publication_year")
        if year not in (2020,2021,2022,2023):
            raise ValueError(f"Expansion work outside training years: {wid}")
        malformed=False
        try: abstract=reconstruct_abstract(work.get("abstract_inverted_index"))
        except ValueError: abstract=None;malformed=True
        primary=work.get("primary_topic") or {}
        topic=primary.get("id")
        if not isinstance(topic,str) or not re.fullmatch(r"https://openalex\.org/T\d+",topic):
            raise ValueError(f"Expansion primary topic missing: {wid}")
        rows.append({"source_record_key":"expansion:"+wid,"work_id":wid,
            "dataset_origin":"targeted_ml_expansion","title":clean_text(work.get("title")) or None,
            "abstract":clean_text(abstract) or None,"publication_date":work["publication_date"],
            "publication_year":year,"work_type":work["type"],"language":work.get("language"),
            "doi":normalize_doi(work.get("doi")) if work.get("doi") else None,
            "primary_topic_id":topic,"topic_score":primary.get("score"),
            "collection_run_id":provenance["collection_run_id"],
            "retrieved_at_utc":provenance["retrieved_at_utc"],
            "label_snapshot":provenance["topic_snapshot_version"],
            "text_quality_status":quality_status(work.get("title"),abstract,malformed=malformed)})
    result=pd.DataFrame(rows).sort_values("source_record_key").reset_index(drop=True)
    if result.source_record_key.duplicated().any(): raise ValueError("Duplicate source record key")
    dates=pd.to_datetime(result.publication_date,format="%Y-%m-%d",errors="raise")
    if not dates.dt.year.eq(result.publication_year).all(): raise ValueError("Year/date inconsistency")
    result["split"] = result.publication_year.map(split_for_year)
    return result


def identity_groups(frame: pd.DataFrame) -> pd.DataFrame:
    """Transitive Work-ID/DOI/normalized-title groups, independent of labels."""
    if frame.source_record_key.duplicated().any(): raise ValueError("Duplicate record keys")
    keys=frame.source_record_key.tolist(); parent={key:key for key in keys};seen={}
    def root(item: str) -> str:
        while parent[item]!=item:
            parent[item]=parent[parent[item]];item=parent[item]
        return item
    def union(a: str,b: str) -> None:
        a,b=root(a),root(b)
        parent[max(a,b)]=min(a,b)
    for row in frame.itertuples(index=False):
        identity=["work:"+row.work_id]
        if isinstance(row.doi,str) and row.doi:
            identity.append("doi:"+row.doi.casefold().removeprefix("https://doi.org/"))
        if isinstance(row.title,str):
            key=title_key(row.title)
            if len(key)>=20: identity.append("title:"+key)
        for value in identity:
            if value in seen: union(row.source_record_key,seen[value])
            else: seen[value]=row.source_record_key
    members=defaultdict(list)
    for row in frame.itertuples(index=False): members[root(row.source_record_key)].append(row.work_id)
    group_ids={key:min(values) for key,values in members.items()}
    out=frame.copy();out["version_group"]=[group_ids[root(key)] for key in keys]
    return out


def resolve_groups(grouped: pd.DataFrame, selected_topics: set[str]) -> tuple[pd.DataFrame,pd.DataFrame,pd.DataFrame]:
    """Prefer complete text within winning split; seal test labels from decisions."""
    audit=grouped.copy();audit["is_representative"]=False
    audit["exclusion_reason"]="nonrepresentative_version"
    audit["representative_work_id"]=None
    summaries=[];representatives=[]
    rank={"train":0,"validation":1,"test":2}
    for group_id,part in audit.groupby("version_group",sort=True):
        periods=set(part.split)
        winning=max(periods,key=rank.get)
        candidates=part.loc[part.split.eq(winning)]
        if winning=="test":
            ordered=candidates.sort_values(["dataset_origin","publication_date","work_id","source_record_key"])
        else:
            ordered=(candidates.assign(quality_rank=candidates.text_quality_status.ne("usable").astype(int),
                                      source_rank=candidates.dataset_origin.ne("original_analytical_sample").astype(int))
                     .sort_values(["quality_rank","source_rank","publication_date","work_id","source_record_key"]))
        chosen=ordered.iloc[0]
        if winning=="test": label_conflict=False  # Do not inspect locked labels.
        else:
            label_conflict=part.loc[part.split.ne("test"),"primary_topic_id"].nunique()>1
        cross_period=len(periods)>1
        reason="eligible"
        if chosen.text_quality_status!="usable": reason=chosen.text_quality_status
        elif label_conflict and not cross_period: reason="topic_label_conflict"
        idx=chosen.name
        audit.at[idx,"is_representative"]=True
        audit.at[idx,"exclusion_reason"]=reason
        audit.loc[part.index,"representative_work_id"]=chosen.work_id
        other_idx=part.index.difference([idx])
        lower_idx=other_idx[audit.loc[other_idx,"split"].ne(winning)]
        audit.loc[lower_idx,"exclusion_reason"]="cross_period_version"
        rep=chosen.to_dict();rep.update({"version_group":group_id,
            "selected_catalogue":chosen.primary_topic_id in selected_topics if winning!="test" else None,
            "usable_for_ml":reason=="eligible","ml_role":winning if reason=="eligible" else "excluded",
            "exclusion_reason":reason,"group_label_conflict_development":bool(label_conflict),
            "cross_period_group":cross_period})
        representatives.append(rep)
        summaries.append({"version_group":group_id,"source_records":len(part),
            "unique_work_ids":part.work_id.nunique(),"periods":",".join(sorted(periods,key=rank.get)),
            "cross_period":cross_period,"topic_label_conflict_development":bool(label_conflict),
            "representative_work_id":chosen.work_id,"representative_source":chosen.dataset_origin,
            "resolution":reason})
    reps=pd.DataFrame(representatives).sort_values("version_group").reset_index(drop=True)
    groups=pd.DataFrame(summaries).sort_values("version_group").reset_index(drop=True)
    return audit,reps,groups


def near_cross_period_risks(reps: pd.DataFrame) -> pd.DataFrame:
    """Rare-title-token blocked, conservative high-similarity cross-period audit."""
    eligible=reps.loc[reps.usable_for_ml & reps.title.notna(),
                      ["version_group","work_id","split","title"]].copy()
    eligible["title_key"]=eligible.title.map(title_key)
    stop={"neural","network","learning","based","using","research","analysis","method","methods",
          "model","models","deep","data","image","study","artificial"}
    tokens={row.work_id:{term for term in row.title_key.split() if len(term)>=5 and term not in stop}
            for row in eligible.itertuples()}
    counts=Counter(term for terms in tokens.values() for term in terms)
    blocks=defaultdict(list)
    for row in eligible.itertuples():
        for term in sorted(tokens[row.work_id],key=lambda term:(counts[term],term))[:3]:
            if counts[term]<=100: blocks[term].append(row)
    pairs=set()
    for entries in blocks.values():
        for i,left in enumerate(entries):
            for right in entries[i+1:]:
                if left.split==right.split or left.version_group==right.version_group: continue
                pair=tuple(sorted((left.work_id,right.work_id)))
                pairs.add(pair)
    by_id=eligible.set_index("work_id")
    risks=[]
    for a,b in sorted(pairs):
        left,right=by_id.loc[a],by_id.loc[b]
        ta,tb=left.title_key,right.title_key
        if min(len(ta),len(tb))<30 or abs(len(ta)-len(tb))>.2*max(len(ta),len(tb)): continue
        score=SequenceMatcher(None,ta,tb,autojunk=False).ratio()
        if score>=.96:
            risks.append({"work_id_a":a,"work_id_b":b,"split_a":left.split,"split_b":right.split,
                          "title_similarity":score,"decision":"lower_period_excluded_pending_review"})
    return pd.DataFrame(risks,columns=["work_id_a","work_id_b","split_a","split_b",
                                      "title_similarity","decision"])


def apply_near_risk_exclusions(reps: pd.DataFrame, audit: pd.DataFrame,
                               risks: pd.DataFrame) -> tuple[pd.DataFrame,pd.DataFrame]:
    if risks.empty: return reps,audit
    rank={"train":0,"validation":1,"test":2}; exclude=set()
    for row in risks.itertuples(index=False):
        loser=row.work_id_a if rank[row.split_a]<rank[row.split_b] else row.work_id_b
        exclude.add(loser)
    reps=reps.copy();audit=audit.copy()
    mask=reps.work_id.isin(exclude)
    reps.loc[mask,"usable_for_ml"]=False
    reps.loc[mask,"ml_role"]="excluded"
    reps.loc[mask,"exclusion_reason"]="near_cross_period_title_pending_review"
    audit.loc[audit.is_representative & audit.work_id.isin(exclude),"exclusion_reason"]="near_cross_period_title_pending_review"
    return reps,audit


def validate_splits(reps: pd.DataFrame, audit: pd.DataFrame) -> dict:
    if reps.version_group.duplicated().any(): raise ValueError("Duplicate canonical version group")
    eligible=reps.loc[reps.usable_for_ml]
    if eligible.work_id.duplicated().any(): raise ValueError("Duplicate model Work ID")
    if eligible.version_group.duplicated().any(): raise ValueError("Duplicate model version group")
    if not eligible.loc[eligible.dataset_origin.eq("targeted_ml_expansion"),"split"].eq("train").all():
        raise ValueError("Expansion contaminated held-out split")
    for field in ("work_id","doi"):
        values=eligible.loc[eligible[field].notna()].groupby(field).split.nunique()
        if values.gt(1).any(): raise ValueError(f"Cross-split {field} leakage")
    keys=eligible.title.fillna("").map(title_key)
    if (eligible.assign(title_key=keys).loc[keys.str.len().ge(20)]
        .groupby("title_key").split.nunique().gt(1).any()):
        raise ValueError("Cross-split exact normalized-title leakage")
    if audit.source_record_key.duplicated().any(): raise ValueError("Source audit lost source-grain uniqueness")
    return {"source_records":len(audit),"canonical_groups":len(reps),
            "eligible_training":int(eligible.split.eq("train").sum()),
            "eligible_validation":int(eligible.split.eq("validation").sum()),
            "sealed_test_total":int(eligible.split.eq("test").sum()),
            "cross_split_work_id_doi_title_version_group":"PASS",
            "expansion_training_only":"PASS"}


def build_integration(original: pd.DataFrame, topics: pd.DataFrame, expansion: list[dict],
                      selected_topics: set[str]) -> tuple[dict[str,pd.DataFrame],dict]:
    rows=source_rows(original,expansion,topics)
    grouped=identity_groups(rows)
    audit,reps,groups=resolve_groups(grouped,selected_topics)
    risks=near_cross_period_risks(reps)
    reps,audit=apply_near_risk_exclusions(reps,audit,risks)
    checks=validate_splits(reps,audit)
    model=reps.loc[reps.usable_for_ml].copy()
    tables={"source_record_audit":audit,"ml_papers":reps,"version_groups":groups,
            "near_duplicate_risks":risks,
            "train":model.loc[model.split.eq("train")].copy(),
            "validation_2024":model.loc[model.split.eq("validation")].copy(),
            "test_2025_sealed":model.loc[model.split.eq("test")].copy(),
            "excluded":reps.loc[~reps.usable_for_ml].copy()}
    # Keep locked 2025 labels only in the separately named sealed artifact.
    # General audit/search tables must not expose them to development code.
    for name in ("source_record_audit","ml_papers","excluded"):
        frame=tables[name].copy()
        locked=frame.split.eq("test")
        frame.loc[locked,["primary_topic_id","topic_score"]]=None
        tables[name]=frame
    return tables,checks


def _json_ready(value):
    if isinstance(value,Path): return str(value)
    raise TypeError(type(value).__name__)


def run(processed_dir: Path, original_manifest_path: Path, expansion_manifest_path: Path,
        catalogue_path: Path, protocol_path: Path, output_dir: Path) -> dict:
    if output_dir.exists(): raise FileExistsError(f"Output directory exists: {output_dir}")
    original_verification=verify_completed_collection(original_manifest_path)
    expansion_verification=verify_expansion(expansion_manifest_path)
    phase3_manifest=json.loads((processed_dir/"manifest.json").read_text())
    for name,entry in phase3_manifest["tables"].items():
        if file_sha256(processed_dir/f"{name}.parquet")!=entry["sha256"]:
            raise ValueError(f"Original Phase 3 table checksum changed: {name}")
    quality_path=Path("data/analysis/finalization_p1_quality_20261101_v2/manifest.json")
    quality=json.loads(quality_path.read_text())
    if quality.get("status")!="complete" or quality["source_manifest_sha256"]!=file_sha256(expansion_manifest_path):
        raise ValueError("Phase 1 private quality audit does not match expansion evidence")
    config=yaml.safe_load(catalogue_path.read_text())
    metadata_path=Path(config["source_metadata_csv"])
    if file_sha256(metadata_path)!=config["source_metadata_sha256"]:
        raise ValueError("Verified topic metadata changed")
    selected={f"https://openalex.org/{item}" for item in config["catalogue_b"]}
    original=pd.read_parquet(processed_dir/"works.parquet")
    topics=pd.read_parquet(processed_dir/"work_topics.parquet")
    expansion_manifest=json.loads(expansion_manifest_path.read_text())
    with Path(expansion_manifest["interim_jsonl_path"]).open() as handle:
        expansion=[json.loads(line) for line in handle]
    if len(original)!=original_verification["verified_unique_work_ids"] or len(expansion)!=expansion_verification["unique_work_ids"]:
        raise ValueError("Source row count differs from verified collection")
    tables,checks=build_integration(original,topics,expansion,selected)
    output_dir.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".finalization_p2_stage_",dir=output_dir.parent) as temp:
        stage=Path(temp);files={}
        for name,frame in tables.items():
            path=stage/f"{name}.parquet"
            stable=frame.sort_values(["version_group"] if name!="source_record_audit" and "version_group" in frame else
                                     ["source_record_key"] if "source_record_key" in frame else list(frame.columns[:1])).reset_index(drop=True)
            stable.to_parquet(path,index=False,engine="pyarrow",compression="zstd")
            files[path.name]={"rows":len(stable),"sha256":file_sha256(path),"bytes":path.stat().st_size}
        source_paths={"original_manifest":original_manifest_path,"expansion_manifest":expansion_manifest_path,
            "phase3_manifest":processed_dir/"manifest.json","phase1_quality_manifest":quality_path,
            "catalogue":catalogue_path,"topic_metadata":metadata_path,"integration_protocol":protocol_path,
            "expansion_interim":Path(expansion_manifest["interim_jsonl_path"])}
        for name in phase3_manifest["tables"]:
            source_paths[f"phase3_{name}"]=processed_dir/f"{name}.parquet"
        manifest={"status":"complete","complete":True,"run_id":output_dir.name,
            "created_at_utc":datetime.now(timezone.utc).isoformat(),
            "code_sha256":file_sha256(Path(__file__)),"source_run_ids":[phase3_manifest["source_run_id"],expansion_manifest["run_id"]],
            "human_annotation_status":"PENDING REAL HUMAN ANNOTATION","api_requests":0,
            "input_rows":{"original":len(original),"expansion":len(expansion)},
            "inputs":{key:{"path":str(path),"sha256":file_sha256(path)} for key,path in source_paths.items()},
            "outputs":files,"validation":checks,
            "summary":{"source_exclusion_reasons":dict(Counter(tables["source_record_audit"].exclusion_reason)),
                "canonical_exclusion_reasons":dict(Counter(tables["ml_papers"].exclusion_reason)),
                "cross_period_groups":int(tables["version_groups"].cross_period.sum()),
                "development_label_conflict_groups":int(tables["version_groups"].topic_label_conflict_development.sum()),
                "near_cross_period_pairs":len(tables["near_duplicate_risks"]),
                "new_training_rows":int(tables["train"].dataset_origin.eq("targeted_ml_expansion").sum()),
                "original_training_rows":int(tables["train"].dataset_origin.eq("original_analytical_sample").sum())},
            "sealed_test_policy":"row count and SHA-256 only; no class distributions or predictions"}
        (stage/"split_manifest.json").write_text(json.dumps(manifest,indent=2,default=_json_ready)+"\n")
        stage.replace(output_dir)
    return manifest


def main(argv: list[str]|None=None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--processed-dir",type=Path,default=ORIGINAL)
    parser.add_argument("--original-manifest",type=Path,default=ORIGINAL_MANIFEST)
    parser.add_argument("--expansion-manifest",type=Path,default=EXPANSION_MANIFEST)
    parser.add_argument("--catalogue",type=Path,default=CATALOGUE)
    parser.add_argument("--protocol",type=Path,default=PROTOCOL)
    parser.add_argument("--output-dir",type=Path,required=True)
    args=parser.parse_args(argv)
    result=run(args.processed_dir,args.original_manifest,args.expansion_manifest,
               args.catalogue,args.protocol,args.output_dir)
    print(json.dumps({"status":result["status"],"run_id":result["run_id"],
        "validation":result["validation"],"summary":result["summary"]},indent=2))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
