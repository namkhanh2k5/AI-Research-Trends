"""Bounded checkpointed collection of historical topic-enriched ML records."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import yaml

from ai_research_trends.config import FIXED_CORPUS, validate_corpus_work
from ai_research_trends.crawling.collect_stratified import (
    _safe_resume_manifest, _write_bytes_atomic, _write_json_atomic, _write_jsonl_atomic,
)
from ai_research_trends.crawling.ml_expansion_plan import build_training_filter, validate_collection_config
from ai_research_trends.crawling.openalex_client import (
    OpenAlexClient, canonical_work_id, utc_now, validate_sample_page,
)
from ai_research_trends.env import load_project_env
from ai_research_trends.preprocessing.validate_tables import file_sha256


def validate_expansion_plan(plan: dict, config: dict, catalogue: dict) -> None:
    validate_collection_config(config,catalogue)
    if plan.get("schema_version")!=1 or plan.get("corpus")!="approved_ai_cv_primary_subfield_non_retracted":
        raise ValueError("Unapproved expansion plan")
    if plan.get("training_years")!=[2020,2021,2022,2023]:
        raise ValueError("Plan may only use historical training years")
    if plan.get("selected_topics")!=catalogue["catalogue_b"]:
        raise ValueError("Selected topic catalogue does not match config")
    if plan.get("config_sha256") is None or plan.get("catalogue_sha256") is None:
        raise ValueError("Plan lacks source checksums")
    if plan.get("per_page")!=config["per_page"] or plan.get("base_seed")!=config["seed"]:
        raise ValueError("Page size or seed differs from config")
    if plan.get("maximum_api_credits")!=config["maximum_api_credits"] or plan.get("maximum_api_requests")!=config["maximum_api_requests"]:
        raise ValueError("Plan budget differs from config")
    strata=plan.get("strata")
    if not isinstance(strata,list) or not strata: raise ValueError("Empty plan")
    keys=set()
    outside_sources={row["name"]:row["primary_topic_id"] for row in config["outside_sources"]}
    for row in strata:
        year=row.get("year");topic=row.get("topic_id")
        if row.get("source_group") not in {"selected",*outside_sources}:
            raise ValueError("Unknown source group")
        if row["source_group"]!="selected" and topic!=outside_sources[row["source_group"]]:
            raise ValueError("Outside source/topic mapping changed")
        if row.get("filter")!=build_training_filter(year,topic):
            raise ValueError("Stratum filter differs from approved historical corpus")
        amount=row.get("planned_records")
        if not isinstance(amount,int) or isinstance(amount,bool) or not 1<=amount<=row.get("source_population_count",0):
            raise ValueError("Invalid or unsupported stratum quota")
        label=f"{row['source_group']}:{topic or 'BROAD'}:{year}"
        expected_seed=int(hashlib.sha256(f"{config['seed']}:{label}".encode()).hexdigest()[:8],16)
        if row.get("seed")!=expected_seed or row.get("expected_pages")!=math.ceil(amount/config["per_page"]):
            raise ValueError("Stratum seed/page allocation changed")
        if label in keys: raise ValueError("Duplicate collection stratum")
        keys.add(label)
        if row["source_group"]=="selected" and topic not in catalogue["catalogue_b"]:
            raise ValueError("Unselected topic placed in selected stratum")
        if row["source_group"]!="selected" and topic in catalogue["catalogue_b"]:
            raise ValueError("Selected topic placed in outside stratum")
    if sum(row["planned_records"] for row in strata)!=plan.get("planned_raw_records"):
        raise ValueError("Plan raw-record total changed")
    if sum(row["planned_records"] for row in strata if row["source_group"]=="selected")!=plan.get("selected_planned_records"):
        raise ValueError("Selected-record total changed")
    if sum(row["planned_records"] for row in strata if row["source_group"]!="selected")!=plan.get("outside_planned_records"):
        raise ValueError("Outside-record total changed")
    if sum(row["expected_pages"] for row in strata)!=plan.get("planned_api_pages"):
        raise ValueError("Plan page total changed")
    if plan["planned_raw_records"]>min(plan["maximum_raw_records"],3000):
        raise ValueError("Plan exceeds 3,000-record cap")
    if plan["planned_api_pages"]>plan["maximum_api_requests"]:
        raise ValueError("Plan request budget insufficient")


def validate_page(rows: list[dict], stratum: dict) -> list[str]:
    ids=[]
    for work in rows:
        work_id=canonical_work_id(work.get("id",""))
        result=validate_corpus_work(work,FIXED_CORPUS,require_non_retracted=True)
        if not result.valid or work.get("publication_year")!=stratum["year"]:
            raise ValueError(f"Out-of-corpus work {work_id}: {result.errors}")
        if stratum["topic_id"] is not None and (work.get("primary_topic") or {}).get("id")!=f"https://openalex.org/{stratum['topic_id']}":
            raise ValueError(f"Wrong primary topic in stratum: {work_id}")
        ids.append(work_id)
    if len(ids)!=len(set(ids)): raise ValueError("Duplicate Work ID within sample page")
    return ids


def _page_params(stratum: dict, page: int, per_page: int) -> dict:
    return {"filter":stratum["filter"],"sample":stratum["planned_records"],
            "seed":stratum["seed"],"per_page":per_page,"page":page}


def _budgeted_request(client: OpenAlexClient, manifest: dict, manifest_path: Path, params: dict):
    if manifest["api_requests_attempted"]>=manifest["maximum_api_requests"]:
        raise RuntimeError("Configured API request cap reached")
    if manifest["api_credits_observed"]>=manifest["maximum_api_credits"]:
        raise RuntimeError("Configured API credit cap reached")
    remaining=manifest.get("last_daily_credits_remaining")
    if remaining is not None and remaining<5:
        raise RuntimeError("Observed OpenAlex daily credits are low; stopping safely")
    manifest["api_requests_attempted"]+=1
    _write_json_atomic(manifest_path,manifest)
    response=client.request("works",params)
    manifest["api_requests_succeeded"]+=1
    used=response.headers.get("X-RateLimit-Credits-Used")
    remaining=response.headers.get("X-RateLimit-Remaining")
    if used is not None: manifest["api_credits_observed"]+=int(used)
    if remaining is not None: manifest["last_daily_credits_remaining"]=int(remaining)
    if manifest["api_credits_observed"]>manifest["maximum_api_credits"]:
        raise RuntimeError("Observed API credit cap exceeded unexpectedly")
    return response


def _checkpoint_pages(run_dir: Path, manifest: dict, client: OpenAlexClient,
                      manifest_path: Path) -> None:
    """Verify every saved page and re-fetch its IDs before mixing new pages."""
    referenced=set()
    probe_dir=run_dir/"resume_probes"
    for index,stratum in enumerate(manifest["strata"]):
        for page in stratum["pages"]:
            path=run_dir/f"stratum_{index:03d}"/f"page_{page['page_number']:03d}.json"
            referenced.add(path.resolve())
            if not path.is_file() or file_sha256(path)!=page["sha256"]:
                raise ValueError(f"Checkpoint page missing or changed: {path}")
            original=json.loads(path.read_bytes())
            stored=validate_sample_page(original,requested_records=stratum["planned_records"],
                page_number=page["page_number"],per_page=manifest["per_page"])
            if validate_page(stored.results,stratum)!=page["work_ids"]:
                raise ValueError("Checkpoint Work IDs disagree with saved page")
    orphan=[path for path in run_dir.glob("stratum_*/page_*.json") if path.resolve() not in referenced]
    partial=list(run_dir.glob("stratum_*/*.part"))
    if orphan or partial:
        raise ValueError(f"Uncheckpointed raw evidence present; preserve and inspect: {len(orphan)} orphan, {len(partial)} partial")
    for index,stratum in enumerate(manifest["strata"]):
        for page in stratum["pages"]:
            params=_page_params(stratum,page["page_number"],manifest["per_page"])
            response=_budgeted_request(client,manifest,manifest_path,params)
            probe_dir.mkdir(exist_ok=True)
            probe=probe_dir/f"probe_resume{manifest['resume_attempts']:03d}_{index:03d}_{page['page_number']:03d}.json"
            if probe.exists(): raise FileExistsError(f"Resume probe already exists: {probe}")
            _write_bytes_atomic(probe,response.content)
            envelope=validate_sample_page(response.json(),requested_records=stratum["planned_records"],
                page_number=page["page_number"],per_page=manifest["per_page"])
            current=validate_page(envelope.results,stratum)
            result={"original_page_sha256":page["sha256"],"probe_sha256":file_sha256(probe),
                    "probe_path":str(probe),"stratum_index":index,"page_number":page["page_number"],
                    "ordered_id_match":current==page["work_ids"],"checked_at_utc":utc_now()}
            manifest["resume_probes"].append(result)
            _write_json_atomic(manifest_path,manifest)
            if not result["ordered_id_match"]:
                raise ValueError("Seeded sample membership changed on resume; raw evidence preserved")


def _finalize(run_dir: Path, interim_dir: Path, manifest: dict) -> None:
    raw_rows=[]; unique={}; repeats=0
    for index,stratum in enumerate(manifest["strata"]):
        for page in sorted(stratum["pages"],key=lambda row:row["page_number"]):
            path=run_dir/f"stratum_{index:03d}"/f"page_{page['page_number']:03d}.json"
            if file_sha256(path)!=page["sha256"]: raise ValueError("Raw page checksum changed")
            payload=json.loads(path.read_bytes())
            envelope=validate_sample_page(payload,requested_records=stratum["planned_records"],
                page_number=page["page_number"],per_page=manifest["per_page"])
            if validate_page(envelope.results,stratum)!=page["work_ids"]:
                raise ValueError("Raw page ID sequence changed")
            for work in envelope.results:
                wid=canonical_work_id(work["id"])
                raw_rows.append(work)
                if wid in unique:
                    repeats+=1
                    continue
                unique[wid]={"work":work,"provenance":{
                    "dataset_origin":"targeted_ml_expansion","collection_run_id":manifest["run_id"],
                    "retrieved_at_utc":page["retrieved_at_utc"],"source_query":page["params"],
                    "sampling_strategy":"OpenAlex seeded sample within topic/year stratum; nonrepresentative",
                    "topic_snapshot_version":manifest["started_at_utc"],
                    "original_or_new":"newly_acquired_record",
                    "intended_ml_role":"candidate_training_only",
                    "source_group":stratum["source_group"]}}
    if len(raw_rows)!=manifest["planned_raw_records"]:
        raise ValueError("Collected records do not match planned raw count")
    raw_jsonl=run_dir/"works.jsonl";interim_jsonl=interim_dir/"records.jsonl"
    if raw_jsonl.exists() or interim_jsonl.exists(): raise FileExistsError("Final output exists")
    _write_jsonl_atomic(raw_jsonl,raw_rows)
    _write_jsonl_atomic(interim_jsonl,list(unique.values()))
    manifest.update({"status":"complete","complete":True,"completed_at_utc":utc_now(),
        "raw_records":len(raw_rows),"unique_collected_work_ids":len(unique),
        "duplicate_ids_across_strata":repeats,
        "raw_jsonl_sha256":file_sha256(raw_jsonl),"raw_jsonl_bytes":raw_jsonl.stat().st_size,
        "interim_jsonl_sha256":file_sha256(interim_jsonl),"interim_jsonl_bytes":interim_jsonl.stat().st_size,
        "raw_jsonl_path":str(raw_jsonl),"interim_jsonl_path":str(interim_jsonl),
        "retry_count":"not exposed by existing OpenAlex client"})


def collect(plan_path: Path, config_path: Path, raw_root: Path, interim_root: Path,
            resume_manifest: Path | None = None, client: OpenAlexClient | None = None) -> dict:
    plan=json.loads(plan_path.read_text())
    config=yaml.safe_load(config_path.read_text())
    catalogue=yaml.safe_load(Path(config["catalogue"]).read_text())
    validate_expansion_plan(plan,config,catalogue)
    if plan["config_sha256"]!=file_sha256(config_path) or plan["catalogue_sha256"]!=file_sha256(Path(config["catalogue"])):
        raise ValueError("Plan/config/catalogue checksum mismatch")
    client=client or OpenAlexClient()
    if not client.api_key: raise ValueError("OPENALEX_API_KEY is required")
    raw_root.mkdir(parents=True,exist_ok=True);interim_root.mkdir(parents=True,exist_ok=True)
    if resume_manifest:
        manifest_path=_safe_resume_manifest(resume_manifest,raw_root)
        manifest=json.loads(manifest_path.read_text())
        if manifest.get("complete") is True: raise ValueError("Completed run is immutable")
        if manifest.get("plan_sha256")!=file_sha256(plan_path): raise ValueError("Resume plan checksum mismatch")
        run_dir=manifest_path.parent;interim_dir=interim_root/run_dir.name
        if not interim_dir.is_dir(): raise ValueError("Missing interim run directory")
        manifest["resume_attempts"]+=1
        _write_json_atomic(manifest_path,manifest)
    else:
        run_id=f"ml_expansion_{utc_now().replace('-','').replace(':','').replace('Z','Z')}"
        run_dir=raw_root/run_id;interim_dir=interim_root/run_id
        if run_dir.exists() or interim_dir.exists(): raise FileExistsError("Run directory already exists")
        run_dir.mkdir();interim_dir.mkdir()
        manifest_path=run_dir/"manifest.json"
        manifest={"status":"incomplete","complete":False,"run_id":run_id,
            "started_at_utc":utc_now(),"endpoint":"https://api.openalex.org/works",
            "plan_sha256":file_sha256(plan_path),"config_sha256":file_sha256(config_path),
            "per_page":plan["per_page"],"maximum_api_requests":plan["maximum_api_requests"],
            "maximum_api_credits":plan["maximum_api_credits"],
            "planned_raw_records":plan["planned_raw_records"],"api_requests_attempted":0,
            "api_requests_succeeded":0,"api_credits_observed":0,"last_daily_credits_remaining":None,
            "resume_attempts":0,"resume_probes":[],"errors":[],
            "strata":[{**row,"pages":[]} for row in plan["strata"]]}
        _write_json_atomic(manifest_path,manifest)
    try:
        if resume_manifest:
            _checkpoint_pages(run_dir,manifest,client,manifest_path)
        for index,stratum in enumerate(manifest["strata"]):
            folder=run_dir/f"stratum_{index:03d}";folder.mkdir(exist_ok=True)
            complete={page["page_number"] for page in stratum["pages"]}
            for page_number in range(1,stratum["expected_pages"]+1):
                if page_number in complete: continue
                params=_page_params(stratum,page_number,manifest["per_page"])
                response=_budgeted_request(client,manifest,manifest_path,params)
                envelope=validate_sample_page(response.json(),requested_records=stratum["planned_records"],
                    page_number=page_number,per_page=manifest["per_page"])
                ids=validate_page(envelope.results,stratum)
                path=folder/f"page_{page_number:03d}.json"
                _write_bytes_atomic(path,response.content)
                stratum["pages"].append({"page_number":page_number,"params":params,
                    "sha256":file_sha256(path),"bytes":path.stat().st_size,
                    "work_ids":ids,"retrieved_at_utc":utc_now(),
                    "rate_limit_remaining":response.headers.get("X-RateLimit-Remaining"),
                    "credits_used":response.headers.get("X-RateLimit-Credits-Used")})
                _write_json_atomic(manifest_path,manifest)
        _finalize(run_dir,interim_dir,manifest)
        _write_json_atomic(manifest_path,manifest)
        return manifest
    except Exception as exc:
        manifest["status"]="incomplete";manifest["complete"]=False
        manifest["errors"].append({"at_utc":utc_now(),"type":type(exc).__name__,"message":str(exc)})
        _write_json_atomic(manifest_path,manifest)
        raise


def main(argv: list[str]|None=None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan",type=Path,default=Path("data/metadata/finalization_phase1_collection_plan.json"))
    parser.add_argument("--config",type=Path,default=Path("config/finalization_phase1_collection.yaml"))
    parser.add_argument("--raw-root",type=Path,default=Path("data/raw/openalex_ml_expansion"))
    parser.add_argument("--interim-root",type=Path,default=Path("data/interim/openalex_ml_expansion"))
    parser.add_argument("--resume-manifest",type=Path)
    parser.add_argument("--execute",action="store_true")
    args=parser.parse_args(argv)
    plan=json.loads(args.plan.read_text());config=yaml.safe_load(args.config.read_text())
    catalogue=yaml.safe_load(Path(config["catalogue"]).read_text())
    validate_expansion_plan(plan,config,catalogue)
    if not args.execute:
        print(json.dumps({"planned_raw_records":plan["planned_raw_records"],
            "planned_api_pages":plan["planned_api_pages"],"training_years":plan["training_years"],
            "would_collect":False,"raw_root":str(args.raw_root),"interim_root":str(args.interim_root)},indent=2))
        return 0
    load_project_env()
    result=collect(args.plan,args.config,args.raw_root,args.interim_root,args.resume_manifest)
    print(json.dumps({"status":result["status"],"run_id":result["run_id"],
                      "raw_records":result["raw_records"],
                      "unique_collected_work_ids":result["unique_collected_work_ids"],
                      "api_requests_attempted":result["api_requests_attempted"],
                      "api_credits_observed":result["api_credits_observed"]},indent=2))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
