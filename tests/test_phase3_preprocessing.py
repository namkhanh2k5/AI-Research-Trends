"""Small, offline fixtures for Phase 3 normalization and integrity controls."""

import hashlib
import json
import math
from copy import deepcopy
from datetime import date
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from ai_research_trends.config import load_config
from ai_research_trends.features.bibliometric import add_category_features
from ai_research_trends.preprocessing.common import (
    entity_id,
    normalize_doi,
    parse_utc,
    publication_age_years,
)
from ai_research_trends.preprocessing.normalize_authorships import normalize_authorships
from ai_research_trends.preprocessing.normalize_categories import normalize_categories
from ai_research_trends.preprocessing.normalize_references import normalize_references
from ai_research_trends.preprocessing.normalize_topics import normalize_topics
from ai_research_trends.preprocessing.normalize_works import normalize_work
from ai_research_trends.preprocessing import pipeline
from ai_research_trends.preprocessing.quality_report import render_report
from ai_research_trends.preprocessing.schemas import SCHEMAS
from ai_research_trends.preprocessing.validate_tables import (
    ProcessedValidationError,
    expected_collaboration_flag,
    validate_rows,
)


WORK_ID = "https://openalex.org/W123"
OTHER_ID = "https://openalex.org/W456"


def _source() -> dict:
    return {
        "id": WORK_ID,
        "doi": " DOI:10.1234/TeSt ",
        "title": "  Retrieval-augmented generation with Large Language Models  in Multimodal AI  ",
        "abstract_inverted_index": {"Xin": [0], "chào": [1]},
        "publication_date": "2020-06-01",
        "publication_year": 2020,
        "type": "article",
        "is_retracted": False,
        "language": None,
        "cited_by_count": 0,
        "fwci": None,
        "open_access": {"is_oa": True, "oa_status": "gold"},
        "primary_topic": {
            "id": "https://openalex.org/T10181",
            "subfield": {"id": "https://openalex.org/subfields/1702"},
            "field": {"id": "https://openalex.org/fields/17"},
            "domain": {"id": "https://openalex.org/domains/3"},
        },
        "topics": [
            {
                "id": "https://openalex.org/T10181",
                "display_name": "NLP",
                "score": 0.9,
                "subfield": {"id": "https://openalex.org/subfields/1702"},
                "field": {"id": "https://openalex.org/fields/17"},
                "domain": {"id": "https://openalex.org/domains/3"},
            }
        ],
        "authorships": [
            {
                "author_position": "first",
                "author": {"id": "https://openalex.org/A1", "display_name": "Nguyễn  Văn A"},
                "is_corresponding": True,
                "institutions": [
                    {"id": "https://openalex.org/I1", "display_name": "University A", "country_code": "VN", "type": "education"},
                ],
                "countries": ["VN"],
            },
            {
                "author_position": "last",
                "author": {"id": None, "display_name": "Missing ID"},
                "is_corresponding": False,
                "institutions": [
                    {"id": "https://openalex.org/I1", "display_name": "University A", "country_code": "VN", "type": "education"},
                ],
                "countries": ["VN"],
            },
        ],
        "corresponding_institution_ids": ["https://openalex.org/I1"],
        "referenced_works": [OTHER_ID, OTHER_ID, "bad-reference"],
        "referenced_works_count": 3,
    }


def _normalized(source: dict | None = None):
    source = source or _source()
    config = load_config("config/topics.yaml")
    work, issues = normalize_work(
        source, study=config["study"], observation_time=parse_utc("2026-10-19T16:03:40Z"),
        run_id="fixture", sampling_weight=10.0,
    )
    return work, issues


def test_work_normalization_preserves_unicode_nulls_and_citations() -> None:
    work, issues = _normalized()
    assert not issues
    assert work["title"].endswith("Multimodal AI")
    assert work["abstract"] == "Xin chào"
    assert work["doi"] == "https://doi.org/10.1234/test"
    assert work["language"] is None and work["fwci"] is None
    assert work["cited_by_count"] == 0 and work["log1p_citations"] == 0
    assert work["zero_citation_flag"] is True and work["has_fwci"] is False
    assert work["sampling_weight"] == 10.0
    assert work["publication_age_years"] > 0
    assert work["reference_list_status"] == "present"


