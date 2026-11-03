"""Capacity-checked, training-only OpenAlex ML expansion planner."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import pandas as pd
import yaml

from ai_research_trends.config import FIXED_CORPUS, build_year_stratum_filter
from ai_research_trends.crawling.collect_stratified import _write_bytes_atomic, _write_json_atomic
from ai_research_trends.crawling.openalex_client import OpenAlexClient, parse_list_response, utc_now
from ai_research_trends.env import load_project_env
from ai_research_trends.preprocessing.validate_tables import file_sha256


def build_training_filter(year: int, topic_id: str | None) -> str:
    """Exact approved primary corpus narrowed to a historical year and optional primary topic."""
    if year not in range(2020, 2024): raise ValueError("ML acquisition must stay in 2020–2023")
    base = build_year_stratum_filter(FIXED_CORPUS, year)
    if topic_id is None: return base
    if not isinstance(topic_id, str) or not topic_id.startswith("T") or not topic_id[1:].isdigit():
        raise ValueError("Invalid short primary-topic ID")
    return f"{base},primary_topic.id:{topic_id}"


def apportion(weights: dict[int, int], total: int) -> dict[int, int]:
    """Largest-remainder allocation with zero allowed for small budgets."""
    if total < 0 or not weights or any(v < 0 for v in weights.values()):
        raise ValueError("Invalid apportionment inputs")
    mass = sum(weights.values())
    if total and not mass: raise ValueError("Cannot allocate against zero source capacity")
    if not mass: return {key: 0 for key in sorted(weights)}
    base = {key: total * size // mass for key, size in weights.items()}
    remaining = total - sum(base.values())
    for key in sorted(weights, key=lambda k: (-(total * weights[k] % mass), k))[:remaining]:
        base[key] += 1
    return {key: base[key] for key in sorted(base)}


def allocate_with_capacity(counts: dict[int, int], requested: int) -> tuple[dict[int, int], int]:
    """Allocate by population size; never request beyond observed source counts."""
    if requested < 0: raise ValueError("Negative requested quota")
    available = sum(counts.values())
    allocated = min(requested, available)
    if not available: return {year: 0 for year in sorted(counts)}, requested
    first = apportion(counts, allocated)
    result = {year: min(first[year], counts[year]) for year in counts}
    left = allocated - sum(result.values())
    while left:
        capacity = {year: counts[year]-result[year] for year in counts if counts[year]>result[year]}
        if not capacity: break
        increment = apportion(capacity, left)
        for year, value in increment.items(): result[year] += min(value, capacity[year])
        left = allocated - sum(result.values())
    return {year: result[year] for year in sorted(result)}, requested-sum(result.values())


def validate_collection_config(config: dict, catalogue: dict) -> None:
    if config.get("schema_version") != 1 or config.get("permitted_years") != [2020,2021,2022,2023]:
        raise ValueError("Collection must be restricted to all four training years")
    if config.get("primary_subfield_ids") != list(FIXED_CORPUS["primary_subfield_ids"]):
        raise ValueError("Approved primary subfield scope changed")
    if config.get("work_types") != list(FIXED_CORPUS["work_types"]) or config.get("is_retracted") is not False:
        raise ValueError("Approved work-type/retraction policy changed")
    if config.get("target_usable_per_selected_topic") not in range(1,1001):
        raise ValueError("Invalid training support target")
    if config.get("maximum_raw_records",0)>3000 or config.get("maximum_raw_records",0)<=0:
        raise ValueError("Phase 1 maximum raw-record budget must be 1–3000")
    if config.get("maximum_api_credits",0)>250 or config.get("maximum_api_credits",0)<=0:
        raise ValueError("API credit budget must be positive and <=250")
    if config.get("maximum_api_requests",0)>250 or config.get("maximum_api_requests",0)<=0:
        raise ValueError("API request budget must be positive and <=250")
    if config.get("per_page") not in range(1,101): raise ValueError("Unsupported per_page")
    if config.get("selected_raw_budget",0)<0 or config.get("outside_raw_quota",0)<0:
        raise ValueError("Negative raw quota")
    if config.get("selected_raw_budget",0)+config.get("outside_raw_quota",0)>config["maximum_raw_records"]:
        raise ValueError("Planned raw budgets exceed the collection maximum")
    outside=config.get("outside_sources")
    if not isinstance(outside,list) or sum(row.get("quota",-1) for row in outside)!=config["outside_raw_quota"]:
        raise ValueError("Outside-source quotas do not sum to outside_raw_quota")
    selected=set(catalogue["catalogue_b"])
    for source in outside:
        topic=source.get("primary_topic_id")
        if topic in selected or source.get("quota",0)<0:
            raise ValueError("Outside source overlaps selected catalogue or has negative quota")
        if topic is not None: build_training_filter(2020,topic)


def build_plan(config: dict, catalogue: dict, gap: pd.DataFrame,
               capacities: dict[str, dict[int, int]]) -> dict:
    validate_collection_config(config,catalogue)
    selected=catalogue["catalogue_b"]
    if set(gap.short_id)!=set(selected) or gap.short_id.duplicated().any():
        raise ValueError("Gap audit does not cover exactly the selected topics")
    target=config["target_usable_per_selected_topic"]
    gap_field=f"shortfall_{target}"; raw_field=f"estimated_raw_needed_{target}"
    if gap_field not in gap or raw_field not in gap:
        raise ValueError("Gap audit does not contain target estimates")
    raw_needed={row.short_id:int(getattr(row,raw_field)) for row in gap.itertuples()}
    if any(value<0 for value in raw_needed.values()): raise ValueError("Negative raw need")
    chosen_total=min(sum(raw_needed.values()),config["selected_raw_budget"])
    selected_quota=apportion(raw_needed,chosen_total) if chosen_total else dict.fromkeys(selected,0)
    strata=[]; shortfalls={}
    requests=[("selected",short,selected_quota[short]) for short in selected]
    requests += [(source["name"],source["primary_topic_id"],source["quota"])
                 for source in config["outside_sources"]]
    for source_name,topic,quota in requests:
        if quota==0: continue
        capacity_key=topic or "BROAD"
        years=capacities.get(capacity_key)
        if not isinstance(years,dict) or set(years)!=set(config["permitted_years"]):
            raise ValueError(f"Missing four-year capacity for {capacity_key}")
        allocation,missing=allocate_with_capacity(years,quota)
        if missing: shortfalls[f"{source_name}:{capacity_key}"]=missing
        for year,amount in allocation.items():
            if amount==0: continue
            filter_value=build_training_filter(year,topic)
            label=f"{source_name}:{capacity_key}:{year}"
            seed=int(hashlib.sha256(f"{config['seed']}:{label}".encode()).hexdigest()[:8],16)
            strata.append({"source_group":source_name,"topic_id":topic,"year":year,
                           "source_population_count":years[year],"planned_records":amount,
                           "filter":filter_value,"seed":seed,
                           "expected_pages":math.ceil(amount/config["per_page"])})
    total=sum(row["planned_records"] for row in strata)
    if total>config["maximum_raw_records"]:
        raise ValueError("Plan exceeds maximum raw records")
    if sum(row["expected_pages"] for row in strata)>config["maximum_api_requests"]:
        raise ValueError("Plan exceeds API request budget before resume probes")
    return {"schema_version":1,"status":"planned_not_executed",
            "created_at_utc":utc_now(),"corpus":"approved_ai_cv_primary_subfield_non_retracted",
            "training_years":config["permitted_years"],"selected_topics":selected,
            "target_usable_per_topic":target,"planned_raw_records":total,
            "maximum_raw_records":config["maximum_raw_records"],
            "maximum_api_credits":config["maximum_api_credits"],
            "maximum_api_requests":config["maximum_api_requests"],
            "per_page":config["per_page"],"base_seed":config["seed"],
            "planned_api_pages":sum(row["expected_pages"] for row in strata),
            "selected_planned_records":sum(row["planned_records"] for row in strata if row["source_group"]=="selected"),
            "outside_planned_records":sum(row["planned_records"] for row in strata if row["source_group"]!="selected"),
            "unfillable_source_shortfalls":shortfalls,"strata":strata}


def build_smoke_plan(plan: dict, *, per_stratum: int = 3) -> dict:
    """Create a separate tiny test plan across all historical years and source types."""
    if not 1 <= per_stratum <= 10:
        raise ValueError("Smoke size must be 1–10 per stratum")
    source_groups = {"selected": "T10028", "neighboring_privacy": "T10764",
                     "broader_ai_cv_sample": None}
    rows = []
    for source_group, topic_id in source_groups.items():
        matching = [row for row in plan["strata"]
                    if row["source_group"] == source_group and row["topic_id"] == topic_id]
        if {row["year"] for row in matching} != set(plan["training_years"]):
            raise ValueError(f"Smoke source does not cover four training years: {source_group}")
        for row in matching:
            if row["source_population_count"] < per_stratum:
                raise ValueError("Smoke source capacity too small")
            rows.append({**row, "planned_records": per_stratum, "expected_pages": 1})
    result = {**plan, "status": "smoke_planned_not_executed",
              "smoke_test": True, "strata": rows,
              "planned_raw_records": len(rows) * per_stratum,
              "planned_api_pages": len(rows),
              "selected_planned_records": 4 * per_stratum,
              "outside_planned_records": 8 * per_stratum}
    return result


def verify_plan_inputs(plan: dict, config_path: Path, catalogue_path: Path,
                       gap_path: Path, capacity_dir: Path) -> dict:
    """Rebuild quota allocations from their exact local, hashed source artifacts."""
    paths={"config_sha256":config_path,"catalogue_sha256":catalogue_path,
           "gap_sha256":gap_path,"capacity_manifest_sha256":capacity_dir/"manifest.json"}
    for field,path in paths.items():
        if file_sha256(path)!=plan.get(field):
            raise ValueError(f"Plan source checksum differs: {field}")
    config=yaml.safe_load(config_path.read_text())
    catalogue=yaml.safe_load(catalogue_path.read_text())
    manifest=json.loads((capacity_dir/"manifest.json").read_text())
    if manifest.get("status")!="complete": raise ValueError("Capacity queries are incomplete")
    capacities={}
    for row in manifest["queries"]:
        path=Path(row["path"])
        if file_sha256(path)!=row["sha256"]:
            raise ValueError(f"Capacity response checksum changed: {path}")
        envelope=parse_list_response(json.loads(path.read_bytes()))
        actual_groups={int(group["key"]):group["count"] for group in envelope.group_by}
        recorded={int(year):count for year,count in row["counts"].items()}
        if len(actual_groups)!=len(envelope.group_by) or actual_groups!=recorded or sum(recorded.values())!=envelope.meta.get("count"):
            raise ValueError(f"Capacity response groups differ from manifest: {path}")
        if row["source"] in capacities: raise ValueError("Duplicate capacity source")
        capacities[row["source"]]=recorded
    expected=build_plan(config,catalogue,pd.read_csv(gap_path),capacities)
    fields=("corpus","training_years","selected_topics","target_usable_per_topic",
            "planned_raw_records","planned_api_pages","selected_planned_records",
            "outside_planned_records","unfillable_source_shortfalls","strata")
    for field in fields:
        if plan.get(field)!=expected[field]: raise ValueError(f"Plan allocation changed: {field}")
    return {"valid":True,"source_capacity_queries":len(manifest["queries"]),
            "verified_strata":len(plan["strata"]),"planned_raw_records":plan["planned_raw_records"]}


def collect_capacities(config: dict, catalogue: dict, output_dir: Path) -> dict[str,dict[int,int]]:
    """Fetch complete four-year group counts, saving original response bytes."""
    if output_dir.exists(): raise FileExistsError("Source-count output already exists")
    load_project_env(); client=OpenAlexClient()
    if not client.api_key: raise ValueError("OPENALEX_API_KEY is required")
    output_dir.mkdir(parents=True,exist_ok=False)
    manifest_path=output_dir/"manifest.json"
    manifest={"status":"incomplete","started_at_utc":utc_now(),"queries":[],"errors":[]}
    _write_json_atomic(manifest_path,manifest)
    topic_ids=list(catalogue["catalogue_b"])+[row["primary_topic_id"] for row in config["outside_sources"]
                                                  if row["primary_topic_id"] is not None]+[None]
    capacities={}
    try:
        for topic in dict.fromkeys(topic_ids):
            key=topic or "BROAD"
            base=build_training_filter(2020,topic).replace(
                "to_publication_date:2020-12-31", "to_publication_date:2023-12-31")
            params={"filter":base,"group_by":"publication_year","per_page":100}
            response=client.request("works",params)
            payload=parse_list_response(response.json())
            counts={int(year):0 for year in config["permitted_years"]}
            seen=set()
            for group in payload.group_by:
                year=int(group["key"])
                count=group["count"]
                if year not in counts or year in seen or not isinstance(count,int) or count<0:
                    raise ValueError(f"Malformed year group for {key}")
                counts[year]=count
                seen.add(year)
            if sum(counts.values())!=payload.meta.get("count") or not payload.group_by:
                raise ValueError(f"Incomplete source capacity for {key}")
            path=output_dir/f"{key}.json"
            _write_bytes_atomic(path,response.content)
            manifest["queries"].append({"source":key,"params":params,"counts":counts,
                "meta_count":payload.meta.get("count"),"sha256":hashlib.sha256(response.content).hexdigest(),
                "path":str(path),"retrieved_at_utc":utc_now(),
                "credits_used":response.headers.get("X-RateLimit-Credits-Used"),
                "remaining":response.headers.get("X-RateLimit-Remaining")})
            capacities[key]=counts
            _write_json_atomic(manifest_path,manifest)
        manifest["status"]="complete";manifest["completed_at_utc"]=utc_now()
        _write_json_atomic(manifest_path,manifest)
        return capacities
    except Exception as exc:
        manifest["errors"].append({"type":type(exc).__name__,"message":str(exc),"at_utc":utc_now()})
        _write_json_atomic(manifest_path,manifest)
        raise


def main(argv: list[str]|None=None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config",type=Path,default=Path("config/finalization_phase1_collection.yaml"))
    parser.add_argument("--gap-csv",type=Path)
    parser.add_argument("--output",type=Path,default=Path("data/metadata/finalization_phase1_collection_plan.json"))
    parser.add_argument("--capacity-dir",type=Path)
    parser.add_argument("--execute-capacity-queries",action="store_true")
    parser.add_argument("--smoke-output",type=Path,
                        help="Also create a separate 36-work test plan; never overwrites production plan")
    parser.add_argument("--smoke-from-plan",type=Path,
                        help="Create only a smoke plan from a previously validated production plan")
    parser.add_argument("--verify-plan",type=Path,
                        help="Read-only rebuild of an existing plan against hashed gap and capacity inputs")
    args=parser.parse_args(argv)
    if args.verify_plan:
        if not args.gap_csv or not args.capacity_dir:
            parser.error("--verify-plan requires --gap-csv and --capacity-dir")
        config=yaml.safe_load(args.config.read_text())
        result=verify_plan_inputs(json.loads(args.verify_plan.read_text()),args.config,
                                  Path(config["catalogue"]),args.gap_csv,args.capacity_dir)
        print(json.dumps(result,indent=2))
        return 0
    if args.output.exists(): parser.error("Plan output exists; refusing overwrite")
    if args.smoke_from_plan:
        source=json.loads(args.smoke_from_plan.read_text())
        if source.get("status")!="planned_not_executed": parser.error("Source plan is not approved")
        args.output.parent.mkdir(parents=True,exist_ok=True)
        smoke=build_smoke_plan(source)
        args.output.write_text(json.dumps(smoke,indent=2)+"\n")
        print(json.dumps({"smoke_test":True,"planned_raw_records":smoke["planned_raw_records"],
                          "planned_api_pages":smoke["planned_api_pages"]},indent=2))
        return 0
    if not args.gap_csv: parser.error("--gap-csv is required unless --smoke-from-plan is used")
    if not args.capacity_dir: parser.error("--capacity-dir is required unless --smoke-from-plan is used")
    config=yaml.safe_load(args.config.read_text())
    catalogue_path=Path(config["catalogue"]);catalogue=yaml.safe_load(catalogue_path.read_text())
    validate_collection_config(config,catalogue)
    if args.execute_capacity_queries:
        capacities=collect_capacities(config,catalogue,args.capacity_dir)
    else:
        manifest=json.loads((args.capacity_dir/"manifest.json").read_text())
        if manifest.get("status")!="complete": raise ValueError("Source capacities are incomplete")
        capacities={row["source"]:{int(k):v for k,v in row["counts"].items()} for row in manifest["queries"]}
    gap=pd.read_csv(args.gap_csv)
    plan=build_plan(config,catalogue,gap,capacities)
    plan["config_sha256"]=file_sha256(args.config)
    plan["catalogue_sha256"]=file_sha256(catalogue_path)
    plan["gap_sha256"]=file_sha256(args.gap_csv)
    plan["capacity_manifest_sha256"]=file_sha256(args.capacity_dir/"manifest.json")
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(plan,indent=2)+"\n")
    if args.smoke_output:
        if args.smoke_output.exists(): parser.error("Smoke plan output exists; refusing overwrite")
        smoke=build_smoke_plan(plan)
        args.smoke_output.parent.mkdir(parents=True,exist_ok=True)
        args.smoke_output.write_text(json.dumps(smoke,indent=2)+"\n")
    print(json.dumps({"planned_raw_records":plan["planned_raw_records"],
                      "selected":plan["selected_planned_records"],
                      "outside":plan["outside_planned_records"],
                      "planned_api_pages":plan["planned_api_pages"],
                      "source_shortfalls":plan["unfillable_source_shortfalls"]},indent=2))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
