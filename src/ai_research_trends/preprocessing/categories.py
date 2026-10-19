"""Separate OpenAlex-native topic lenses from project-defined text labels."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable

from ai_research_trends.preprocessing.text import reconstruct_abstract


@dataclass(frozen=True)
class CategoryMatches:
    """Independent, overlapping labels from two non-equivalent methods."""

    openalex_native: frozenset[str]
    custom_emerging: frozenset[str]


def _short_id(value: Any) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    return value.rstrip("/").split("/")[-1]


def work_topic_ids(work: dict[str, Any]) -> set[str]:
    """Return unique short IDs from the overlapping OpenAlex topics array."""
    return {
        topic_id
        for topic in (work.get("topics") or [])
        if isinstance(topic, dict) and (topic_id := _short_id(topic.get("id")))
    }


def searchable_text(work: dict[str, Any], scope: str = "title_abstract") -> str:
    """Construct only the text explicitly allowed by a configured rule scope."""
    title = work.get("title") if isinstance(work.get("title"), str) else ""
    if scope == "title":
        return title
    if scope != "title_abstract":
        raise ValueError(f"Unsupported text-rule scope: {scope!r}")
    abstract = reconstruct_abstract(work.get("abstract_inverted_index")) or ""
    return f"{title} {abstract}".strip()


def matches_rule_group(work: dict[str, Any], rule: dict[str, Any]) -> bool:
    """A rule group matches when every configured regular expression matches."""
    patterns = rule.get("all_of")
    if not isinstance(patterns, list) or not patterns:
        raise ValueError("Each rule group must define a non-empty all_of list")
    flags = 0 if rule.get("case_sensitive", False) else re.IGNORECASE
    text = searchable_text(work, str(rule.get("scope", "title_abstract")))
    return all(re.search(str(pattern), text, flags=flags) is not None for pattern in patterns)


def match_openalex_native(
    work: dict[str, Any], categories: dict[str, dict[str, Any]]
) -> frozenset[str]:
    """Match topic IDs only; no text rule can change a native taxonomy label."""
    ids = work_topic_ids(work)
    return frozenset(
        slug
        for slug, category in categories.items()
        if ids.intersection(str(topic_id) for topic_id in category.get("topic_ids", []))
    )


def match_custom_emerging(
    work: dict[str, Any], categories: dict[str, dict[str, Any]]
) -> frozenset[str]:
    """Match documented title/abstract rules only; no topic ID is implicit."""
    return frozenset(
        slug
        for slug, category in categories.items()
        if any(matches_rule_group(work, rule) for rule in category.get("rule_groups", []))
    )


def classify_work(work: dict[str, Any], config: dict[str, Any]) -> CategoryMatches:
    """Return both analytical layers without collapsing or prioritizing overlaps."""
    return CategoryMatches(
        openalex_native=match_openalex_native(
            work, config.get("openalex_native_categories", {})
        ),
        custom_emerging=match_custom_emerging(
            work, config.get("custom_emerging_technologies", {})
        ),
    )


def all_category_keys(matches: CategoryMatches) -> Iterable[tuple[str, str]]:
    """Yield layer/category pairs while preserving methodological provenance."""
    for slug in sorted(matches.openalex_native):
        yield "openalex_native", slug
    for slug in sorted(matches.custom_emerging):
        yield "custom_emerging", slug
