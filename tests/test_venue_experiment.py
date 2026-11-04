"""Offline safety and methodological regression tests for the venue pilot."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from ai_research_trends.experiments.venue_core import (
    extract_openalex_venue, normalize_issn, parse_crossref, resolve_venue,
    retraction_comparison, source_id,
)
from ai_research_trends.experiments.venue_enrichment import (
    CrossrefCollector, atomic_bytes, checked_manifest, quarantine_orphans,
)
from ai_research_trends.experiments.venue_inventory import select_dois
from ai_research_trends.experiments.venue_analysis import paired_provider_gains
from ai_research_trends.experiments.venue_retrieval import (
    build_candidate_pool, metrics_for_predictions, query_text, rank_from_scores,
    rank_text, validate_temporal_frames, VenueDiscoveryService,
)


def source(sid="S123", kind="journal", name="Example Journal"):
    return {"id": f"https://openalex.org/{sid}", "type": kind,
            "display_name": name, "issn": ["1234-5679"]}


def work(primary, alternatives=None):
    return {"id": "https://openalex.org/W123", "doi": "https://doi.org/10.1234/ABC",
            "publication_year": 2023, "publication_date": "2023-06-01", "type": "article",
            "primary_topic": {"id": "https://openalex.org/T123"},
            "is_retracted": False, "primary_location": primary,
            "locations": alternatives or []}


def test_identifier_normalization():
    assert source_id("s123") == "https://openalex.org/S123"
    assert normalize_issn("12345679") == "1234-5679"
    with pytest.raises(ValueError):
        source_id("https://openalex.org/W123")
    with pytest.raises(ValueError):
        normalize_issn("1234-5678")


def test_repository_is_not_publication_venue():
    primary = {"source": source("S1", "repository", "arXiv"), "is_published": False}
    alt = {"source": source("S2", "journal"), "version": "publishedVersion"}
    result = extract_openalex_venue(work(primary, [alt]))
    assert result["primary_source_type"] == "repository"
    assert result["source_id"] == "https://openalex.org/S2"
    assert result["has_repository_host"] is True


def test_ambiguous_published_sources_not_name_merged():
    p = {"source": source("S1"), "is_published": True}
    q = {"source": source("S2"), "is_published": True}
    result = extract_openalex_venue(work(p, [q]))
    assert result["source_id"] is None
    assert result["match_status"] == "AMBIGUOUS"


def test_crossref_doi_and_retraction_parsing():
    payload = {"message": {"DOI": "10.1234/ABC", "title": ["A Title"],
        "container-title": ["Journal"], "ISSN": ["1234-5679"],
        "type": "journal-article", "published": {"date-parts": [[2023, 6, 1]]},
        "update-to": [{"type": "retraction"}]}}
    parsed = parse_crossref(payload, "https://doi.org/10.1234/abc")
    assert parsed["crossref_retraction_evidence"] is True
    assert parsed["published_year"] == 2023
    with pytest.raises(ValueError):
        parse_crossref(payload, "https://doi.org/10.9999/other")
    assert retraction_comparison(True, None)["status_unknown"] is True


def test_identifier_conflict_keeps_provider_values():
    local = extract_openalex_venue(work({"source": source(), "is_published": True}))
    cross = {"issns": ["2049-3630"], "container_title": "Other",
             "publisher": "Publisher", "crossref_type": "journal-article"}
    result = resolve_venue(local, cross)
    assert result["identity_status"] == "CONFLICT"
    assert result["canonical_venue_id"] is None
    assert result["openalex_name"] == "Example Journal"
    assert result["crossref_name"] == "Other"


def test_crossref_only_issn_resolution_and_missing_metadata():
    local = extract_openalex_venue(work({"source": source("S1", "repository")}))
    cross = {"issns": ["1234-5679"], "container_title": "Journal",
             "crossref_type": "journal-article"}
    assert resolve_venue(local, cross)["canonical_venue_id"] == "issn:1234-5679"
    assert resolve_venue(local)["canonical_venue_id"] is None


def test_doi_selection_is_deterministic_and_capped():
    frame = pd.DataFrame({"doi": [f"https://doi.org/10.1234/{i}" for i in range(8)],
                          "work_id": [f"W{i}" for i in range(8)],
                          "publication_year": [2020, 2021] * 4,
                          "source_id": ["S1", None] * 4})
    a = select_dois(frame, 4)
    b = select_dois(frame.sample(frac=1, random_state=9), 4)
    assert a.doi.tolist() == b.doi.tolist()
    with pytest.raises(ValueError):
        select_dois(frame, 1001)


def test_raw_response_atomic_and_resume_checksum(tmp_path: Path):
    path = tmp_path / "response.json"
    atomic_bytes(path, b'{"message":{}}')
    with pytest.raises(FileExistsError):
        atomic_bytes(path, b"replacement")
    manifest_path = tmp_path / "manifest.json"
    manifest = checked_manifest(manifest_path, provider="crossref", identifiers=["doi"], cap=2)
    import hashlib
    manifest["requests"] = [{"identifier": "doi", "raw_path": "response.json",
                              "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}]
    manifest_path.write_text(json.dumps(manifest))
    checked_manifest(manifest_path, provider="crossref", identifiers=["doi"], cap=2)
    path.write_bytes(b"tampered")
    with pytest.raises(ValueError):
        checked_manifest(manifest_path, provider="crossref", identifiers=["doi"], cap=2)
    with pytest.raises(ValueError):
        checked_manifest(manifest_path, provider="crossref", identifiers=["other"], cap=2)


def test_collector_budget_and_mock_response(tmp_path: Path):
    class Response:
        status_code = 404
        content = b'{"status":"resource not found"}'
        headers = {}
    class Session:
        headers = {}
        def get(self, url, timeout):
            return Response()
    collector = CrossrefCollector(session=Session(), sleep=lambda _: None)
    doi = "https://doi.org/10.1234/x"
    manifest = collector.collect([doi], tmp_path, cap=1)
    assert manifest["not_found"] == 1
    assert manifest["http_attempts"] == 1
    assert collector.collect([doi], tmp_path, cap=1)["http_attempts"] == 1
    with pytest.raises(ValueError):
        collector.collect([doi, doi], tmp_path, cap=2)


def test_interrupted_raw_write_is_quarantined_not_checkpointed(tmp_path: Path):
    raw = tmp_path / "crossref_raw"
    raw.mkdir()
    partial = raw / ".abc.json.partial"
    partial.write_bytes(b'{"broken":')
    manifest = {"requests": []}
    quarantine_orphans(tmp_path, raw, manifest)
    assert not partial.exists()
    assert (tmp_path / "quarantine" / ".abc.json.partial.orphan").read_bytes() == b'{"broken":'
    assert manifest["quarantined_orphans"][0]["bytes"] == 10


def test_rate_limit_retry_stops_at_actual_request_cap(tmp_path: Path):
    class Response:
        status_code = 429
        content = b'{"error":"rate limited"}'
        headers = {"Retry-After": "0"}
    class Session:
        headers = {}
        calls = 0
        def get(self, url, timeout):
            self.calls += 1
            return Response()
    session = Session()
    result = CrossrefCollector(session=session, sleep=lambda _: None).collect(
        ["https://doi.org/10.1234/x"], tmp_path, cap=1)
    assert session.calls == 1
    assert result["http_attempts"] == 1
    assert result["status"] == "incomplete"
    assert (tmp_path / "crossref_request_manifest.json").is_file()


def test_temporal_pool_and_metrics():
    train = pd.DataFrame({"work_id": ["w1", "w2", "w3"],
        "canonical_venue_id": ["v1", "v1", "v2"],
        "venue_type": ["journal", "journal", "repository"],
        "display_name": ["J", "J", "R"]})
    pool, venues = build_candidate_pool(train, 2)
    assert len(pool) == 2 and venues.canonical_venue_id.tolist() == ["v1"]
    actual = ["v1", "v2", None]
    result = metrics_for_predictions(actual, [["v1"], ["v1"], ["v1"]], {"v1"})
    assert result["candidate_coverage"] == pytest.approx(1 / 3)
    assert result["recall_at_1"] == pytest.approx(1 / 3)
    assert result["mrr_at_10"] == pytest.approx(1 / 3)
    assert rank_from_scores({}, set()) == []
    with pytest.raises(ValueError):
        query_text("", "abstract")


def test_temporal_cutoff_and_version_isolation():
    train = pd.DataFrame({"work_id": ["w1"], "version_group": ["g1"],
                          "publication_year": [2023]})
    dev = pd.DataFrame({"work_id": ["w2"], "version_group": ["g2"],
                        "publication_year": [2024]})
    validate_temporal_frames(train, dev)
    with pytest.raises(ValueError, match="version-group"):
        validate_temporal_frames(train, dev.assign(version_group="g1"))
    with pytest.raises(ValueError, match="Temporal"):
        validate_temporal_frames(train, dev.assign(publication_year=2025))


def test_text_retrieval_abstains_without_lexical_evidence():
    from sklearn.feature_extraction.text import TfidfVectorizer
    vectorizer = TfidfVectorizer().fit(["cat dog"])
    matrix = vectorizer.transform(["cat dog"])
    index = {"vectorizer": vectorizer, "matrix": matrix, "profiles": matrix,
             "doc_venues": ["v1"], "venue_ids": ["v1"]}
    assert rank_text(index, "galaxy quasar", method="v2_tfidf_papers") == []
    assert rank_text(index, "galaxy quasar", method="v3_venue_profiles") == []


def test_paired_provider_gains_reject_row_misalignment():
    before = pd.DataFrame({"work_id": ["w1", "w2"], "doi": ["d1", "d2"],
        "openalex_publisher": [None, None], "crossref_publisher": [None, None]})
    after = pd.DataFrame({"work_id": ["w1", "w2"], "doi": ["d1", "d2"],
        "openalex_publisher": ["P", None], "crossref_publisher": [None, "Q"]}, index=[10, 20])
    assert paired_provider_gains(before, after) == {
        "source_api_publisher_recovered": 1,
        "crossref_publisher_available_where_local_missing": 1}
    with pytest.raises(ValueError, match="misaligned"):
        paired_provider_gains(before, after.iloc[::-1])


def test_manual_topic_input_must_be_valid_openalex_id():
    service = VenueDiscoveryService.__new__(VenueDiscoveryService)
    with pytest.raises(ValueError, match="OpenAlex Topic ID"):
        service.discover_publication_venues("title", "a meaningful abstract", selected_topic_id="journal-name")
