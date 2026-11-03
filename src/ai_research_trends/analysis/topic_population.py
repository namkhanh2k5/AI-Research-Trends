"""Bounded OpenAlex primary-topic/year aggregate snapshot for the frozen catalogue."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yaml

from ai_research_trends.config import FIXED_CORPUS, build_study_filter
from ai_research_trends.crawling.collect_aggregates import validate_year_aggregation
from ai_research_trends.crawling.openalex_client import OpenAlexClient
from ai_research_trends.env import load_project_env
from ai_research_trends.preprocessing.validate_tables import file_sha256


def query_specs(catalogue: dict) -> list[dict]:
    base=build_study_filter(FIXED_CORPUS,retraction_scope="non_retracted")
    ids=catalogue["catalogue_b"]
    if len(ids)!=14 or len(set(ids))!=14: raise ValueError("Frozen catalogue must contain 14 distinct topics")
    return [{"topic_id":topic,"params":{"filter":f"{base},primary_topic.id:{topic}",
            "group_by":"publication_year","per_page":100}} for topic in ids]


def collect(catalogue_path: Path, output_dir: Path, *, max_requests: int=14,
            client: OpenAlexClient|None=None) -> dict:
    if output_dir.exists(): raise FileExistsError(output_dir)
    catalogue=yaml.safe_load(catalogue_path.read_text());specs=query_specs(catalogue)
    if max_requests!=len(specs): raise ValueError("Budget must authorize exactly all 14 queries")
    if client is None:
        load_project_env();client=OpenAlexClient()
    if not client.api_key: raise RuntimeError("OPENALEX_API_KEY is not configured; no live query attempted")
    output_dir.mkdir(parents=True,exist_ok=False)
    manifest={"status":"incomplete","complete":False,"run_id":output_dir.name,
        "started_at_utc":datetime.now(timezone.utc).isoformat(),"catalogue_sha256":file_sha256(catalogue_path),
        "corpus_definition":FIXED_CORPUS,"maximum_api_requests":max_requests,"requests":[],"api_requests":0,
        "source":"OpenAlex live primary_topic.id aggregate snapshot; not immutable historical truth"}
    def save():
        with tempfile.NamedTemporaryFile(mode="w",dir=output_dir,delete=False,prefix=".manifest_",suffix=".tmp") as handle:
            json.dump(manifest,handle,indent=2,default=list);handle.write("\n");temp=Path(handle.name)
        temp.replace(output_dir/"manifest.json")
    save();records=[]
    try:
        for spec in specs:
            response=client.request("/works",spec["params"])
            stamp=datetime.now(timezone.utc).isoformat()
            raw=response.content
            raw_name=f"raw/{spec['topic_id']}.json"
            target=output_dir/raw_name;target.parent.mkdir(exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=target.parent,delete=False,prefix=".response_",suffix=".tmp") as handle:
                handle.write(raw);temporary=Path(handle.name)
            temporary.replace(target)
            manifest["api_requests"]+=1
            entry={"topic_id":spec["topic_id"],"params":spec["params"],"retrieved_at_utc":stamp,
                   "raw_path":raw_name,"raw_sha256":hashlib.sha256(raw).hexdigest(),
                   "http_status":response.status_code}
            manifest["requests"].append(entry);save()
            counts,total=validate_year_aggregation(response.json(),list(range(2020,2026)))
            entry["meta_count"]=total;entry["year_groups"]=counts;save()
            for year,count in counts.items():
                records.append({"topic_id":spec["topic_id"],"year":int(year),"work_count":count,
                    "source_scope":"primary_non_retracted_AI_CV_corpus_primary_topic_id",
                    "retrieved_at_utc":stamp,"query_sha256":hashlib.sha256(
                        json.dumps(spec["params"],sort_keys=True).encode()).hexdigest()})
        frame=pd.DataFrame(records).sort_values(["topic_id","year"])
        if len(frame)!=84 or frame[["topic_id","year"]].duplicated().any():
            raise ValueError("Topic-year aggregate coverage incomplete")
        frame.to_csv(output_dir/"topic_year_population.csv",index=False)
        manifest["output_sha256"]=file_sha256(output_dir/"topic_year_population.csv")
        manifest["output_rows"]=len(frame);manifest["status"]="complete";manifest["complete"]=True
        manifest["completed_at_utc"]=datetime.now(timezone.utc).isoformat();save()
    except Exception as exc:
        manifest["failure_type"]=type(exc).__name__;manifest["failure_message"]=str(exc)[:300]
        save();raise
    return manifest


def verify(run_dir: Path) -> dict:
    manifest=json.loads((run_dir/"manifest.json").read_text())
    if manifest.get("status")!="complete" or not manifest.get("complete"):
        raise ValueError("Topic aggregate snapshot incomplete")
    for req in manifest["requests"]:
        if file_sha256(run_dir/req["raw_path"])!=req["raw_sha256"]:
            raise ValueError("Raw API response changed")
        counts,total=validate_year_aggregation(json.loads((run_dir/req["raw_path"]).read_text()),list(range(2020,2026)))
        if counts!=req["year_groups"] or total!=req["meta_count"]:
            raise ValueError("Topic aggregation validation changed")
    output=run_dir/"topic_year_population.csv"
    if file_sha256(output)!=manifest["output_sha256"] or len(pd.read_csv(output))!=84:
        raise ValueError("Topic population CSV changed")
    return {"valid":True,"queries":len(manifest["requests"]),"rows":84}


def main(argv: list[str]|None=None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest="command",required=True)
    make=sub.add_parser("collect");make.add_argument("--catalogue",type=Path,default=Path("config/phase6b_catalogue.yaml"))
    make.add_argument("--output-dir",type=Path,required=True)
    make.add_argument("--max-requests",type=int,default=14)
    check=sub.add_parser("verify");check.add_argument("run_dir",type=Path)
    args=parser.parse_args(argv)
    result=collect(args.catalogue,args.output_dir,max_requests=args.max_requests) if args.command=="collect" else verify(args.run_dir)
    print(json.dumps({"status":result.get("status","verified"),"api_requests":result.get("api_requests",result.get("queries")),
                      "rows":result.get("output_rows",result.get("rows"))},indent=2));return 0


if __name__=="__main__": raise SystemExit(main())
