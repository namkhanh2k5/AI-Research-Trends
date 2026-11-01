"""Bounded, read-only comparison of old and current OpenAlex training labels."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd
import yaml

from ai_research_trends.crawling.collect_stratified import _write_bytes_atomic, _write_json_atomic
from ai_research_trends.crawling.openalex_client import OpenAlexClient, canonical_work_id, utc_now
from ai_research_trends.env import load_project_env
from ai_research_trends.preprocessing.validate_tables import file_sha256


def deterministic_audit_ids(works: pd.DataFrame, selected: set[str], seed: int,
                            per_topic: int = 6, outside: int = 36) -> list[str]:
    historical = works.loc[works.publication_year.between(2020, 2023)]
    if historical.work_id.duplicated().any(): raise ValueError("Duplicate source Work ID")
    order = lambda work_id: hashlib.sha256(f"{seed}:{work_id}".encode()).hexdigest()
    chosen = []
    for topic in sorted(selected):
        ids = historical.loc[historical.primary_topic_id.eq(topic), "work_id"]
        if len(ids) < per_topic: raise ValueError(f"Insufficient historical works for {topic}")
        chosen.extend(sorted(ids, key=order)[:per_topic])
    outside_ids = historical.loc[~historical.primary_topic_id.isin(selected), "work_id"]
    if len(outside_ids) < outside: raise ValueError("Insufficient outside-catalogue works")
    chosen.extend(sorted(outside_ids, key=order)[:outside])
    if len(chosen) != len(set(chosen)): raise ValueError("Audit IDs are not unique")
    return chosen


def summarize_drift(comparisons: pd.DataFrame, selected: set[str]) -> dict:
    successful = comparisons.loc[comparisons.status.eq("retrieved")]
    changed = successful.loc[~successful.old_primary_topic.eq(successful.new_primary_topic)]
    selected_old = successful.loc[successful.old_primary_topic.isin(selected)]
    return {
        "checked": len(comparisons), "retrieved": len(successful),
        "unavailable": int(comparisons.status.eq("unavailable").sum()),
        "primary_agree": int(len(successful) - len(changed)),
        "primary_changed": len(changed),
        "primary_agreement_rate": float((len(successful)-len(changed))/len(successful)) if len(successful) else None,
        "top_three_set_agree": int(successful.top3_set_agree.sum()),
        "old_selected_retrieved": len(selected_old),
        "old_selected_primary_changed": int((selected_old.old_primary_topic!=selected_old.new_primary_topic).sum()),
        "old_selected_moved_outside_catalogue": int((~selected_old.new_primary_topic.isin(selected)).sum()),
        "old_title_missing": int(successful.old_title_missing.sum()),
        "new_title_missing": int(successful.new_title_missing.sum()),
        "old_abstract_missing": int(successful.old_abstract_missing.sum()),
        "new_abstract_missing": int(successful.new_abstract_missing.sum()),
    }


def verify_drift_evidence(manifest_path: Path) -> dict:
    """Verify all preserved singleton bodies and published aggregate checksums."""
    manifest=json.loads(manifest_path.read_text())
    if manifest.get("status")!="complete" or len(manifest.get("responses",[]))!=manifest.get("planned_ids"):
        raise ValueError("Label-drift audit is incomplete")
    for entry in manifest["responses"]:
        path=Path(entry["path"])
        if not path.is_file() or path.stat().st_size!=entry["bytes"] or file_sha256(path)!=entry["sha256"]:
            raise ValueError(f"Label-drift response integrity failed: {path}")
        if entry["status_code"]==200:
            returned=canonical_work_id(json.loads(path.read_bytes()).get("id",""))
            if returned!=entry["requested_work_id"]:
                raise ValueError(f"Label-drift response Work ID changed: {path}")
    for name,key in (("comparisons_private.csv","comparison_sha256"),
                     ("transitions.csv","transition_sha256"),("summary.json","summary_sha256")):
        if file_sha256(manifest_path.parent/name)!=manifest[key]:
            raise ValueError(f"Label-drift output checksum failed: {name}")
    return {"valid":True,"verified_responses":len(manifest["responses"]),
            "summary":manifest["summary"]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--processed-dir", type=Path, default=Path("data/processed/openalex_stratified/stratified_20261019T155909Z"))
    parser.add_argument("--catalogue", type=Path, default=Path("config/phase6b_catalogue.yaml"))
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--seed", type=int, default=20261101)
    parser.add_argument("--per-topic", type=int, default=6)
    parser.add_argument("--outside", type=int, default=36)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--verify-manifest",type=Path,
                        help="Read-only verification of a completed audit")
    args = parser.parse_args(argv)
    if args.verify_manifest:
        print(json.dumps(verify_drift_evidence(args.verify_manifest),indent=2))
        return 0
    if args.output_dir is None: parser.error("--output-dir is required unless --verify-manifest is used")
    if args.output_dir.exists(): parser.error("Output directory exists; choose a new versioned directory")
    config = yaml.safe_load(args.catalogue.read_text())
    selected = {f"https://openalex.org/{item}" for item in config["catalogue_b"]}
    works_path = args.processed_dir / "works.parquet"
    topics_path = args.processed_dir / "work_topics.parquet"
    works = pd.read_parquet(works_path)
    topics = pd.read_parquet(topics_path)
    ids = deterministic_audit_ids(works, selected, args.seed, args.per_topic, args.outside)
    if not args.execute:
        print(json.dumps({"planned_ids": len(ids), "training_years_only": True,
                          "api_requests": 0, "output_dir": str(args.output_dir)}))
        return 0
    load_project_env()
    client = OpenAlexClient()
    if not client.api_key: parser.error("OPENALEX_API_KEY is not configured")
    args.output_dir.mkdir(parents=True, exist_ok=False)
    raw_dir = args.output_dir / "responses"
    raw_dir.mkdir()
    manifest_path = args.output_dir / "manifest.json"
    manifest = {"status": "incomplete", "started_at_utc": utc_now(), "seed": args.seed,
                "planned_ids": len(ids), "requests_attempted": 0, "requests_succeeded": 0,
                "source_work_sha256": file_sha256(works_path),
                "source_topic_sha256": file_sha256(topics_path),
                "catalogue_sha256": file_sha256(args.catalogue),
                "request_kind": "OpenAlex works singleton; historical training IDs only",
                "responses": [], "errors": []}
    _write_json_atomic(manifest_path, manifest)
    old = works.set_index("work_id")
    old_topics = topics.loc[topics.work_id.isin(ids)].sort_values(["work_id", "topic_rank"])
    old_top3 = old_topics.groupby("work_id").topic_id.apply(lambda series: list(series.head(3))).to_dict()
    rows = []
    try:
        for work_id in ids:
            short = work_id.rsplit("/", 1)[-1]
            manifest["requests_attempted"] += 1
            response = client.request(f"works/{short}", allow_statuses=frozenset({404}))
            body = response.content
            path = raw_dir / f"{short}.json"
            _write_bytes_atomic(path, body)
            entry = {"requested_work_id": work_id, "status_code": response.status_code,
                     "retrieved_at_utc": utc_now(), "path": str(path),
                     "sha256": hashlib.sha256(body).hexdigest(), "bytes": len(body),
                     "rate_limit": {key: response.headers.get(key) for key in
                         ("X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Credits-Used")}}
            manifest["responses"].append(entry)
            if response.status_code == 404:
                rows.append({"work_id": work_id, "status": "unavailable"})
            else:
                payload = response.json()
                returned_id = canonical_work_id(payload.get("id", ""))
                if returned_id != work_id:
                    raise ValueError(f"Requested and returned Work IDs differ: {work_id}")
                primary = (payload.get("primary_topic") or {}).get("id")
                if not isinstance(primary, str):
                    raise ValueError(f"Current primary topic missing for {work_id}")
                current_top3 = [item.get("id") for item in (payload.get("topics") or [])[:3]]
                previous = old.loc[work_id]
                rows.append({"work_id": work_id, "status": "retrieved", "returned_work_id": returned_id,
                             "old_primary_topic": previous.primary_topic_id,
                             "new_primary_topic": primary,
                             "old_top3": json.dumps(old_top3.get(work_id, [])),
                             "new_top3": json.dumps(current_top3),
                             "top3_set_agree": set(old_top3.get(work_id, [])) == set(current_top3),
                             "old_title_missing": pd.isna(previous.title),
                             "new_title_missing": not bool((payload.get("title") or "").strip()),
                             "old_abstract_missing": pd.isna(previous.abstract),
                             "new_abstract_missing": not bool(payload.get("abstract_inverted_index")),
                             "old_subfield": previous.primary_subfield_id,
                             "new_subfield": ((payload.get("primary_topic") or {}).get("subfield") or {}).get("id")})
                manifest["requests_succeeded"] += 1
            _write_json_atomic(manifest_path, manifest)
        frame = pd.DataFrame(rows)
        comparison = args.output_dir / "comparisons_private.csv"
        frame.to_csv(comparison, index=False)
        summary = summarize_drift(frame, selected)
        transitions = (frame.loc[frame.status.eq("retrieved")]
                       .groupby(["old_primary_topic", "new_primary_topic"]).size()
                       .rename("works").reset_index().sort_values("works", ascending=False))
        transitions_path = args.output_dir / "transitions.csv"
        transitions.to_csv(transitions_path, index=False)
        summary_path = args.output_dir / "summary.json"
        summary_path.write_text(json.dumps(summary, indent=2) + "\n")
        manifest.update({"status": "complete", "completed_at_utc": utc_now(),
                         "comparison_sha256": file_sha256(comparison),
                         "transition_sha256": file_sha256(transitions_path),
                         "summary_sha256": file_sha256(summary_path), "summary": summary})
        _write_json_atomic(manifest_path, manifest)
        print(json.dumps(summary, indent=2))
        return 0
    except Exception as exc:
        manifest["errors"].append({"at_utc": utc_now(), "type": type(exc).__name__, "message": str(exc)})
        _write_json_atomic(manifest_path, manifest)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
