import json
from pathlib import Path

import pytest

from ai_research_trends.crawling.openalex_client import (
    OpenAlexClient,
    OpenAlexError,
    canonical_openalex_id,
    parse_list_response,
)


class FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200, raw: bytes | None = None) -> None:
        self._payload = payload
        self.status_code = status_code
        self.content = raw if raw is not None else json.dumps(payload).encode()
        self.text = self.content.decode()
        self.headers: dict[str, str] = {}
        self.url = "https://api.openalex.org/works"

    def json(self) -> dict:
        return self._payload


class FakeSession:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = responses
        self.headers: dict[str, str] = {}
        self.calls: list[dict] = []

    def get(self, url: str, params: dict, timeout: float) -> FakeResponse:
        self.calls.append({"url": url, "params": params, "timeout": timeout})
        return self.responses.pop(0)


def test_canonical_openalex_id() -> None:
    assert canonical_openalex_id("https://openalex.org/w123/") == "https://openalex.org/W123"
    assert canonical_openalex_id("W456") == "https://openalex.org/W456"
    with pytest.raises(ValueError):
        canonical_openalex_id("not-an-id")


def test_retry_after_transient_status() -> None:
    first = FakeResponse({"error": "busy"}, status_code=429)
    first.headers["Retry-After"] = "0"
    second = FakeResponse({"results": []})
    sleeps: list[float] = []
    session = FakeSession([first, second])
    client = OpenAlexClient(
        session=session, sleep=sleeps.append, min_interval_seconds=0, max_retries=2
    )

    assert client.get_json("works") == {"results": []}
    assert len(session.calls) == 2
    assert sleeps


def test_api_parameter_handling_for_basic_page() -> None:
    response = FakeResponse(
        {"meta": {"count": 1, "next_cursor": None}, "results": [{"id": "https://openalex.org/W1"}], "group_by": []}
    )
    session = FakeSession([response])
    client = OpenAlexClient(session=session, min_interval_seconds=0)

    pages = list(
        client.iter_basic_pages(
            "works", {"filter": "publication_year:2025", "sample": 1, "seed": 9},
            expected_records=1, per_page=100
        )
    )
    assert len(pages) == 1
    assert session.calls[0]["params"] == {
        "filter": "publication_year:2025",
        "sample": 1,
        "seed": 9,
        "per_page": 100,
        "page": 1,
    }


def test_parse_pagination_response_with_null_cursor() -> None:
    envelope = parse_list_response(
        {"meta": {"count": 0, "next_cursor": None}, "results": [], "group_by": []}
    )
    assert envelope.results == []
    assert envelope.next_cursor is None
    with pytest.raises(OpenAlexError, match="meta"):
        parse_list_response({"results": []})


def test_collect_sample_preserves_raw_bytes_and_deduplicates(tmp_path: Path) -> None:
    work = {"id": "https://openalex.org/W1", "title": "Example"}
    payload = {"meta": {"count": 2}, "results": [work, work], "group_by": []}
    raw = b'{"meta":{"count":2},"results":[{"id":"https://openalex.org/W1","title":"Example"},{"id":"https://openalex.org/W1","title":"Example"}],"group_by":[]}'
    response = FakeResponse(payload, raw=raw)
    client = OpenAlexClient(session=FakeSession([response]), min_interval_seconds=0)

    summary = client.collect_sample(
        query_filter="publication_year:2025",
        requested_records=2,
        seed=7,
        raw_root=tmp_path / "raw",
        interim_root=tmp_path / "interim",
    )

    page_path = next((tmp_path / "raw").glob("*/page_0001.json"))
    assert page_path.read_bytes() == raw
    assert summary.raw_records == 2
    assert summary.unique_records == 1
    assert summary.duplicate_records == 1
    assert summary.complete_for_requested_sample is False
    assert Path(summary.raw_jsonl_path).read_text().count("\n") == 2
    assert Path(summary.jsonl_path).read_text().count("\n") == 1
