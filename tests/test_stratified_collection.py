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
from ai_research_trends.crawling.plan_stratified_sample import APPROVED_PRIMARY_FILTER


def _plan() -> dict:
    return {
        "schema_version": 1,
        "design": "proportional_publication_year_stratified_largest_remainder",
        "population_query_name": "study_population_primary_non_retracted",
        "population_query_parameters": {
            "filter": APPROVED_PRIMARY_FILTER,
            "group_by": "publication_year",
        },
        "population_counts_source": "data/metadata/test_population.json",
        "population_counts_sha256": "0" * 64,
        "population_total": 60,
        "target_sample_size": 6,
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

    def __init__(self, year: int, identifier: int | None = None) -> None:
        work = _work(year)
        if identifier is not None:
            work["id"] = f"https://openalex.org/W{identifier}"
        self.content = json.dumps(
            {"meta": {"count": 1}, "results": [work], "group_by": []},
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
    diagnostics = result["diagnostics"]
    assert diagnostics["pages_expected"] == diagnostics["pages_checkpointed"] == 6
    assert diagnostics["raw_page_files_on_disk"] == 6
    assert diagnostics["raw_page_bytes_on_disk"] == sum(
        Path(page["path"]).stat().st_size
        for stratum in result["strata"]
        for page in stratum["pages"]
    )
    assert diagnostics["api_requests_attempted"] == 6
    assert diagnostics["api_requests_succeeded"] == 6
    assert diagnostics["api_failures"] == []
    assert diagnostics["duplicate_check"]["passed"] is True
    assert diagnostics["run_complete"] is True
    assert all(
        page["work_ids"]
        for stratum in result["strata"]
        for page in stratum["pages"]
    )


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
    assert failed["diagnostics"]["api_requests_attempted"] == 2
    assert failed["diagnostics"]["api_requests_succeeded"] == 1
    assert len(failed["diagnostics"]["api_failures"]) == 1
    assert failed["diagnostics"]["run_complete"] is False

    resumed_client = FakeClient(list(range(2020, 2026)))
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
    assert len(resumed_client.calls) == 6
    assert resumed["resume_consistency_probes"][0]["status"] == "passed"


def test_resume_fails_safely_when_seeded_page_membership_changes(tmp_path: Path) -> None:
    raw_root = tmp_path / "raw"
    interim_root = tmp_path / "interim"
    with pytest.raises(OpenAlexError, match="simulated"):
        collect_stratified_sample(
            plan=_plan(),
            config=load_config("config/topics.yaml"),
            client=FakeClient(list(range(2020, 2026)), fail_after=1),
            raw_root=raw_root,
            interim_root=interim_root,
            base_seed=100,
        )
    manifest_path = next(raw_root.glob("stratified_*/manifest.json"))

    class ChangedProbeClient(FakeClient):
        def request(self, path: str, params: dict) -> FakeResponse:
            self.calls.append(params)
            return FakeResponse(2020, identifier=999999)

    changed = ChangedProbeClient([])
    with pytest.raises(OpenAlexError, match="refusing to mix retrieval snapshots"):
        collect_stratified_sample(
            plan=_plan(),
            config=load_config("config/topics.yaml"),
            client=changed,
            raw_root=raw_root,
            interim_root=interim_root,
            base_seed=100,
            resume_manifest=manifest_path,
        )

    failed = json.loads(manifest_path.read_text())
    assert failed["status"] == "failed"
    assert failed["complete"] is False
    probe = failed["resume_consistency_probes"][0]
    assert probe["status"] == "failed"
    assert probe["checkpoint_work_ids"] == ["https://openalex.org/W2020"]
    assert probe["probe_work_ids"] == ["https://openalex.org/W999999"]
    assert Path(probe["probe_raw_path"]).exists()
    assert len(changed.calls) == 1


def test_duplicate_failure_reports_raw_bytes_and_duplicate_check(tmp_path: Path) -> None:
    class DuplicateClient(FakeClient):
        def request(self, path: str, params: dict) -> FakeResponse:
            year = self.years.pop(0)
            self.calls.append(params)
            return FakeResponse(year, identifier=1)

    raw_root = tmp_path / "raw"
    with pytest.raises(OpenAlexError, match="Duplicate Work ID"):
        collect_stratified_sample(
            plan=_plan(),
            config=load_config("config/topics.yaml"),
            client=DuplicateClient(list(range(2020, 2026))),
            raw_root=raw_root,
            interim_root=tmp_path / "interim",
            base_seed=100,
        )
    manifest = json.loads(next(raw_root.glob("stratified_*/manifest.json")).read_text())
    diagnostics = manifest["diagnostics"]
    assert diagnostics["duplicate_check"]["duplicate_work_ids_detected"] == 1
    assert diagnostics["duplicate_check"]["passed"] is False
    assert diagnostics["pages_checkpointed"] == 1
    assert diagnostics["raw_page_files_on_disk"] == 2
    assert diagnostics["raw_page_bytes_on_disk"] > 0
    assert diagnostics["run_complete"] is False


def test_resume_path_must_stay_inside_raw_root(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="inside"):
        _safe_resume_manifest(tmp_path / "elsewhere" / "manifest.json", tmp_path / "raw")


def test_collection_plan_rejects_duplicate_or_missing_years() -> None:
    plan = _plan()
    plan["strata"][5]["publication_year"] = 2024
    with pytest.raises(ValueError, match="2020 through 2025"):
        validate_collection_plan(plan)
