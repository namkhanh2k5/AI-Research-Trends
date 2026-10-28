"""Bounded official OpenAlex topic-metadata evidence for Phase 6B scope review."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from ai_research_trends.crawling.discover_topics import parse_topic_response
from ai_research_trends.crawling.openalex_client import OpenAlexClient
from ai_research_trends.env import load_project_env
from ai_research_trends.preprocessing.validate_tables import file_sha256


NUMERICALLY_ELIGIBLE = (
    "T10036", "T10664", "T10020", "T10764", "T10028", "T10052", "T10862",
    "T10682", "T10462", "T10888", "T10100", "T10775", "T10331", "T10181",
    "T10201", "T11307", "T11276", "T10812", "T11689", "T12026",
)


def parse_verified_topic(payload: dict, expected_id: str) -> dict:
    parsed = parse_topic_response(payload)
    if parsed["short_id"] != expected_id:
        raise ValueError(f"Topic response mismatch: requested {expected_id}, got {parsed['short_id']}")
    if not isinstance(parsed["description"], str) or not parsed["description"].strip():
        raise ValueError(f"Topic {expected_id} has no official description")
    subfield = parsed.get("subfield") or {}
    return {"topic_id":parsed["id"],"short_id":expected_id,"name":parsed["display_name"],
            "description":parsed["description"],"subfield_id":str(subfield.get("id") or "").split("/")[-1],
            "source_url":parsed["singleton_api_url"],"updated_date":parsed["topic_updated_date"]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--ids", nargs="+", default=list(NUMERICALLY_ELIGIBLE))
    args = parser.parse_args(argv)
    if args.output_dir.exists():
        parser.error("Output directory already exists; choose a fresh versioned directory")
    if len(args.ids) != len(set(args.ids)) or any(i not in NUMERICALLY_ELIGIBLE for i in args.ids):
        parser.error("IDs must be unique members of the 20 pre-2025 support-eligible candidates")
    load_project_env()
    client = OpenAlexClient()
    args.output_dir.mkdir(parents=True, exist_ok=False)
    rows = []
    evidence = []
    try:
        for topic_id in args.ids:
            response = client.request(f"topics/{topic_id}",
                                      {"select":"id,display_name,description,subfield,updated_date"})
            body = response.content
            parsed = parse_verified_topic(response.json(), topic_id)
            path = args.output_dir / f"{topic_id}.json"
            path.write_bytes(body)  # Original response bytes; never rewritten.
            rows.append(parsed)
            evidence.append({"topic_id":topic_id,"url":response.url,"retrieved_at_utc":
                datetime.now(timezone.utc).isoformat(),"sha256":hashlib.sha256(body).hexdigest(),
                "bytes":len(body),"path":str(path)})
    except Exception:
        (args.output_dir / "incomplete_evidence.json").write_text(json.dumps(evidence,indent=2)+"\n")
        raise
    output = args.output_dir / "topics.csv"
    pd.DataFrame(rows).sort_values("short_id").to_csv(output,index=False)
    manifest = {"status":"complete","source":"OpenAlex topics singleton endpoint",
                "retrieved_at_utc":datetime.now(timezone.utc).isoformat(),
                "rows":len(rows),"topics_csv_sha256":file_sha256(output),"responses":evidence}
    (args.output_dir / "manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
    print(json.dumps({"rows":len(rows),"topics_csv_sha256":manifest["topics_csv_sha256"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
