"""One unique work/topic row per OpenAlex assigned topic."""

from __future__ import annotations

from typing import Any

from ai_research_trends.preprocessing.common import (
    clean_text,
    entity_id,
    nonnegative_float,
    taxonomy_id,
)


def normalize_topics(source: dict[str, Any], work_id: str) -> list[dict[str, Any]]:
    topics = source.get("topics")
    if topics is None:
        return []
    if not isinstance(topics, list):
        raise ValueError(f"{work_id} topics must be a list or null")
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for rank, topic in enumerate(topics, start=1):
        if not isinstance(topic, dict):
            raise ValueError(f"{work_id} contains a malformed topic object")
        topic_id = entity_id(topic.get("id"), "T", nullable=False)
        if topic_id in seen:
            continue
        seen.add(topic_id)
        score = nonnegative_float(topic.get("score"), "topic_score")
        if score is not None and score > 1:
            raise ValueError(f"{work_id} topic score exceeds 1")
        rows.append(
            {
                "work_id": work_id,
                "topic_id": topic_id,
                "topic_name": clean_text(topic.get("display_name")),
                "topic_rank": rank,
                "topic_score": score,
                "subfield_id": taxonomy_id((topic.get("subfield") or {}).get("id"), "subfields"),
                "field_id": taxonomy_id((topic.get("field") or {}).get("id"), "fields"),
                "domain_id": taxonomy_id((topic.get("domain") or {}).get("id"), "domains"),
            }
        )
    return rows
