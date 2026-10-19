import pytest

from ai_research_trends.crawling.discover_topics import parse_topic_response
from ai_research_trends.crawling.openalex_client import OpenAlexError


def test_parse_topic_response_preserves_hierarchy_and_evidence() -> None:
    parsed = parse_topic_response(
        {
            "id": "https://openalex.org/T12026",
            "display_name": "Explainable Artificial Intelligence (XAI)",
            "description": "Interpretable models",
            "subfield": {
                "id": "https://openalex.org/subfields/1702",
                "display_name": "Artificial Intelligence",
            },
            "field": {"id": "https://openalex.org/fields/17", "display_name": "Computer Science"},
            "domain": {"id": "https://openalex.org/domains/3", "display_name": "Physical Sciences"},
            "works_count": 123,
            "updated_date": "2026-10-18T03:01:31",
        }
    )
    assert parsed["short_id"] == "T12026"
    assert parsed["subfield"]["display_name"] == "Artificial Intelligence"
    assert parsed["singleton_api_url"].endswith("/T12026")


def test_parse_topic_response_rejects_missing_identity() -> None:
    with pytest.raises(OpenAlexError):
        parse_topic_response({"display_name": "No ID"})
