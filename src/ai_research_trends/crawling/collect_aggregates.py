"""Collect year aggregates for the fixed corpus and OpenAlex-native topic lenses."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ai_research_trends.config import build_study_filter, load_config
from ai_research_trends.crawling.openalex_client import OpenAlexClient, utc_now
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
    population_filter = build_study_filter(study)
    specs: list[dict[str, Any]] = [
        {
            "name": "study_population",
            "analytical_layer": "population_frame",
            "method": "primary_subfield_frame",
            "params": {"filter": population_filter, "group_by": "publication_year"},
        }
    ]
    for slug, category in config["openalex_native_categories"].items():
        topic_ids = category.get("topic_ids", [])
        category_filter = f"{population_filter},topics.id:{'|'.join(topic_ids)}"
        specs.append(
            {
                "name": slug,
                "analytical_layer": "openalex_native",
                "method": "overlapping_openalex_topics_within_population_frame",
                "params": {"filter": category_filter, "group_by": "publication_year"},
            }
        )
    return specs


def collect(config: dict[str, Any], client: OpenAlexClient, raw_root: Path) -> dict[str, Any]:
    run_id = datetime.now(timezone.utc).strftime("aggregates_%Y%m%dT%H%M%SZ")
    run_dir = raw_root / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    outputs: list[dict[str, Any]] = []

    for spec in _query_specs(config):
        response = client.request("works", spec["params"])
        raw_path = run_dir / f"{spec['name']}.json"
        raw_path.write_bytes(response.content)
        payload = response.json()
        groups = payload.get("group_by", [])
        counts = {str(row["key"]): int(row["count"]) for row in groups}
        outputs.append(
            {
                "name": spec["name"],
                "analytical_layer": spec["analytical_layer"],
                "method": spec["method"],
                "query_parameters": spec["params"],
                "meta_count": payload.get("meta", {}).get("count"),
                "counts_by_year": counts,
                "raw_path": str(raw_path),
                "sha256": hashlib.sha256(response.content).hexdigest(),
            }
        )

    return {
        "schema_version": 2,
        "retrieved_at_utc": utc_now(),
        "run_directory": str(run_dir),
        "period_complete_calendar_years": [2020, 2021, 2022, 2023, 2024, 2025],
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
