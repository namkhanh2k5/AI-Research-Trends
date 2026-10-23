"""Provenance-rich, overlapping membership in two independent category layers."""

from __future__ import annotations

from typing import Any

from ai_research_trends.preprocessing.categories import (
    classify_work,
    matches_rule_group,
    work_topic_ids,
)


def normalize_categories(
    source: dict[str, Any], work_id: str, config: dict[str, Any], config_sha256: str
) -> tuple[list[dict[str, Any]], str | None]:
    matches = classify_work(source, config)
    topic_ids = work_topic_ids(source)
    version = f"topics.yaml:sha256:{config_sha256}"
    rows: list[dict[str, Any]] = []
    for slug in sorted(matches.openalex_native):
        category = config["openalex_native_categories"][slug]
        matched = sorted(set(category["topic_ids"]) & topic_ids)
        if not matched:
            raise ValueError(f"{work_id} has native label without a matching topic ID")
        rows.append(
            {
                "work_id": work_id,
                "analytical_layer": "openalex_native",
                "category": slug,
                "matched_rule_or_topic_ids": matched,
                "classification_version": version,
            }
        )
    for slug in sorted(matches.custom_emerging):
        category = config["custom_emerging_technologies"][slug]
        rule_names = [
            rule["name"]
            for rule in category["rule_groups"]
            if matches_rule_group(source, rule)
        ]
        if not rule_names:
            raise ValueError(f"{work_id} has custom label without a matching rule")
        rows.append(
            {
                "work_id": work_id,
                "analytical_layer": "custom_emerging",
                "category": slug,
                "matched_rule_or_topic_ids": sorted(rule_names),
                "classification_version": version,
            }
        )
    return rows, matches.text_quarantine_reason
