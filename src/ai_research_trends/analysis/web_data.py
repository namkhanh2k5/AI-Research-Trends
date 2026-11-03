"""Build verified, sample-scoped data products for a future Research Topic Explorer."""

from __future__ import annotations

import argparse
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yaml

from ai_research_trends.analysis.validation import verify_run as verify_phase4
from ai_research_trends.preprocessing.validate_tables import file_sha256

PHASE3=Path("data/processed/openalex_stratified/stratified_20261019T155909Z")
PHASE4=Path("data/analysis/phase4_stratified_20261019T155909Z_v3")


def _jsonable(value):
    if pd.isna(value): return None
    if hasattr(value,"item"): return value.item()
    if hasattr(value,"isoformat"): return value.isoformat()
    return value


def build(processed_dir: Path, phase4_dir: Path, catalogue_path: Path, output_dir: Path,
          topic_population_dir: Path|None=None) -> dict:
    if output_dir.exists(): raise FileExistsError(output_dir)
    verified=verify_phase4(phase4_dir)
    p3=json.loads((processed_dir/"manifest.json").read_text())
    for name,entry in p3["tables"].items():
        if file_sha256(processed_dir/f"{name}.parquet")!=entry["sha256"]:
            raise ValueError(f"Phase 3 source changed: {name}")
    catalogue=yaml.safe_load(catalogue_path.read_text())
    metadata_path=Path(catalogue["source_metadata_csv"])
    if file_sha256(metadata_path)!=catalogue["source_metadata_sha256"]:
        raise ValueError("Official topic metadata changed")
    metadata=pd.read_csv(metadata_path).set_index("short_id")
    population=None
    if topic_population_dir is not None:
        from ai_research_trends.analysis.topic_population import verify as verify_topic_population
        verify_topic_population(topic_population_dir)
        population=pd.read_csv(topic_population_dir/"topic_year_population.csv")
    works=pd.read_parquet(processed_dir/"works.parquet")
    relations=pd.read_parquet(processed_dir/"work_topics.parquet")
    if works.work_id.duplicated().any() or len(works)!=p3["tables"]["works"]["rows"]:
        raise ValueError("Original analytical sample is incomplete or duplicated")
    if relations[["work_id","topic_id"]].duplicated().any():
        raise ValueError("Duplicate work/topic relationship")
    secondary=(relations.sort_values(["work_id","topic_rank","topic_id"])
               .groupby("work_id").topic_id.apply(lambda s:"|".join(s.astype(str))).rename("topic_ids"))
    fields=["work_id","title","publication_year","primary_topic_id","work_type","language","doi",
            "cited_by_count","oa_status","has_abstract","publication_date"]
    index=works[fields].merge(secondary,on="work_id",how="left",validate="one_to_one")
    index=index.sort_values("work_id").reset_index(drop=True)
    index["source_scope"]="original_12000_detailed_sample_not_population"
    if len(index)!=len(works): raise ValueError("Paper index multiplied work rows")
    phase4_tables={name:pd.read_csv(phase4_dir/f"{name}.csv") for name in
                   ("publication_trends","citation_descriptives","oa_descriptives",
                    "collaboration_descriptives","country_collaboration_edges",
                    "institution_collaboration_edges")}
    selected=catalogue["catalogue_b"]
    briefs={}
    for short_id in selected:
        full_id=f"https://openalex.org/{short_id}"
        primary=works.loc[works.primary_topic_id.eq(full_id)].copy()
        if primary.empty: raise ValueError(f"No original sample primary-topic works: {short_id}")
        native=relations.loc[relations.topic_id.eq(full_id)]
        related=(relations.loc[relations.work_id.isin(native.work_id) & relations.topic_id.ne(full_id)]
                 .groupby("topic_id").work_id.nunique().sort_values(ascending=False).head(5))
        representative=primary.sort_values(["publication_date","cited_by_count","work_id"],
                                            ascending=[False,False,True]).head(5)
        briefs[short_id]={"topic_id":short_id,"official_name":str(metadata.at[short_id,"name"]),
            "official_description":str(metadata.at[short_id,"description"]),
            "parent_subfield":str(metadata.at[short_id,"subfield_id"]),
            "scope_status":catalogue["scope_review"][short_id]["status"],
            "sample_primary_topic_works":len(primary),"sample_any_topic_works":native.work_id.nunique(),
            "sample_year_counts":{str(k):int(v) for k,v in primary.publication_year.value_counts().sort_index().items()},
            "sample_citation_median":float(primary.cited_by_count.median()),
            "sample_oa_counts":{str(k):int(v) for k,v in primary.oa_status.value_counts(dropna=False).items()},
            "related_native_topics":[{"topic_id":k,"shared_sample_works":int(v)} for k,v in related.items()],
            "representative_papers":[{"work_id":r.work_id,"title":r.title,
                "publication_date":r.publication_date,"cited_by_count":int(r.cited_by_count)}
                for r in representative.itertuples()],
            "representative_rule":"five most recent primary-topic sampled papers; citations break same-date ties",
            "population_topic_year_counts":None if population is None else {
                str(int(row.year)):int(row.work_count) for row in
                population.loc[population.topic_id.eq(short_id)].itertuples()},
            "population_topic_snapshot_utc":None if population is None else
                str(population.loc[population.topic_id.eq(short_id),"retrieved_at_utc"].iloc[0]),
            "warnings":["Original 12,000-work sample is not a population estimate",
                        "OpenAlex primary topic is a machine-assigned label, not independently verified ground truth",
                        "Citation counts depend on publication age; representative does not mean best"]}
    output_dir.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".web_data_stage_",dir=output_dir.parent) as temp:
        stage=Path(temp)
        index.to_parquet(stage/"paper_index.parquet",index=False,compression="zstd")
        for key,value in briefs.items():
            path=stage/"topic_briefs"/f"{key}.json";path.parent.mkdir(exist_ok=True)
            path.write_text(json.dumps(value,ensure_ascii=False,indent=2,default=_jsonable)+"\n")
        for key,frame in phase4_tables.items():
            frame.to_csv(stage/f"{key}.csv",index=False)
        overview={"population_scope":"primary AI/CV subfields 1702/1707, article/review/preprint, 2020–2025, non-retracted",
                  "population_counts_source":"verified Phase 4 aggregate series",
                  "detailed_sample_works":len(works),"selected_topics":len(selected),
                  "sample_citation_median":float(works.cited_by_count.median()),
                  "sample_abstract_missing":int(works.abstract.isna().sum()),
                  "sample_fwci_missing":int(works.fwci.isna().sum()),
                  "sample_institution_missing":int(works.has_institution_affiliation.eq(False).sum())}
        (stage/"overview.json").write_text(json.dumps(overview,indent=2)+"\n")
        outputs={str(p.relative_to(stage)):{"sha256":file_sha256(p),"bytes":p.stat().st_size}
                 for p in sorted(stage.rglob("*")) if p.is_file()}
        manifest={"status":"complete","complete":True,"run_id":output_dir.name,
            "created_at_utc":datetime.now(timezone.utc).isoformat(),
            "source_scope":"original_12000_only; expansion excluded",
            "phase4_verification":verified,"source_phase3_manifest_sha256":file_sha256(processed_dir/"manifest.json"),
            "source_phase4_manifest_sha256":file_sha256(phase4_dir/"manifest.json"),
            "catalogue_sha256":file_sha256(catalogue_path),"code_sha256":file_sha256(Path(__file__)),
            "topic_population_manifest_sha256":None if topic_population_dir is None else
                file_sha256(topic_population_dir/"manifest.json"),
            "paper_rows":len(index),"topic_briefs":len(briefs),"outputs":outputs,"api_requests":0,
            "population_topic_series":"unavailable" if population is None else
                "verified OpenAlex primary-topic snapshot; separate from sample and older Phase 4 aggregate snapshot"}
        (stage/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
        stage.replace(output_dir)
    return manifest


def verify(run_dir: Path) -> dict:
    manifest=json.loads((run_dir/"manifest.json").read_text())
    if manifest.get("status")!="complete" or not manifest.get("complete"):
        raise ValueError("Web data run is incomplete")
    for name,item in manifest["outputs"].items():
        path=run_dir/name
        if not path.is_file() or path.stat().st_size!=item["bytes"] or file_sha256(path)!=item["sha256"]:
            raise ValueError(f"Corrupt web data product: {name}")
    index=pd.read_parquet(run_dir/"paper_index.parquet")
    if len(index)!=manifest["paper_rows"] or index.work_id.duplicated().any():
        raise ValueError("Paper index row or identity failure")
    if not index.source_scope.eq("original_12000_detailed_sample_not_population").all():
        raise ValueError("Non-original work entered paper index")
    for path in (run_dir/"topic_briefs").glob("*.json"):
        brief=json.loads(path.read_text())
        counts=brief["population_topic_year_counts"]
        if counts is not None and (set(counts)!={str(y) for y in range(2020,2026)}
                                   or brief["population_topic_snapshot_utc"] is None):
            raise ValueError("Incomplete or unproven topic population series")
    return {"valid":True,"outputs_verified":len(manifest["outputs"]),"paper_rows":len(index),
            "topic_briefs":manifest["topic_briefs"]}


def main(argv: list[str]|None=None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest="command",required=True)
    make=sub.add_parser("build")
    make.add_argument("--processed-dir",type=Path,default=PHASE3)
    make.add_argument("--phase4-dir",type=Path,default=PHASE4)
    make.add_argument("--catalogue",type=Path,default=Path("config/phase6b_catalogue.yaml"))
    make.add_argument("--topic-population-dir",type=Path)
    make.add_argument("--output-dir",type=Path,required=True)
    check=sub.add_parser("verify");check.add_argument("run_dir",type=Path)
    args=parser.parse_args(argv)
    result=build(args.processed_dir,args.phase4_dir,args.catalogue,args.output_dir,args.topic_population_dir) if args.command=="build" else verify(args.run_dir)
    print(json.dumps(result,indent=2,default=_jsonable));return 0


if __name__=="__main__": raise SystemExit(main())