def test_doi_and_identifier_normalization_rejects_invalid_values() -> None:
    assert normalize_doi(None) is None
    assert normalize_doi("https://doi.org/10.9999/AbC") == "https://doi.org/10.9999/abc"
    assert entity_id("A123", "A") == "https://openalex.org/A123"
    with pytest.raises(ValueError, match="Malformed DOI"):
        normalize_doi("not-a-doi")
    with pytest.raises(ValueError, match="Expected OpenAlex A ID"):
        entity_id("https://openalex.org/I123", "A")


def test_abstract_malformed_index_is_quarantined_without_dropping_work() -> None:
    source = _source()
    source["abstract_inverted_index"] = {"x": [0, 0]}
    work, issues = _normalized(source)
    assert work["abstract"] is None and not work["has_abstract"]
    assert len(issues) == 1 and issues[0]["field"] == "abstract_inverted_index"
    categories, reason = normalize_categories(source, WORK_ID, load_config("config/topics.yaml"), "a" * 64)
    assert reason is not None
    assert {row["analytical_layer"] for row in categories} == {"openalex_native"}


def test_missing_reference_list_differs_from_empty_list() -> None:
    source = _source()
    source["referenced_works"] = None
    assert _normalized(source)[0]["reference_list_status"] == "missing"
    source["referenced_works"] = []
    assert _normalized(source)[0]["reference_list_status"] == "empty"


def test_topic_deduplication_keeps_first_rank_and_score() -> None:
    source = _source()
    source["topics"].append({**source["topics"][0], "score": 0.1})
    rows = normalize_topics(source, WORK_ID)
    assert len(rows) == 1 and rows[0]["topic_rank"] == 1
    assert rows[0]["topic_score"] == 0.9


def test_authorship_institution_country_deduplication_and_missing_author_id() -> None:
    authors, institutions, countries, features, issues = normalize_authorships(_source(), WORK_ID)
    assert not issues
    assert len(authors) == 2 and authors[1]["author_id"] is None
    assert authors[0]["author_name"] == "Nguyễn Văn A"
    assert len(institutions) == 1 and institutions[0]["is_corresponding_institution"]
    assert countries == [{"work_id": WORK_ID, "country_code": "VN", "country_provenance": "authorship_countries|institution_country_code"}]
    assert features["identified_author_count"] == 1
    assert features["unique_institution_count"] == features["unique_country_count"] == 1
    assert features["international_collaboration"] is False


def test_unknown_collaboration_is_not_domestic_false() -> None:
    source = _source()
    source["authorships"][1]["countries"] = []
    source["authorships"][1]["institutions"] = []
    _, _, _, features, _ = normalize_authorships(source, WORK_ID)
    assert features["country_affiliation_complete"] is False
    assert features["international_collaboration"] is None
    assert features["institutional_collaboration"] is None
    assert expected_collaboration_flag(0, False) is None


def test_reference_edges_keep_external_and_audit_invalid_duplicates() -> None:
    rows, issues = normalize_references(_source(), WORK_ID, {WORK_ID})
    assert rows == [{"citing_work_id": WORK_ID, "referenced_work_id": OTHER_ID, "referenced_in_sample": False}]
    assert {item["reason"] for item in issues} >= {"duplicate reference edge"}
    assert len(issues) == 2


def test_overlapping_native_and_custom_category_provenance() -> None:
    config = load_config("config/topics.yaml")
    rows, reason = normalize_categories(_source(), WORK_ID, config, "a" * 64)
    assert reason is None
    assert ("openalex_native", "natural_language_processing") in {(r["analytical_layer"], r["category"]) for r in rows}
    assert ("custom_emerging", "large_language_models") in {(r["analytical_layer"], r["category"]) for r in rows}
    assert ("custom_emerging", "retrieval_augmented_generation") in {(r["analytical_layer"], r["category"]) for r in rows}
    assert all(r["matched_rule_or_topic_ids"] for r in rows)


def test_publication_age_boundary_and_negative_age() -> None:
    observation = parse_utc("2026-10-19T00:00:00Z")
    assert publication_age_years(date(2026, 10, 19), observation) == 0
    with pytest.raises(ValueError, match="after"):
        publication_age_years(date(2026, 10, 20), observation)


def test_citation_outliers_and_missing_fwci_are_preserved() -> None:
    source = _source()
    source["cited_by_count"] = 4199
    work, _ = _normalized(source)
    assert work["cited_by_count"] == 4199
    assert math.isclose(work["log1p_citations"], math.log1p(4199))
    assert work["fwci"] is None and not work["has_fwci"]


