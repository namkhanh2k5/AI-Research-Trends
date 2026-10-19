import json
from pathlib import Path

from ai_research_trends.config import load_config
from ai_research_trends.crawling.profile_pilot import profile


def test_profile_handles_null_and_missing_metadata(tmp_path: Path) -> None:
    path = tmp_path / "works.jsonl"
    row = {
        "id": "https://openalex.org/W1",
        "doi": None,
        "title": "Minimal record",
        "abstract_inverted_index": None,
        "publication_year": 2025,
        "publication_date": "2025-06-15",
        "type": "article",
        "language": None,
        "cited_by_count": None,
        "fwci": None,
        "primary_topic": None,
        "topics": None,
        "open_access": None,
        "authorships": None,
    }
    path.write_text(json.dumps(row) + "\n", encoding="utf-8")
    config = load_config("config/topics.yaml")

    result = profile(path, config)
    assert result["records"] == 1
    assert result["missing_count"]["doi"] == 1
    assert result["missing_count"]["authorships"] == 1
    assert result["missing_authorship_institution_count"] == 1
    assert result["language_available_count"] == 0
    assert result["citation_distribution"]["available_count"] == 0
    assert result["primary_corpus_membership"]["violating_records"] == 1


def test_profile_quarantines_malformed_abstract_without_dropping_work(tmp_path: Path) -> None:
    path = tmp_path / "works.jsonl"
    row = {
        "id": "W2",
        "title": "A neutral record",
        "abstract_inverted_index": {"broken": "positions"},
        "publication_date": "2025-01-02",
        "publication_year": 2025,
        "type": "article",
        "is_retracted": False,
        "primary_topic": {
            "subfield": {"id": "https://openalex.org/subfields/1702"}
        },
        "topics": [{"id": "https://openalex.org/T12026"}],
        "authorships": [],
    }
    path.write_text(json.dumps(row) + "\n", encoding="utf-8")
    result = profile(path, load_config("config/topics.yaml"))
    quarantine = result["custom_text_classification_quarantine"]
    assert result["records"] == 1
    assert quarantine["count"] == 1
    assert result["category_match_count"]["openalex_native"] == {"explainable_ai": 1}
    assert result["category_match_count"]["custom_emerging"] == {}
