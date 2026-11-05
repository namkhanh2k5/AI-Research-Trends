import json
from pathlib import Path

import pytest

from ai_research_trends.config import load_config
from ai_research_trends.crawling.collect_aggregates import (
    collect,
    validate_year_aggregation,
)
from ai_research_trends.crawling.openalex_client import OpenAlexError


def _payload(counts: list[int] | None = None) -> dict:
    counts = counts or [1, 2, 3, 4, 5, 6]
    return {
        "meta": {"count": sum(counts)},
        "results": [],
        "group_by": [
            {"key": str(year), "key_display_name": str(year), "count": count}
            for year, count in zip(range(2020, 2026), counts, strict=True)
        ],
    }


class FakeResponse:
    status_code = 200
    headers: dict[str, str] = {}

    def __init__(self, payload: dict) -> None:
        self._payload = payload
        self.content = json.dumps(payload).encode()

    def json(self) -> dict:
        return self._payload


class FakeClient:
    def __init__(self, payloads: list[dict]) -> None:
        self.payloads = payloads

    def request(self, path: str, params: dict) -> FakeResponse:
        assert path == "works"
        return FakeResponse(self.payloads.pop(0))


def test_year_aggregation_requires_complete_unique_groups_and_meta_count() -> None:
    counts, total = validate_year_aggregation(_payload(), list(range(2020, 2026)))
    assert total == 21
    assert counts["2025"] == 6

    missing = _payload()
    missing["group_by"].pop()
    with pytest.raises(OpenAlexError, match="incomplete"):
        validate_year_aggregation(missing, list(range(2020, 2026)))

    duplicate = _payload()
    duplicate["group_by"][-1]["key"] = "2024"
    with pytest.raises(OpenAlexError, match="duplicate"):
        validate_year_aggregation(duplicate, list(range(2020, 2026)))

    mismatch = _payload()
    mismatch["meta"]["count"] += 1
    with pytest.raises(OpenAlexError, match="meta.count"):
        validate_year_aggregation(mismatch, list(range(2020, 2026)))


def test_failed_aggregate_collection_preserves_incomplete_manifest(tmp_path: Path) -> None:
    malformed = _payload()
    malformed["group_by"] = malformed["group_by"][:-1]
    with pytest.raises(OpenAlexError):
        collect(load_config("config/topics.yaml"), FakeClient([malformed]), tmp_path)

    manifest_path = next(tmp_path.glob("aggregates_*/manifest.json"))
    manifest = json.loads(manifest_path.read_text())
    assert manifest["status"] == "failed"
    assert manifest["complete"] is False
    assert manifest["completed_queries"] == []
    assert manifest["failed_query"] == "study_population_all"
    assert next(manifest_path.parent.glob("study_population_all.json")).exists()
