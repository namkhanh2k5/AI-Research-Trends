import json
from pathlib import Path

import pytest

from ai_research_trends.config import load_config
from ai_research_trends.crawling.collect_stratified import (
    _safe_resume_manifest,
    collect_stratified_sample,
    validate_collection_plan,
)
from ai_research_trends.crawling.openalex_client import OpenAlexError


def _plan() -> dict:
    return {
        "design": "proportional_publication_year_stratified_largest_remainder",
        "allocated_sample_size": 6,
        "strata": [
            {
                "publication_year": year,
                "population_size": 10,
                "sample_size": 1,
                "inclusion_probability": 0.1,
                "sampling_weight": 10.0,
                "remainder_numerator": 0,
            }
            for year in range(2020, 2026)
        ],
    }


def _work(year: int) -> dict:
    return {
        "id": f"https://openalex.org/W{year}",
        "publication_date": f"{year}-06-15",
        "publication_year": year,
        "type": "article",
        "is_retracted": False,
        "primary_topic": {
            "subfield": {"id": "https://openalex.org/subfields/1702"}
        },
    }


class FakeResponse:
    status_code = 200
    headers: dict[str, str] = {}

    def __init__(self, year: int) -> None:
        self.content = json.dumps(
            {"meta": {"count": 1}, "results": [_work(year)], "group_by": []},
            separators=(",", ":"),
        ).encode()


class FakeClient:
    base_url = "https://api.openalex.org"

    def __init__(self, years: list[int], fail_after: int | None = None) -> None:
        self.years = years
        self.fail_after = fail_after
        self.calls: list[dict] = []

    def request(self, path: str, params: dict) -> FakeResponse:
        if self.fail_after is not None and len(self.calls) >= self.fail_after:
            raise OpenAlexError("simulated network failure")
        self.calls.append(params)
        year = self.years.pop(0)
        assert f"from_publication_date:{year}-01-01" in params["filter"]
        assert params["sample"] == 1
        return FakeResponse(year)


def test_checkpointed_collection_preserves_pages_and_completes(tmp_path: Path) -> None:
    client = FakeClient(list(range(2020, 2026)))
    result = collect_stratified_sample(
        plan=_plan(),
        config=load_config("config/topics.yaml"),
        client=client,
        raw_root=tmp_path / "raw",
        interim_root=tmp_path / "interim",
        base_seed=100,
    )
    assert result["complete"] is True
    assert result["unique_work_ids"] == 6
    assert len(client.calls) == 6
    assert Path(result["raw_jsonl"]).read_text().count("\n") == 6
    assert all(len(stratum["pages"]) == 1 for stratum in result["strata"])


def test_failed_collection_can_resume_without_refetching_checkpoint(tmp_path: Path) -> None:
    raw_root = tmp_path / "raw"
    interim_root = tmp_path / "interim"
    failing = FakeClient(list(range(2020, 2026)), fail_after=1)
    with pytest.raises(OpenAlexError, match="simulated"):
        collect_stratified_sample(
            plan=_plan(),
            config=load_config("config/topics.yaml"),
            client=failing,
            raw_root=raw_root,
            interim_root=interim_root,
            base_seed=100,
        )
    manifest_path = next(raw_root.glob("stratified_*/manifest.json"))
    failed = json.loads(manifest_path.read_text())
    assert failed["status"] == "failed"
    assert failed["strata"][0]["status"] == "complete"

    resumed_client = FakeClient(list(range(2021, 2026)))
    resumed = collect_stratified_sample(
        plan=_plan(),
        config=load_config("config/topics.yaml"),
        client=resumed_client,
        raw_root=raw_root,
        interim_root=interim_root,
        base_seed=100,
        resume_manifest=manifest_path,
    )
    assert resumed["complete"] is True
    assert len(resumed_client.calls) == 5


def test_resume_path_must_stay_inside_raw_root(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="inside"):
        _safe_resume_manifest(tmp_path / "elsewhere" / "manifest.json", tmp_path / "raw")


def test_collection_plan_rejects_duplicate_or_missing_years() -> None:
    plan = _plan()
    plan["strata"][5]["publication_year"] = 2024
    with pytest.raises(ValueError, match="2020 through 2025"):
        validate_collection_plan(plan)
