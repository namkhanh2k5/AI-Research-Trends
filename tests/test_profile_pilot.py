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
