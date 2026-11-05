"""Offline cursor-sync contract; no live OpenAlex access or research-file edits."""

import hashlib
import json
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from ai_research_trends.preprocessing.validate_tables import file_sha256
from ai_research_trends.web.paper_discovery import PaperDiscovery, build_index, verify_index
from ai_research_trends.web.sync import (
    daily_windows, normalize_application_work, publication_filter, read_sync_status, sync, sync_daily,
)


def work(number, title, *, day="2026-01-02", abstract=True):
    return {"id": f"https://openalex.org/W{number}", "title": title,
            "abstract_inverted_index": ({"We": [0], "study": [1], "neural": [2],
                                          "translation": [3], "with": [4], "attention": [5],
                                          "models": [6], "today": [7]} if abstract else None),
            "publication_date": day, "publication_year": 2026, "type": "article",
            "is_retracted": False, "doi": None, "cited_by_count": 0,
            "primary_topic": {"id": "https://openalex.org/T10028",
                              "subfield": {"id": "https://openalex.org/subfields/1702"}}}


def page(rows, count, cursor):
    return {"meta": {"count": count, "next_cursor": cursor}, "results": rows}


class Response:
    def __init__(self, payload):
        self.content = json.dumps(payload).encode()


class Client:
    def __init__(self, pages, fail_after=None):
        self.pages = pages
        self.fail_after = fail_after
        self.calls = 0

    def request(self, path, params):
        assert path == "works"
        assert params["filter"] == publication_filter(date(2026, 1, 2), date(2026, 1, 2))
        self.calls += 1
        if self.fail_after is not None and self.calls > self.fail_after:
            raise RuntimeError("temporary API failure")
        return Response(self.pages[params["cursor"]])


@pytest.fixture
def source(tmp_path, monkeypatch):
    original = tmp_path / "research" / "works.parquet"
    original.parent.mkdir()
    pd.DataFrame([{"work_id": "https://openalex.org/W1",
                   "title": "Original neural translation with attention models",
                   "abstract": "A study of neural translation and attention with multilingual examples and test cases.",
                   "publication_date": date(2020, 1, 2), "publication_year": 2020,
                   "work_type": "article", "doi": None,
                   "primary_topic_id": "https://openalex.org/T10028", "cited_by_count": 2}]).to_parquet(original)
    original_hash = file_sha256(original)
    (original.parent / "manifest.json").write_text(json.dumps({
        "status": "complete", "tables": {"works": {"rows": 1, "sha256": original_hash}}}))
    web = tmp_path / "web"
    web.mkdir()
    (web / "manifest.json").write_text("{}")
    monkeypatch.setattr("ai_research_trends.web.paper_discovery.verify_web_data", lambda _: None)
    old_index = tmp_path / "old_index"
    build_index(original, web, old_index, min_df=1)
    return original, web, old_index, original_hash


def run(tmp_path, source, client, **kwargs):
    original, web, old_index, _ = source
    rebuilder = kwargs.pop("rebuild_index", lambda a, b, c, **kw:
                           build_index(a, b, c, min_df=1, **kw))
    return sync(root=tmp_path / "app", original_works=original, web_dir=web,
                original_index=old_index, client=client,
                start=date(2026, 1, 2), end=date(2026, 1, 2), per_page=1,
                max_records=10, rebuild_index=rebuilder, **kwargs)


def test_success_idempotence_and_index_contains_new_paper(tmp_path, source):
    new = work(2, "New neural translation with attention research")
    pages = {"*": page([new], 1, None)}
    first = run(tmp_path, source, Client(pages))
    assert first["status"] == "complete"
    assert first["changes"]["newly_observed_ids"] == 1
    state = read_sync_status(tmp_path / "app")
    assert state is not None
    assert state["application_rows"] == 1
    assert state["indexed_application_works"] == 1
    assert state["index_scope"] == "historical_sample_plus_application_sync"
    assert first["storage_bytes"] > 0
    index = PaperDiscovery(Path(state["index"]))
    assert index.manifest["scope"] == "historical_sample_plus_application_sync"
    assert "https://openalex.org/W2" in index.papers.work_id.tolist()
    found = index.search("New neural translation with attention research",
                         "We study neural translation with attention models today",
                         year_min=2026, top_k=5)
    assert [item["work_id"] for item in found["items"]] == ["https://openalex.org/W2"]
    second = run(tmp_path, source, Client(pages))
    assert second["changes"]["newly_observed_ids"] == 0
    assert second["application_rows"] == 1
    assert file_sha256(source[0]) == source[3]
    assert len(list((tmp_path / "app" / "runs").iterdir())) == 2


