"""Offline safeguards for independent metadata validation and the review gate."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from ai_research_trends.experiments.dual_source import validation_pipeline as pipeline
from ai_research_trends.experiments.dual_source.validation_core import (
    REVIEW_STATUS, STRATA, classify_404, classify_conflict, license_evidence,
    license_url_info, normalized_publisher, reviewed_correctness, select_review_sample,
    stable_key, wilson_interval,
)


def _fixture() -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    for i in range(40):
        rows.append({"work_id": f"https://openalex.org/W{i+1}", "doi": f"https://doi.org/10.1234/x{i}",
                     "title": f"Paper {i}", "publication_year": 2020+i%5,
                     "work_type": "article" if i%2 else "review",
                     "group": "A_GENERAL" if i%3 else "B_TARGETED_MISSINGNESS",
                     "publisher_source": "crossref" if i<10 else "openalex",
                     "license_source": "crossref" if 7<=i<20 else "openalex",
                     "match_status": "CROSSREF_NOT_FOUND" if i>=26 else "EXACT_DOI_MATCH"})
    conflicts = pd.DataFrame([{"work_id": f"https://openalex.org/W{i+1}"} for i in range(18,30)])
    return pd.DataFrame(rows), conflicts


def test_review_sample_deterministic_unique_and_secondary_flags():
    frame, conflicts = _fixture()
    a = select_review_sample(frame, conflicts, targets=(3, 3, 3, 3))
    b = select_review_sample(frame, conflicts, targets=(3, 3, 3, 3))
    pd.testing.assert_frame_equal(a, b)
    assert len(a) == a.work_id.nunique() == 12
    assert a.primary_review_stratum.value_counts().reindex(STRATA).tolist() == [3]*4
    assert a.review_status.eq(REVIEW_STATUS).all()
    assert a.loc[a.primary_review_stratum.eq(STRATA[0]), "publisher_recovered"].all()
    assert a.loc[a.primary_review_stratum.eq(STRATA[3]), "crossref_404"].all()


def test_review_hash_is_domain_separated_from_original_cohort_order():
    frame, conflicts = _fixture()
    sample = select_review_sample(frame, conflicts, targets=(2, 2, 2, 2))
    for row in sample.itertuples():
        assert row.sampling_order_key == stable_key(20261104, "rq7_1_review:" + row.work_id)
        assert row.sampling_order_key != stable_key(20261104, row.work_id)


def test_review_sampling_shortfall_fails_without_replacement():
    frame, conflicts = _fixture()
    with pytest.raises(ValueError, match="Insufficient disjoint"):
        select_review_sample(frame, conflicts, targets=(30, 0, 0, 0))
    duplicate = pd.concat([frame, frame.iloc[[0]]])
    with pytest.raises(ValueError, match="Invalid canonical"):
        select_review_sample(duplicate, conflicts, targets=(1, 1, 1, 1))


def test_review_sheet_keeps_provider_values_and_stays_unreviewed(tmp_path: Path):
    frame, conflicts = _fixture()
    sample = select_review_sample(frame, conflicts, targets=(1, 1, 1, 1))
    frame["publisher"] = "Recovered Inc"
    frame["license"] = json.dumps([{"URL": "https://creativecommons.org/licenses/by/4.0/"}])
    conflicts = pd.DataFrame([{"work_id": wid, "field": "publisher",
                               "openalex_value": "Original Inc", "crossref_value": "Recovered Inc"}
                              for wid in conflicts.work_id])
    sheets = pipeline._make_review_sheets(tmp_path, sample, frame, conflicts)
    assert len(sheets) == 4
    sheet = pd.read_csv(tmp_path / "review_sheet_s3_conflict.csv")
    assert sheet.loc[0, "original_provider_value"] == "Original Inc"
    assert sheet.loc[0, "recovered_or_compared_value"] == "Recovered Inc"
    assert sheet.review_decision.eq(REVIEW_STATUS).all()
    assert sheet.reviewer_id.isna().all()


def test_publisher_normalization_is_lexical_not_identity():
    assert normalized_publisher("  SPRINGER, Inc. ") == normalized_publisher("springer inc")
    assert normalized_publisher("Springer Nature") != normalized_publisher("Springer")
    assert normalized_publisher(None) is None


def test_license_url_and_version_are_not_reuse_permission():
    ev = license_evidence(json.dumps([{"URL": "https://creativecommons.org/licenses/by/4.0/",
                                       "content-version": "vor", "start": {"date-time": "2020-01-01"}}]))
    assert ev["license_identifiers"] == ["CC-BY-4.0"]
    assert ev["content_version_restriction"] is True
    assert ev["start_dates"] == ["2020-01-01"]
    assert ev["reuse_rights_status"] == "UNKNOWN"
    assert ev["license_semantics_verified"] is False
    assert license_url_info("javascript:bad")["url_syntax_valid"] is False
    assert license_evidence("not-json")["license_metadata_present"] is False


@pytest.mark.parametrize("field,left,right,expected", [
    ("work_type", "article", "journal-article", "TAXONOMY_DIFFERENCE"),
    ("publication_date", "2020-01-01", "2020-02-01", "DATE_DEFINITION_DIFFERENCE"),
    ("license", "cc-by", "[{'URL':'https://x'}]", "SCHEMA_INCOMPATIBILITY"),
    ("issns", "['1111-1111','2222-2222']", "['2222-2222']", "SCHEMA_INCOMPATIBILITY"),
    ("publisher", "ACME Inc", " acme, inc. ", "NORMALIZATION_DIFFERENCE"),
    ("publisher", "Publisher A", "Publisher B", "SEMANTIC_METADATA_CONFLICT"),
    ("abstract", "one", "two", "UNRESOLVED"),
])
def test_conflict_taxonomy(field, left, right, expected):
    result = classify_conflict({"field": field, "openalex_value": left, "crossref_value": right})
    assert result["classification"] == expected
    assert result["classification_rule"]
    assert result["confidence_category"] in ("HIGH", "MEDIUM", "LOW")


def test_crossref_404_requires_stored_404_and_agency_evidence():
    doi = "https://doi.org/10.1234/test"
    assert classify_404(doi, 404, "DataCite") == "NON_CROSSREF_REGISTRATION"
    assert classify_404(doi, 404, "Crossref") == "CROSSREF_REGISTERED_NOT_FOUND"
    assert classify_404(doi, 404, None) == "UNKNOWN_REASON"
    assert classify_404("invalid", 404, None) == "DOI_IDENTITY_PROBLEM"
    with pytest.raises(ValueError, match="stored Crossref"):
        classify_404(doi, 200, "DataCite")


def test_wilson_denominator_and_pending_review_are_not_accuracy():
    assert wilson_interval(0, 0) is None
    low, high = wilson_interval(5, 5)
    assert 0 < low < high <= 1
    with pytest.raises(ValueError):
        wilson_interval(2, 1)
    result = reviewed_correctness([REVIEW_STATUS]*30)
    assert result["reviewed"] == result["authoritatively_verifiable"] == 0
    assert result["correctness_among_verifiable"] is None
    assert result["wilson_95"] is None
    alias = reviewed_correctness(["VERIFIED_CORRECT", "ACCEPTABLE_ALIAS", "VERIFIED_INCORRECT"])
    assert alias["correct_or_acceptable_alias"] == 2
    assert alias["authoritatively_verifiable"] == 3


def test_source_checksum_expectation_detects_mutation(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(pipeline, "verify", lambda source: {"status": "PASS"})
    for name in ("plan.json", "cohort.parquet", "collection_manifest.json", "processing_manifest.json", "evaluation.json"):
        (tmp_path / name).write_text("original")
    out = tmp_path / "processed"
    out.mkdir()
    for i in range(9):
        (out / f"table{i}.parquet").write_text("original")
    baseline = pipeline.check_source(tmp_path)
    assert len(baseline) == 14
    (out / "table0.parquet").write_text("tampered")
    with pytest.raises(ValueError, match="checksums changed"):
        pipeline.check_source(tmp_path, baseline)


def test_agency_and_license_request_budget_rejected_before_http(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(pipeline, "verify_validation", lambda run: {"status": "PASS"})
    pipeline.save_json(tmp_path / "review_sample_manifest.json",
                       {"agency_request_cap": 20, "license_url_request_cap": 10})
    with pytest.raises(ValueError, match="budget exceeded"):
        pipeline.check_license_urls(tmp_path, max_requests=11)
    # Agency cap is checked after loading cases; provide an empty fixture.
    pd.DataFrame(columns=["work_id", "doi"]).to_parquet(tmp_path / "cases.parquet")
    manifest = pipeline.load_json(tmp_path / "review_sample_manifest.json")
    manifest["doi_404_cases"] = {"path": "cases.parquet"}
    pipeline.save_json(tmp_path / "review_sample_manifest.json", manifest)
    with pytest.raises(ValueError, match="budget exceeded"):
        pipeline.check_agencies(tmp_path, max_requests=21)


def test_source_backed_check_rejects_fake_human_adjudication(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(pipeline, "verify_validation", lambda run: {"status": "PASS"})
    sample = pd.DataFrame([{"work_id": "https://openalex.org/W1",
                            "doi": "https://doi.org/10.1234/x1",
                            "primary_review_stratum": STRATA[0]}])
    sample.to_parquet(tmp_path / "review_sample.parquet")
    pipeline.save_json(tmp_path / "review_sample_manifest.json",
                       {"sample": {"path": "review_sample.parquet"}})
    check = {"work_id": "https://openalex.org/W1", "doi": "https://doi.org/10.1234/x1",
             "status": "SOURCE_BACKED_CORRECT", "human_adjudicated": True,
             "evidence_urls": ["https://official.example/a", "https://directory.example/b"]}
    pipeline.save_json(tmp_path / "official_source_checks.json", {"checks": [check]})
    with pytest.raises(ValueError, match="cannot claim human"):
        pipeline.register_official_evidence(tmp_path)
    check["human_adjudicated"] = False
    pipeline.save_json(tmp_path / "official_source_checks.json", {"checks": [check]})
    result = pipeline.register_official_evidence(tmp_path)
    assert result == {"registered_source_backed_checks": 1, "human_adjudications": 0}
