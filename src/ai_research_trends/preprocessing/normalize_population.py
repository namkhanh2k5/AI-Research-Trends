"""Validate complete OpenAlex aggregate evidence and build population tables."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from ai_research_trends.crawling.collect_aggregates import _query_specs, validate_year_aggregation
from ai_research_trends.preprocessing.common import parse_utc


def normalize_population(
    artifact: dict[str, Any], config: dict[str, Any]
) -> list[dict[str, Any]]:
    if artifact.get("complete") is not True:
        raise ValueError("Population aggregate artifact is incomplete")
    specs = _query_specs(config)
    queries = artifact.get("queries")
    if not isinstance(queries, list) or [q.get("name") for q in queries] != [s["name"] for s in specs]:
        raise ValueError("Population aggregate queries do not match approved configuration")
    retrieved_at = parse_utc(artifact["retrieved_at_utc"])
    manifest = json.loads(Path(artifact["run_manifest"]).read_text())
    if manifest.get("complete") is not True or manifest.get("status") != "complete":
        raise ValueError("Population aggregate run manifest is incomplete")
    if manifest.get("completed_queries") != [s["name"] for s in specs]:
        raise ValueError("Population aggregate manifest query list is incomplete")

    rows: list[dict[str, Any]] = []
    for query, spec in zip(queries, specs, strict=True):
        if query.get("query_parameters") != spec["params"]:
            raise ValueError(f"Population query parameters drifted for {spec['name']}")
        raw = Path(query["raw_path"]).read_bytes()
        if hashlib.sha256(raw).hexdigest() != query.get("sha256"):
            raise ValueError(f"Population raw response checksum mismatch for {spec['name']}")
        counts, total = validate_year_aggregation(json.loads(raw), list(range(2020, 2026)))
        if counts != query.get("counts_by_year") or total != query.get("meta_count"):
            raise ValueError(f"Population count mismatch for {spec['name']}")
        query_hash = hashlib.sha256(
            json.dumps(spec["params"], sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        for year, work_count in counts.items():
            rows.append(
                {
                    "series": spec["name"],
                    "year": int(year),
                    "work_count": work_count,
                    "definition": f"{spec['method']}; retraction_scope={spec['retraction_scope']}",
                    "retrieved_at_utc": retrieved_at,
                    "query_hash": query_hash,
                }
            )
    return sorted(rows, key=lambda row: (row["series"], row["year"]))
