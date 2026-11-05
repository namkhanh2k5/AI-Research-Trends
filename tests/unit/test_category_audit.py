from ai_research_trends.config import load_config
from ai_research_trends.crawling.audit_categories import build_audit_candidates


def _work(identifier: int, title: str) -> dict:
    return {
        "id": f"W{identifier}",
        "title": title,
        "abstract_inverted_index": None,
        "publication_year": 2025,
    }


def test_audit_candidates_include_deterministic_positives_and_negatives() -> None:
    rows = [
        _work(1, "A large language model for science"),
        _work(2, "A vision-language model"),
        _work(3, "Retrieval-augmented generation for search"),
        _work(4, "Unrelated optimization method"),
        _work(5, "Another unrelated method"),
    ]
    config = load_config("config/topics.yaml")
    first = build_audit_candidates(
        rows, config, seed=7, positive_per_category=1, negative_per_category=2
    )
    second = build_audit_candidates(
        rows, config, seed=7, positive_per_category=1, negative_per_category=2
    )
    assert first["categories"] == second["categories"]
    for audit in first["categories"].values():
        assert audit["positive_candidates"] == 1
        assert audit["negative_candidates"] == 2
        assert all(row["manual_judgment"] is None for row in audit["candidates"])