def test_interruption_resume_and_changed_membership_fails(tmp_path, source):
    a = work(2, "Neural translation research in visual systems")
    b = work(3, "Neural language research across data sources")
    pages = {"*": page([a], 2, "cursor2"), "cursor2": page([b], 2, None)}
    with pytest.raises(RuntimeError, match="temporary"):
        run(tmp_path, source, Client(pages, fail_after=1))
    root = tmp_path / "app"
    assert read_sync_status(root) is None
    run_dir = next((root / "runs").iterdir())
    manifest = json.loads((run_dir / "manifest.json").read_text())
    assert manifest["status"] == "incomplete" and len(manifest["pages"]) == 1
    changed = {"*": page([work(4, "Different neural translation research paper")], 2, "cursor2"),
               "cursor2": page([b], 2, None)}
    with pytest.raises(ValueError, match="membership"):
        run(tmp_path, source, Client(changed), resume=run_dir.name)
    assert read_sync_status(root) is None
    assert file_sha256(run_dir / "raw_pages/page_0001.json") == manifest["pages"][0]["sha256"]
    completed = run(tmp_path, source, Client(pages), resume=run_dir.name)
    assert completed["retrieved"] == 2
    assert completed["application_rows"] == 2


def test_failed_index_rebuild_keeps_last_good_state(tmp_path, source):
    one = {"*": page([work(2, "Neural translation and attention in research")], 1, None)}
    run(tmp_path, source, Client(one))
    previous = read_sync_status(tmp_path / "app")
    assert previous is not None
    def fail(*args, **kwargs):
        raise RuntimeError("index build failed")
    with pytest.raises(RuntimeError, match="index build failed"):
        run(tmp_path, source, Client(one), rebuild_index=fail)
    assert read_sync_status(tmp_path / "app") == previous
    verify_index(Path(previous["index"]))


def test_invalid_work_and_malformed_abstract_are_rejected():
    row = work(2, "Neural translation paper")
    row["is_retracted"] = True
    with pytest.raises(ValueError, match="Out-of-scope"):
        normalize_application_work(row, date(2026, 1, 2), date(2026, 1, 2), "2026-01-03T00:00:00Z")
    row["is_retracted"] = False
    row["abstract_inverted_index"] = {"duplicate": [0, 0]}
    with pytest.raises(ValueError, match="Malformed abstract"):
        normalize_application_work(row, date(2026, 1, 2), date(2026, 1, 2), "2026-01-03T00:00:00Z")
    row["abstract_inverted_index"] = None
    assert normalize_application_work(row, date(2026, 1, 2), date(2026, 1, 2), "2026-01-03T00:00:00Z")["abstract"] is None


def test_window_rejects_out_of_scope_dates():
    with pytest.raises(ValueError):
        publication_filter(date(2025, 12, 31), date(2026, 1, 1))


def test_orphan_page_is_quarantined_before_resume(tmp_path, source):
    a = work(2, "Neural translation research in visual systems")
    b = work(3, "Neural language research across data sources")
    pages = {"*": page([a], 2, "cursor2"), "cursor2": page([b], 2, None)}
    with pytest.raises(RuntimeError):
        run(tmp_path, source, Client(pages, fail_after=1))
    root = tmp_path / "app"
    run_dir = next((root / "runs").iterdir())
    (run_dir / "raw_pages/page_0002.json").write_bytes(b"partial and malformed")
    with pytest.raises(ValueError, match="Quarantined"):
        run(tmp_path, source, Client(pages), resume=run_dir.name)
    assert not (run_dir / "raw_pages/page_0002.json").exists()
    assert len(list((run_dir / "quarantine").iterdir())) == 1
    assert read_sync_status(root) is None


def test_resume_rejects_changed_population_count(tmp_path, source):
    a = work(2, "Neural translation research in visual systems")
    b = work(3, "Neural language research across data sources")
    pages = {"*": page([a], 2, "cursor2"), "cursor2": page([b], 2, None)}
    with pytest.raises(RuntimeError):
        run(tmp_path, source, Client(pages, fail_after=1))
    root = tmp_path / "app"
    run_dir = next((root / "runs").iterdir())
    changed = {"*": page([a], 3, "cursor2"), "cursor2": page([b], 3, None)}
    with pytest.raises(ValueError, match="count changed"):
        run(tmp_path, source, Client(changed), resume=run_dir.name)
    assert read_sync_status(root) is None


def test_web_falls_back_without_a_valid_sync(monkeypatch, tmp_path):
    from ai_research_trends.web import service
    assert read_sync_status(tmp_path / "never_synced") is None
    monkeypatch.delenv("AI_TRENDS_DISCOVERY_INDEX", raising=False)
    monkeypatch.setattr("ai_research_trends.web.sync.read_sync_status", lambda *_: None)
    assert service.discovery_path() == service.DEFAULT_DISCOVERY
    assert service.sync_status() is None


def test_daily_window_plan_is_contiguous_and_bounded():
    days = daily_windows(date(2026, 1, 2), date(2026, 1, 5))
    assert days == [date(2026, 1, 2), date(2026, 1, 3), date(2026, 1, 4), date(2026, 1, 5)]
    with pytest.raises(ValueError, match="do not skip dates"):
        daily_windows(date(2026, 1, 2), date(2026, 1, 5), max_days=3)


