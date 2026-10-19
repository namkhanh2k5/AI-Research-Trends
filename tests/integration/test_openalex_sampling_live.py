"""Opt-in live probe of documented OpenAlex sample/seed/page behavior."""

import os

import pytest

from ai_research_trends.config import build_year_stratum_filter, load_config
from ai_research_trends.crawling.openalex_client import (
    OpenAlexClient,
    canonical_work_id,
    validate_sample_page,
)


pytestmark = pytest.mark.skipif(
    os.getenv("OPENALEX_RUN_LIVE_TESTS") != "1",
    reason="Set OPENALEX_RUN_LIVE_TESTS=1 to run live OpenAlex probes",
)


def _fetch_page(client: OpenAlexClient, query_filter: str, page: int) -> tuple[int, list[str]]:
    payload = client.get_json(
        "works",
        {
            "filter": query_filter,
            "sample": 20,
            "seed": 20251019,
            "per_page": 10,
            "page": page,
            "select": "id",
        },
    )
    envelope = validate_sample_page(
        payload, requested_records=20, page_number=page, per_page=10
    )
    return envelope.meta["count"], [canonical_work_id(row["id"]) for row in envelope.results]


def test_seeded_sample_repeats_across_two_basic_pages() -> None:
    """Empirical probe only; it does not prove uniform inclusion or future stability."""
    study = load_config("config/topics.yaml")["study"]
    query_filter = build_year_stratum_filter(study, 2025)
    client = OpenAlexClient()

    first_page_one = _fetch_page(client, query_filter, 1)
    first_page_two = _fetch_page(client, query_filter, 2)
    repeat_page_one = _fetch_page(client, query_filter, 1)
    repeat_page_two = _fetch_page(client, query_filter, 2)

    first_ids = first_page_one[1] + first_page_two[1]
    repeated_ids = repeat_page_one[1] + repeat_page_two[1]
    assert first_page_one[0] == first_page_two[0] == 20
    assert first_page_one == repeat_page_one
    assert first_page_two == repeat_page_two
    assert first_ids == repeated_ids
    assert len(first_ids) == len(set(first_ids)) == 20
