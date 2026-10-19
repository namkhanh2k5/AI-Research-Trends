from ai_research_trends.crawling.validate_topics import validate


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