class DailyClient:
    def __init__(self, *, fail_day=None, oversized_day=None):
        self.fail_day = fail_day
        self.oversized_day = oversized_day
        self.calls = []

    def request(self, path, params):
        day = params["filter"].split("from_publication_date:", 1)[1][:10]
        self.calls.append(day)
        if day == self.fail_day:
            raise RuntimeError("API unavailable")
        number = int(day[-2:]) + 100
        return Response(page([work(number, f"Neural translation research on day {day}", day=day)],
                             11 if day == self.oversized_day else 1, None))


def _daily(tmp_path, source, client, start, end, **kwargs):
    original, web, old_index, _ = source
    return sync_daily(start=start, end=end, root=tmp_path / "app", original_works=original,
                      web_dir=web, original_index=old_index, client=client,
                      per_page=1, max_records=10,
                      rebuild_index=lambda a, b, c, **kw: build_index(a, b, c, min_df=1, **kw),
                      **kwargs)


def test_missed_days_stop_at_failure_and_recover_without_skipping(tmp_path, source):
    second = date(2026, 1, 3)
    third = date(2026, 1, 4)
    first = date(2026, 1, 2)
    failed = DailyClient(fail_day=str(second))
    with pytest.raises(RuntimeError, match="no later date was processed"):
        _daily(tmp_path, source, failed, first, third)
    assert failed.calls == [str(first), str(second)]
    state = read_sync_status(tmp_path / "app")
    assert state["window_end"] == str(first)
    manifests = [json.loads(path.read_text()) for path in (tmp_path / "app/runs").glob("*/manifest.json")]
    assert sorted(item["status"] for item in manifests) == ["complete", "incomplete"]
    completed = _daily(tmp_path, source, DailyClient(), second, third)
    assert [item["window_end"] for item in completed] == [str(second), str(third)]
    state = read_sync_status(tmp_path / "app")
    assert state["window_end"] == str(third)
    assert state["application_rows"] == 3
    assert file_sha256(source[0]) == source[3]


def test_oversized_day_does_not_advance_past_gap(tmp_path, source):
    first, second = date(2026, 1, 2), date(2026, 1, 3)
    with pytest.raises(RuntimeError, match="no later date was processed") as error:
        _daily(tmp_path, source, DailyClient(oversized_day=str(second)), first, second)
    assert f"--from-date {second} --to-date {second}" in str(error.value)
    state = read_sync_status(tmp_path / "app")
    assert state["window_end"] == str(first)
    manifests = [json.loads(path.read_text()) for path in (tmp_path / "app/runs").glob("*/manifest.json")]
    assert any(item["status"] == "incomplete" and "exceeds max_records" in item["last_error"]
               for item in manifests)
    _daily(tmp_path, source, DailyClient(), second, second)
    assert read_sync_status(tmp_path / "app")["window_end"] == str(second)


def test_explicit_range_cannot_skip_unpublished_days(tmp_path, source):
    first = date(2026, 1, 2)
    _daily(tmp_path, source, DailyClient(), first, first)
    with pytest.raises(RuntimeError, match="stopped at 2026-01-04") as error:
        _daily(tmp_path, source, DailyClient(), date(2026, 1, 4), date(2026, 1, 4))
    assert "skips unpublished dates" in str(error.value.__cause__)
    assert read_sync_status(tmp_path / "app")["window_end"] == str(first)


def test_resume_after_completed_index_before_state_commit(tmp_path, source):
    pages = {"*": page([work(2, "Neural translation and attention in research")], 1, None)}
    def built_then_interrupted(a, b, c, **kwargs):
        build_index(a, b, c, min_df=1, **kwargs)
        raise RuntimeError("interrupted after index build")
    with pytest.raises(RuntimeError, match="interrupted"):
        run(tmp_path, source, Client(pages), rebuild_index=built_then_interrupted)
    root = tmp_path / "app"
    run_dir = next((root / "runs").iterdir())
    assert (run_dir / "index/manifest.json").is_file()
    assert read_sync_status(root) is None
    result = run(tmp_path, source, Client(pages), resume=run_dir.name)
    assert result["status"] == "complete"
    assert read_sync_status(root) is not None


def test_empty_day_completes_without_inventing_application_papers(tmp_path, source):
    result = run(tmp_path, source, Client({"*": page([], 0, None)}))
    assert result["status"] == "complete"
    assert result["retrieved"] == 0
    assert result["application_rows"] == 0
    assert result["changes"]["newly_observed_ids"] == 0


def test_status_backfills_indexed_count_for_older_index_manifest(tmp_path, source):
    result = run(tmp_path, source, Client({"*": page([work(2, "Neural translation and attention in research")], 1, None)}))
    index_manifest = tmp_path / "app" / "runs" / result["run_id"] / "index" / "manifest.json"
    old = json.loads(index_manifest.read_text())
    old["stats"].pop("indexed_application_works")
    old["stats"].pop("indexed_historical_works")
    index_manifest.write_text(json.dumps(old))
    status = read_sync_status(tmp_path / "app")
    assert status["application_rows"] == 1
    assert status["indexed_application_works"] == 1
