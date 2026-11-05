"""Topic discovery parsing and validation share one taxonomy contract."""

import pytest

from ai_research_trends.crawling.discover_topics import parse_topic_response
from ai_research_trends.crawling.openalex_client import OpenAlexError
from ai_research_trends.crawling.validate_topics import validate


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


class FakeClient:
    def get_json(self, path: str, params: dict) -> dict:
        assert path == "topics/T12026"
        assert "display_name" in params["select"]
        return {
            "id": "https://openalex.org/T12026",
            "display_name": "Explainable Artificial Intelligence (XAI)",
            "subfield": {"id": "https://openalex.org/subfields/1702"},
        }


def test_validate_topic_identity() -> None:
    config = {
        "openalex_native_categories": {
            "explainable_ai": {
                "verified_topics": [
                    {
                        "id": "T12026",
                        "display_name": "Explainable Artificial Intelligence (XAI)",
                        "subfield_id": "1702",
                    }
                ]
            }
        }
    }
    report = validate(config, FakeClient())
    assert report["all_valid"] is True
    assert report["checks"][0]["valid"] is True
