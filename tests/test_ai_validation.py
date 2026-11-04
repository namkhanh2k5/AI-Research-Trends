"""Offline invariants for isolated AI-assisted topic and publisher assessment."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from ai_research_trends.experiments.ai_validation import (
    PUBLISHER_SHEET, RUN_ROOT, TOPIC_CHOICES, atomic_parquet, collect_official_pages,
    parse_page_metadata, publisher_metrics, require_private_output, topic_metrics,
    validate_publisher_decisions, validate_scope, validate_topic_decisions,
    verify_frozen_run,
)
from ai_research_trends.preprocessing.validate_tables import file_sha256


def _blind() -> pd.DataFrame:
    return pd.DataFrame({"example_id": ["A", "B"], "title": ["A", "B"]})


def _decisions() -> pd.DataFrame:
    return pd.DataFrame({
        "example_id": ["A", "B"], "selected_topic_id": ["T10028", "NONE"],
        "second_plausible_topic_id": ["T10181", None],
        "confidence_category": ["MEDIUM", "HIGH"],
        "evidence_summary": ["Language model for linguistic tasks.",
                             "Quantum circuit rather than AI methods."],
        "ambiguity_notes": ["NLP clusters overlap.", None],
    })


def test_topic_decisions_preserve_none_and_overlap() -> None:
    frame = validate_topic_decisions(_decisions(), _blind(), {"T10028", "T10181"})
    assert topic_metrics(frame)["secondary_plausible"] == 1
    assert topic_metrics(frame)["none"] == 1
    assert TOPIC_CHOICES == {"NONE", "UNCLEAR"}


@pytest.mark.parametrize("mutation", [
    lambda x: x.assign(example_id=["A", "A"]),
    lambda x: x.assign(selected_topic_id=["T99999", "NONE"]),
    lambda x: x.assign(evidence_summary=["short", "also short"]),
    lambda x: x.assign(second_plausible_topic_id=["T10028", None]),
    lambda x: x.assign(selected_topic_id=["UNCLEAR", "NONE"]),
])
def test_topic_decisions_reject_invalid(mutation) -> None:
    with pytest.raises(ValueError):
        validate_topic_decisions(mutation(_decisions()), _blind(), {"T10028", "T10181"})


def test_scope_requires_all_frozen_topics() -> None:
    topics = pd.DataFrame({"short_id": ["T1", "T2"], "name": ["one", "two"]})
    scope = pd.DataFrame({"topic_id": ["T1"], "scope_status": ["CLEARLY_DEFINED"],
                          "boundary_note": ["Defined task"], "overlap_note": [None]})
    with pytest.raises(ValueError, match="fourteen"):
        validate_scope(scope, topics)


def test_page_metadata_parser() -> None:
    parsed = parse_page_metadata(b'<title>Official article</title><meta name="citation_publisher" content="Example Society">')
    assert parsed["page_title"] == "Official article"
    assert parsed["meta"]["citation_publisher"] == ["Example Society"]


class _Response:
    def __init__(self, url: str, status: int = 200, location: str | None = None):
        self.url = url
        self.status_code = status
        self.ok = status == 200
        self.is_redirect = status in (301, 302)
        self.headers = {"Location": location} if location else {}
        self.content = b'<title>Public page</title><meta name="citation_publisher" content="Example">'


class _Session:
    def __init__(self, redirects: bool = False):
        self.calls: list[str] = []
        self.redirects = redirects

    def get(self, url: str, **kwargs):
        assert kwargs["allow_redirects"] is False
        self.calls.append(url)
        if self.redirects and url.startswith("https://doi.org/"):
            return _Response(url, 302, "https://publisher.example/article")
        return _Response(url)


def _publisher_source() -> pd.DataFrame:
    return pd.DataFrame({"work_id": [f"https://openalex.org/W{i}" for i in range(30)],
                         "doi": [f"https://doi.org/10.1000/{i}" for i in range(30)],
                         "recovered_or_compared_value": ["Example Society"] * 30})


def test_request_budget_stops_before_extra_cases(tmp_path: Path) -> None:
    session = _Session()
    path = tmp_path / "pages.json"
    evidence = collect_official_pages(_publisher_source(), path, budget=2, session=session)
    assert evidence["direct_get_attempts"] == 2
    assert evidence["observed_http_transactions"] == 2
    assert len(session.calls) == 2
    assert len(evidence["cases"]) == 30
    assert sum(x["status"] == "BUDGET_EXHAUSTED" for x in evidence["cases"]) == 28
    with pytest.raises(FileExistsError):
        collect_official_pages(_publisher_source(), path, budget=2, session=session)


def test_request_budget_stops_during_redirect(tmp_path: Path) -> None:
    session = _Session(redirects=True)
    evidence = collect_official_pages(_publisher_source(), tmp_path / "redirect.json",
                                      budget=1, session=session)
    assert len(session.calls) == 1
    assert evidence["cases"][0]["status"] == "BUDGET_EXHAUSTED_ON_REDIRECT"
    assert evidence["observed_http_transactions"] == 1


def test_publisher_evidence_required_for_positive_decisions() -> None:
    source = _publisher_source()
    rows = pd.DataFrame({
        "work_id": source.work_id, "doi": source.doi,
        "crossref_publisher": ["Example Society"] * 30,
        "official_publisher": ["Example Society"] * 30,
        "official_venue": ["Example Journal"] * 30,
        "evidence_url": ["https://publisher.example/article"] * 30,
        "secondary_evidence_url": [None] * 30,
        "retrieved_at_utc": ["2026-11-04T00:00:00Z"] * 30,
        "publisher_relation": ["EXACT"] * 30,
        "assessment_status": ["SOURCE_BACKED_CORRECT"] * 29 + ["SOURCE_BACKED_ACCEPTABLE_ALIAS"],
        "confidence_category": ["HIGH"] * 30,
        "reasoning_summary": ["Verified on publisher site"] * 30,
        "evidence_independence": ["OFFICIAL_SOURCE_BACKED"] * 30,
        "reviewer_type": ["AI_ASSISTED"] * 30,
        "human_adjudicated": [False] * 30,
    })
    assert publisher_metrics(validate_publisher_decisions(rows, source))["source_verifiable"] == 30
    rows.loc[0, "evidence_url"] = None
    with pytest.raises(ValueError, match="evidence URL"):
        validate_publisher_decisions(rows, source)
    rows.loc[0, "evidence_url"] = "https://publisher.example/article"
    rows.loc[0, "reviewer_type"] = "reviewer_a"
    with pytest.raises(ValueError, match="impersonate"):
        validate_publisher_decisions(rows, source)


def test_private_path_and_atomic_table(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        require_private_output(tmp_path / "not_private.parquet")
    assert RUN_ROOT.as_posix().startswith("data/analysis/")
    entry = atomic_parquet(tmp_path / "small.parquet", pd.DataFrame({"x": [1, 2]}))
    assert entry["rows"] == 2
    assert entry["sha256"] == file_sha256(tmp_path / "small.parquet")


def test_local_frozen_run_if_available() -> None:
    root = RUN_ROOT / "ai_assisted_20261104_v2"
    if not (root / "topic/frozen/manifest.json").exists():
        pytest.skip("Git-ignored local AI audit outputs unavailable in clean clone")
    result = verify_frozen_run(root)
    assert result["counts"] == {"topics": 14, "calibration": 40,
                                "evaluation": 100, "publishers": 30}
    assert result["sealed_2025_test"] == "NOT_ACCESSED"
    assert PUBLISHER_SHEET.exists()
    revision = json.loads((root / "revision_provenance.json").read_text())
    prior = RUN_ROOT / "ai_assisted_20261104_v1/manifest.json"
    assert revision["previous_manifest_sha256"] == file_sha256(prior)
    assert len(revision["corrected_example_ids"]) == 2
