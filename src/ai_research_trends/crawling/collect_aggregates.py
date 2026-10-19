"""Collect year aggregates for the fixed corpus and OpenAlex-native topic lenses."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ai_research_trends.config import build_study_filter, load_config
from ai_research_trends.crawling.openalex_client import (
    OpenAlexClient,
    OpenAlexError,
    parse_list_response,
    utc_now,
)
from ai_research_trends.env import load_project_env


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Collect OpenAlex group_by=publication_year counts. Category counts overlap "
            "and must never be summed as a corpus total."
        )
    )
    parser.add_argument("--config", default="config/topics.yaml", help="Study YAML path")
    parser.add_argument("--raw-root", default="data/raw/openalex_aggregates", help="Raw root")
    parser.add_argument(
        "--output", default="data/metadata/population_counts.json", help="Derived count table"
    )
    return parser


def _query_specs(config: dict[str, Any]) -> list[dict[str, Any]]:
    study = config["study"]
    filters = {
        "all": build_study_filter(study, retraction_scope="all"),
        "primary_non_retracted": build_study_filter(
            study, retraction_scope="non_retracted"
        ),
    }
    specs: list[dict[str, Any]] = []
    for scope, population_filter in filters.items():
        specs.append(
            {
                "name": f"study_population_{scope}",
                "analytical_layer": "population_frame",
                "estimand_role": "primary" if scope == "primary_non_retracted" else "sensitivity",
                "retraction_scope": scope,
                "method": "primary_subfield_frame",
                "params": {"filter": population_filter, "group_by": "publication_year"},
            }
        )
    for slug, category in config["openalex_native_categories"].items():
        topic_ids = category.get("topic_ids", [])
        for scope, population_filter in filters.items():
            category_filter = f"{population_filter},topics.id:{'|'.join(topic_ids)}"
            specs.append(
                {
                    "name": f"{slug}_{scope}",
                    "analytical_layer": "openalex_native",
                    "estimand_role": (
                        "primary" if scope == "primary_non_retracted" else "sensitivity"
                    ),
                    "retraction_scope": scope,
                    "method": "overlapping_openalex_topics_within_population_frame",
                    "params": {"filter": category_filter, "group_by": "publication_year"},
                }
            )
    return specs


def validate_year_aggregation(
    payload: Any, expected_years: list[int]
) -> tuple[dict[str, int], int]:
    """Reject incomplete or internally inconsistent OpenAlex year groups."""
    envelope = parse_list_response(payload)
    meta_count = envelope.meta.get("count")
    if not isinstance(meta_count, int) or isinstance(meta_count, bool) or meta_count < 0:
        raise OpenAlexError("Aggregation meta.count must be a non-negative integer")

    counts: dict[str, int] = {}
    for index, row in enumerate(envelope.group_by):
        key = row.get("key")
        count = row.get("count")
        if not isinstance(key, (str, int)) or isinstance(key, bool):
            raise OpenAlexError(f"Aggregation group {index} has an invalid year key")
        year = str(key)
        if year in counts:
            raise OpenAlexError(f"Aggregation contains duplicate year key {year}")
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            raise OpenAlexError(f"Aggregation year {year} has an invalid count")
        counts[year] = count

    expected = {str(year) for year in expected_years}
    actual = set(counts)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise OpenAlexError(
            f"Aggregation year groups are incomplete: missing={missing}, extra={extra}"
        )
    if sum(counts.values()) != meta_count:
        raise OpenAlexError(
            "Aggregation counts do not sum to meta.count: "
            f"groups={sum(counts.values())}, meta.count={meta_count}"
        )
    return dict(sorted(counts.items())), meta_count


def _write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def collect(config: dict[str, Any], client: OpenAlexClient, raw_root: Path) -> dict[str, Any]:
    run_id = datetime.now(timezone.utc).strftime("aggregates_%Y%m%dT%H%M%SZ")
    run_dir = raw_root / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    outputs: list[dict[str, Any]] = []
    expected_years = list(range(2020, 2026))
    specs = _query_specs(config)
    manifest_path = run_dir / "manifest.json"
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "run_id": run_id,
        "created_at_utc": utc_now(),
        "status": "running",
        "complete": False,
        "expected_query_count": len(specs),
        "completed_queries": [],
        "failed_query": None,
    }
    _write_json_atomic(manifest_path, manifest)

    try:
        for spec in specs:
            if not re.fullmatch(r"[a-z0-9_]+", spec["name"]):
                raise ValueError(f"Unsafe aggregate query name: {spec['name']!r}")
            response = client.request("works", spec["params"])
            raw_path = run_dir / f"{spec['name']}.json"
            raw_path.write_bytes(response.content)
            payload = response.json()
            counts, meta_count = validate_year_aggregation(payload, expected_years)
            outputs.append(
                {
                    "name": spec["name"],
                    "analytical_layer": spec["analytical_layer"],
                    "estimand_role": spec["estimand_role"],
                    "retraction_scope": spec["retraction_scope"],
                    "method": spec["method"],
                    "query_parameters": spec["params"],
                    "meta_count": meta_count,
                    "counts_by_year": counts,
                    "raw_path": str(raw_path),
                    "sha256": hashlib.sha256(response.content).hexdigest(),
                }
            )
            manifest["completed_queries"].append(spec["name"])
            _write_json_atomic(manifest_path, manifest)
    except Exception as exc:
        manifest.update(
            {
                "status": "failed",
                "complete": False,
                "failed_at_utc": utc_now(),
                "failed_query": spec["name"] if "spec" in locals() else None,
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
        )
        _write_json_atomic(manifest_path, manifest)
        raise

    manifest.update({"status": "complete", "complete": True, "completed_at_utc": utc_now()})
    _write_json_atomic(manifest_path, manifest)

    return {
        "schema_version": 3,
        "retrieved_at_utc": utc_now(),
        "run_directory": str(run_dir),
        "run_manifest": str(manifest_path),
        "complete": True,
        "period_complete_calendar_years": expected_years,
        "category_counts_overlap": True,
        "warning": (
            "OpenAlex-native category counts overlap and must not be summed. Custom "
            "text-derived technologies are deliberately excluded from this aggregate file."
        ),
        "queries": outputs,
    }


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    load_project_env()
    report = collect(load_config(args.config), OpenAlexClient(), Path(args.raw_root))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({item["name"]: item["meta_count"] for item in report["queries"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
