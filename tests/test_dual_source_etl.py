"""Offline invariants for the isolated dual-provider RQ7 pilot."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from ai_research_trends.experiments.dual_source.core import (
    integrate_record, normalize_crossref, normalize_openalex, plain_crossref_abstract,
    proportional_allocation, quality_counts, safe_doi, select_cohort,
)
from ai_research_trends.experiments.dual_source.pipeline import (
    _checked, _openalex_records, _quarantine_uncheckpointed, _store_response,
    crossref_session, reserve_attempt,
)
from ai_research_trends.preprocessing.validate_tables import file_sha256


def _work(i: int) -> dict:
    return {"id": f"https://openalex.org/W{i}", "doi": f"https://doi.org/10.1234/x{i}",
            "display_name": "A  Vietnamese   title", "publication_date": "2022-05-01",
            "publication_year": 2022, "type": "article", "is_retracted": False,
            "abstract_inverted_index": {"Xin": [0], "chào": [1]},
            "primary_location": {"source": {"id": "https://openalex.org/S1",
                                               "display_name": "Journal", "issn": ["0378-5955"]}},
            "open_access": {"is_oa": True, "oa_status": "gold"}}


def _crossref(doi: str = "10.1234/x1") -> dict:
    return {"message": {"DOI": doi, "title": ["A Vietnamese title"],
                        "container-title": ["Journal"], "publisher": "Publisher",
                        "ISSN": ["0378-5955"], "published": {"date-parts": [[2022, 5, 1]]},
                        "abstract": "<jats:p>Xin &amp; chào</jats:p>",
                        "license": [{"URL": "https://example.org/license"}]}}


def test_allocation_deterministic_and_exact():
    assert proportional_allocation({"a": 2, "b": 2, "c": 2}, 4) == {"a": 2, "b": 1, "c": 1}
    with pytest.raises(ValueError):
        proportional_allocation({"a": 1}, 2)


def test_selection_disjoint_and_deterministic():
    works = pd.DataFrame([{"work_id": f"https://openalex.org/W{i}", "publication_year": 2022 + i % 2,
                           "work_type": "article", "doi": f"https://doi.org/10.1234/x{i}",
                           "is_retracted": False} for i in range(1, 11)])
    venue = pd.DataFrame([{"work_id": f"https://openalex.org/W{i}",
                           "dataset_origin": "original_analytical_sample", "publisher": None,
                           "source_name": None, "issn_l": None, "source_id": None}
                          for i in range(1, 11)])
    first = select_cohort(works, venue, general_n=4, targeted_n=2)
    second = select_cohort(works, venue, general_n=4, targeted_n=2)
    pd.testing.assert_frame_equal(first, second)
    assert len(first) == first.work_id.nunique() == 6
    assert first.group.value_counts().to_dict() == {"A_GENERAL": 4, "B_TARGETED_MISSINGNESS": 2}


def test_doi_status_and_crossref_mismatch():
    assert safe_doi(" doi:10.1234/ABC ") == ("https://doi.org/10.1234/abc", "VALID")
    assert safe_doi(None) == (None, "DOI_MISSING")
    assert safe_doi("not-a-doi") == (None, "DOI_INVALID")
    assert safe_doi("https://doi.org/10.1234%2FABC") == ("https://doi.org/10.1234/abc", "VALID")
    with pytest.raises(ValueError, match="mismatch"):
        normalize_crossref(_crossref(), "10.1234/other")


def test_openalex_normalization_and_malformed_abstract():
    normalized = normalize_openalex(_work(1))
    assert normalized["abstract"] == "Xin chào"
    assert normalized["title"] == "A Vietnamese title"
    assert normalized["publisher"] is None
    assert normalized["issns"] == ["0378-5955"]
    work = _work(2)
    work["abstract_inverted_index"] = {"bad": [-1]}
    assert normalize_openalex(work)["abstract_status"] == "MALFORMED"
    assert normalize_openalex(work)["abstract"] is None
    work = _work(3)
    work["publication_year"] = 2023
    with pytest.raises(ValueError, match="year/date"):
        normalize_openalex(work)


def test_crossref_parsing_dates_markup_and_missing():
    parsed = normalize_crossref(_crossref(), "https://doi.org/10.1234/x1")
    assert parsed["publication_year"] == 2022
    assert parsed["dates"]["published"] == "2022-05-01"
    assert parsed["abstract"] == "Xin & chào"
    assert plain_crossref_abstract(None) is None
    partial = _crossref()
    partial["message"].pop("published")
    assert normalize_crossref(partial, "10.1234/x1")["publication_year"] is None


def test_integration_recovery_provenance_and_conflict():
    oa = normalize_openalex(_work(1))
    cr = normalize_crossref(_crossref(), "10.1234/x1")
    merged, provenance, conflicts = integrate_record(oa, cr, "EXACT_DOI_MATCH")
    assert merged["publisher"] == "Publisher"
    assert next(x for x in provenance if x["field"] == "publisher")["selected_source"] == "crossref"
    assert merged["publication_year"] == 2022
    cr["publication_year"] = 2023
    merged, _, conflicts = integrate_record(oa, cr, "EXACT_DOI_MATCH")
    assert merged["publication_year"] == 2022
    assert any(x["field"] == "publication_year" for x in conflicts)
    assert merged["match_status"] == "EXACT_DOI_MATCH"


def test_retraction_evidence_does_not_clear_openalex_flag():
    oa = normalize_openalex(_work(1))
    oa["is_retracted"] = True
    cr = normalize_crossref(_crossref(), "10.1234/x1")
    merged, _, conflicts = integrate_record(oa, cr, "EXACT_DOI_MATCH")
    assert merged["is_retracted"] is True
    assert not any(x["field"] == "is_retracted" for x in conflicts)
    cr["retraction_evidence"] = True
    oa["is_retracted"] = False
    merged, _, conflicts = integrate_record(oa, cr, "EXACT_DOI_MATCH")
    assert merged["is_retracted"] is False
    assert any(x["field"] == "is_retracted" for x in conflicts)


def test_quality_denominators_and_duplicates():
    rows = [normalize_openalex(_work(1)), normalize_openalex(_work(1))]
    quality = quality_counts(rows)
    assert quality["records"] == 2
    assert quality["duplicate_work_ids"] == 1
    assert quality["duplicate_dois"] == 1


def test_atomic_raw_checksum_and_orphan_quarantine(tmp_path: Path):
    entry = _store_response(tmp_path, "crossref", "10.1234/test", b'{"ok":true}', status=200)
    _checked(tmp_path / entry["path"], tmp_path, entry)
    orphan = tmp_path / "raw" / "crossref" / ".partial"
    orphan.write_bytes(b"broken")
    moved = _quarantine_uncheckpointed(tmp_path, orphan.parent, [entry])
    assert len(moved) == 1
    assert not orphan.exists()
    assert (tmp_path / moved[0]["path"]).read_bytes() == b"broken"
    (tmp_path / entry["path"]).write_bytes(b"tampered")
    with pytest.raises(ValueError, match="checkpoint"):
        _checked(tmp_path / entry["path"], tmp_path, entry)


def test_normalize_crossref_invalid_issn_preserved():
    payload = _crossref()
    payload["message"]["ISSN"] = ["0000-0001"]
    parsed = normalize_crossref(payload, "10.1234/x1")
    assert parsed["invalid_issns"] == ["0000-0001"]


def test_no_fuzzy_match_without_doi():
    oa = normalize_openalex(_work(1))
    oa["doi"] = None
    oa["doi_status"] = "DOI_MISSING"
    merged, _, _ = integrate_record(oa, None, "DOI_MISSING")
    assert merged["match_status"] == "DOI_MISSING"
    assert merged["publisher"] is None


def test_request_cap_persists_in_manifest_state():
    manifest = {"crossref_http_attempts": 1}
    reserve_attempt(manifest, "crossref", 2)
    assert manifest["crossref_http_attempts"] == 2
    with pytest.raises(RuntimeError, match="cap exhausted"):
        reserve_attempt(manifest, "crossref", 2)
    assert manifest["crossref_http_attempts"] == 2


def test_crossref_polite_session_configuration():
    session = crossref_session("researcher@example.org")
    assert session.params["mailto"] == "researcher@example.org"
    assert "researcher@example.org" not in session.headers["User-Agent"]
    assert "Authorization" not in session.headers
    with pytest.raises(ValueError):
        crossref_session("")


def test_openalex_alias_requires_explicit_checkpoint_mapping(tmp_path: Path):
    payload = {"meta": {"count": 1}, "results": [_work(99)]}
    entry = _store_response(tmp_path, "openalex", "batch:000",
                            json.dumps(payload).encode(), status=200)
    entry["aliases"] = {"https://openalex.org/W1": "https://openalex.org/W99"}
    assert list(_openalex_records(tmp_path, {"openalex": [entry]})) == ["https://openalex.org/W1"]
    entry["aliases"] = {}
    assert list(_openalex_records(tmp_path, {"openalex": [entry]})) == ["https://openalex.org/W99"]


def test_selection_excludes_2025_and_retracted_frame():
    works = pd.DataFrame([{"work_id": f"https://openalex.org/W{i}",
                           "publication_year": 2025 if i == 5 else 2022,
                           "work_type": "article", "doi": f"10.1234/x{i}",
                           "is_retracted": i == 2} for i in range(1, 6)])
    venue = pd.DataFrame([{"work_id": f"https://openalex.org/W{i}",
                           "dataset_origin": "original_analytical_sample", "publisher": None,
                           "source_name": None, "issn_l": None, "source_id": None}
                          for i in range(1, 6)])
    with pytest.raises(ValueError, match="non-retracted"):
        select_cohort(works, venue, general_n=2, targeted_n=1)
