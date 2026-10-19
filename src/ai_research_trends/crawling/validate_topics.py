"""CLI that verifies configured topic identifiers against live OpenAlex records."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ai_research_trends.config import load_config
from ai_research_trends.crawling.openalex_client import OpenAlexClient, utc_now
from ai_research_trends.env import load_project_env


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate configured OpenAlex topic IDs, names, and subfields."
    )
    parser.add_argument("--config", default="config/topics.yaml", help="Study YAML path")
    parser.add_argument(
        "--output", default="data/metadata/topic_validation.json", help="Validation report path"
    )
    return parser


def validate(config: dict, client: OpenAlexClient) -> dict:
    checks: list[dict] = []
    for category_slug, category in config["openalex_native_categories"].items():
        for expected in category.get("verified_topics", []):
            topic_id = expected["id"]
            actual = client.get_json(
                f"topics/{topic_id}",
                params={"select": "id,display_name,description,subfield,field,domain,updated_date"},
            )
            actual_id = actual.get("id", "").rstrip("/").split("/")[-1]
            actual_subfield = (actual.get("subfield") or {}).get("id", "").rstrip("/").split("/")[-1]
            expected_subfield = expected.get("subfield_id") or (
                (expected.get("hierarchy") or {}).get("subfield") or {}
            ).get("id")
            matches = {
                "id": actual_id == topic_id,
                "display_name": actual.get("display_name") == expected["display_name"],
                "subfield_id": actual_subfield == expected_subfield,
            }
            if "description" in expected:
                matches["description"] = actual.get("description") == expected["description"]
            for level in ("subfield", "field", "domain"):
                expected_level = ((expected.get("hierarchy") or {}).get(level) or {})
                if expected_level:
                    actual_level = actual.get(level) or {}
                    actual_level_id = str(actual_level.get("id", "")).rstrip("/").split("/")[-1]
                    matches[f"{level}_hierarchy"] = (
                        actual_level_id == str(expected_level.get("id"))
                        and actual_level.get("display_name") == expected_level.get("display_name")
                    )
            checks.append(
                {
                    "category": category_slug,
                    "expected": expected,
                    "actual": actual,
                    "matches": matches,
                    "valid": all(matches.values()),
                }
            )
    return {
        "schema_version": 1,
        "validated_at_utc": utc_now(),
        "all_valid": all(check["valid"] for check in checks),
        "checks": checks,
    }


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    load_project_env()
    config = load_config(args.config)
    report = validate(config, OpenAlexClient())
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"all_valid": report["all_valid"], "checks": len(report["checks"])}))
    return 0 if report["all_valid"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
