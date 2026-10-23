"""Reference edges and an explicit audit for malformed source references."""

from __future__ import annotations

from typing import Any

from ai_research_trends.crawling.openalex_client import canonical_work_id


def normalize_references(
    source: dict[str, Any], work_id: str, sample_work_ids: set[str]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    values = source.get("referenced_works")
    if values is None:
        return [], []
    if not isinstance(values, list):
        raise ValueError(f"{work_id} referenced_works must be a list or null")
    rows: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    seen: set[str] = set()
    for position, value in enumerate(values, start=1):
        try:
            reference_id = canonical_work_id(value)
        except (TypeError, ValueError) as exc:
            issues.append(
                {
                    "work_id": work_id,
                    "field": "referenced_works",
                    "position": position,
                    "reason": f"{type(exc).__name__}: {exc}",
                    "raw_value": repr(value)[:200],
                }
            )
            continue
        if reference_id in seen:
            issues.append(
                {
                    "work_id": work_id,
                    "field": "referenced_works",
                    "position": position,
                    "reason": "duplicate reference edge",
                    "raw_value": reference_id,
                }
            )
            continue
        seen.add(reference_id)
        rows.append(
            {
                "citing_work_id": work_id,
                "referenced_work_id": reference_id,
                "referenced_in_sample": reference_id in sample_work_ids,
            }
        )
    return rows, issues
