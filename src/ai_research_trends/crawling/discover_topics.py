"""Discover candidate OpenAlex topics and preserve the API evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ai_research_trends.config import load_config
from ai_research_trends.crawling.openalex_client import (
    OpenAlexClient,
    OpenAlexError,
    parse_list_response,
    utc_now,
)
from ai_research_trends.env import load_project_env


SEARCHES: dict[str, tuple[str, ...]] = {
    "natural_language_processing": ("natural language processing",),
    "large_language_models": ("large language models",),
    "computer_vision": ("computer vision",),
    "reinforcement_learning": ("reinforcement learning",),
    "explainable_ai": ("explainable artificial intelligence",),
    "multimodal_machine_learning_applications": ("multimodal machine learning",),
    "multimodal_ai": ("multimodal artificial intelligence",),
    "retrieval_augmented_generation": ("retrieval augmented generation",),
}

TOPIC_SELECT = "id,display_name,description,subfield,field,domain,works_count,updated_date"


def parse_topic_response(topic: Any) -> dict[str, Any]:
    """Extract research-relevant topic evidence from one API topic object."""
    if not isinstance(topic, dict):
        raise OpenAlexError("Topic result must be an object")
    topic_id = topic.get("id")
    display_name = topic.get("display_name")
    if not isinstance(topic_id, str) or not topic_id.rstrip("/").split("/")[-1].startswith("T"):
        raise OpenAlexError("Topic result has no valid OpenAlex topic ID")
    if not isinstance(display_name, str) or not display_name:
        raise OpenAlexError("Topic result has no display name")

    def hierarchy(name: str) -> dict[str, Any] | None:
        value = topic.get(name)
        if value is None:
            return None
        if not isinstance(value, dict):
            raise OpenAlexError(f"Topic {name} must be an object or null")
        return {"id": value.get("id"), "display_name": value.get("display_name")}

    return {
        "id": topic_id,
        "short_id": topic_id.rstrip("/").split("/")[-1],
        "display_name": display_name,
        "description": topic.get("description"),
        "subfield": hierarchy("subfield"),
        "field": hierarchy("field"),
        "domain": hierarchy("domain"),
        "works_count_at_discovery": topic.get("works_count"),
        "topic_updated_date": topic.get("updated_date"),
        "singleton_api_url": f"https://api.openalex.org/topics/{topic_id.rstrip('/').split('/')[-1]}",
    }


def _selected_topic_ids(config: dict[str, Any], category: str) -> set[str]:
    native = config["openalex_native_categories"].get(category, {})
    return set(native.get("topic_ids", []))


def discover_topics(
    client: OpenAlexClient,
    config: dict[str, Any],
    raw_root: Path,
    *,
    per_query: int = 10,
) -> dict[str, Any]:
    """Search topic text; returned candidates are never treated as a category census."""
    if not 1 <= per_query <= 100:
        raise ValueError("per_query must be between 1 and 100")
    run_id = datetime.now(timezone.utc).strftime("topic_discovery_%Y%m%dT%H%M%SZ")
    run_dir = raw_root / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    categories: dict[str, Any] = {}

    for category, queries in SEARCHES.items():
        selected_ids = _selected_topic_ids(config, category)
        candidates: dict[str, dict[str, Any]] = {}
        evidence: list[dict[str, Any]] = []
        for index, query in enumerate(queries, start=1):
            params = {"search": query, "per_page": per_query, "select": TOPIC_SELECT}
            response = client.request("topics", params)
            raw_path = run_dir / f"{category}_{index:02d}.json"
            raw_path.write_bytes(response.content)
            envelope = parse_list_response(response.json())
            for rank, raw_topic in enumerate(envelope.results, start=1):
                parsed = parse_topic_response(raw_topic)
                parsed.setdefault("search_hits", []).append({"query": query, "rank": rank})
                parsed["selected_in_config"] = parsed["short_id"] in selected_ids
                existing = candidates.get(parsed["short_id"])
                if existing:
                    existing["search_hits"].extend(parsed["search_hits"])
                else:
                    candidates[parsed["short_id"]] = parsed
            evidence.append(
                {
                    "query": query,
                    "request_url": response.url,
                    "raw_path": str(raw_path),
                    "sha256": hashlib.sha256(response.content).hexdigest(),
                    "api_result_count": envelope.meta.get("count"),
                    "returned_count": len(envelope.results),
                }
            )
        categories[category] = {
            "selected_topic_ids": sorted(selected_ids),
            "search_evidence": evidence,
            "candidates": list(candidates.values()),
            "warning": (
                "Text search returns candidates ranked by names/descriptions; it is not "
                "proof of exhaustive category membership. Empty selected IDs are intentional "
                "for custom text-derived technologies."
            ),
        }

    return {
        "schema_version": 2,
        "discovered_at_utc": utc_now(),
        "endpoint": "https://api.openalex.org/topics",
        "run_directory": str(run_dir),
        "categories": categories,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Search live OpenAlex topics and store candidate/evidence records."
    )
    parser.add_argument("--config", default="config/topics.yaml", help="Study YAML path")
    parser.add_argument(
        "--raw-root", default="data/raw/topic_discovery", help="Raw API evidence root"
    )
    parser.add_argument(
        "--output", default="data/metadata/topic_discovery.json", help="Discovery report JSON"
    )
    parser.add_argument("--per-query", type=int, default=10, help="Candidates per search")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    load_project_env()
    report = discover_topics(
        OpenAlexClient(), load_config(args.config), Path(args.raw_root), per_query=args.per_query
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"categories": len(report["categories"]), "output": str(output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