@pytest.mark.parametrize("mutation,pattern", [
    ({"cited_by_count": -1}, "cited_by_count"),
    ({"fwci": -0.1}, "fwci"),
    ({"is_retracted": True}, "approved corpus"),
    ({"publication_date": "2026-01-01"}, "approved corpus"),
    ({"open_access": {"is_oa": False, "oa_status": "gold"}}, "inconsistent OA"),
])
def test_invalid_source_metadata_fails_loudly(mutation: dict, pattern: str) -> None:
    source = _source()
    source.update(mutation)
    with pytest.raises(ValueError, match=pattern):
        _normalized(source)


def _mini_tables():
    source = _source()
    source["referenced_works"] = [OTHER_ID]
    work, _ = _normalized(source)
    authors, institutions, countries, features, _ = normalize_authorships(source, WORK_ID)
    work.update(features)
    memberships, _ = normalize_categories(source, WORK_ID, load_config("config/topics.yaml"), "a" * 64)
    add_category_features(work, memberships)
    references, _ = normalize_references(source, WORK_ID, {WORK_ID})
    population = [{"series": "study_population_primary_non_retracted", "year": year, "work_count": 10,
                   "definition": "fixture", "retrieved_at_utc": parse_utc("2026-10-19T00:00:00Z"),
                   "query_hash": "a" * 64} for year in range(2020, 2026)]
    tables = {
        "works": [work], "work_topics": normalize_topics(source, WORK_ID),
        "authorships": authors, "work_institutions": institutions,
        "work_countries": countries, "references": references,
        "category_membership": memberships, "population_year_counts": population,
    }
    plan = {"allocated_sample_size": 1, "strata": [{"publication_year": 2020, "sample_size": 1, "sampling_weight": 10.0}]}
    return tables, plan, population


def test_relational_and_sampling_validation_passes_on_coherent_fixture() -> None:
    tables, plan, population = _mini_tables()
    checks = validate_rows(tables, plan, population, load_config("config/topics.yaml"))
    assert all(value["status"] == "PASS" for value in checks.values())


def test_relational_validation_rejects_orphan_bridge() -> None:
    tables, plan, population = _mini_tables()
    tables["work_topics"][0]["work_id"] = OTHER_ID
    with pytest.raises(ProcessedValidationError, match="work_topics_work_fk"):
        validate_rows(tables, plan, population, load_config("config/topics.yaml"))


def test_sampling_validation_rejects_wrong_weight() -> None:
    tables, plan, population = _mini_tables()
    tables["works"][0]["sampling_weight"] = 1.0
    with pytest.raises(ProcessedValidationError, match="nominal_weights"):
        validate_rows(tables, plan, population, load_config("config/topics.yaml"))


def test_deterministic_parquet_bytes_for_same_normalized_work(tmp_path: Path) -> None:
    tables, _, _ = _mini_tables()
    table = pa.Table.from_pylist(tables["works"], schema=SCHEMAS["works"])
    hashes = []
    for name in ("first.parquet", "second.parquet"):
        path = tmp_path / name
        pq.write_table(table, path, compression="zstd", version="2.6")
        hashes.append(hashlib.sha256(path.read_bytes()).hexdigest())
    assert hashes[0] == hashes[1]


def test_pipeline_failure_preserves_incomplete_diagnostic(tmp_path: Path, monkeypatch) -> None:
    def broken(**_kwargs):
        raise ValueError("source integrity failed")

    monkeypatch.setattr(pipeline, "process_collection", broken)
    output = tmp_path / "new-run"
    with pytest.raises(ValueError, match="source integrity failed"):
        pipeline.main([
            "--source-jsonl", "source.jsonl", "--source-manifest", "source-manifest.json",
            "--plan", "plan.json", "--population", "population.json",
            "--phase2-profile", "profile.json", "--output-dir", str(output),
        ])
    assert not output.exists()
    failures = list(tmp_path.glob("new-run.failure_*.json"))
    assert len(failures) == 1
    assert json.loads(failures[0].read_text())["status"] == "incomplete"


def test_quality_report_rejects_incomplete_run(tmp_path: Path) -> None:
    (tmp_path / "manifest.json").write_text('{"status":"incomplete","complete":false}')
    (tmp_path / "quality.json").write_text("{}")
    with pytest.raises(ValueError, match="incomplete"):
        render_report(tmp_path)
