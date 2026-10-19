from ai_research_trends.config import is_primary_corpus_work, load_config
from ai_research_trends.crawling.collect_aggregates import _query_specs
from ai_research_trends.crawling.profile_pilot import (
    include_in_primary_analysis,
    missing_affiliation_metadata,
)
from ai_research_trends.preprocessing.categories import classify_work


def _work(**overrides):
    value = {
        "id": "https://openalex.org/W1",
        "title": "A large language model with retrieval-augmented generation",
        "abstract_inverted_index": None,
        "publication_year": 2025,
        "type": "article",
        "primary_topic": {
            "subfield": {"id": "https://openalex.org/subfields/1702"}
        },
        "topics": [
            {"id": "https://openalex.org/T10028"},
            {"id": "https://openalex.org/T11714"},
        ],
        "authorships": [],
        "is_retracted": False,
    }
    value.update(overrides)
    return value


def test_population_aggregation_uses_exact_fixed_filter() -> None:
    config = load_config("config/topics.yaml")
    specs = _query_specs(config)
    expected = (
        "from_publication_date:2020-01-01,to_publication_date:2025-12-31,"
        "primary_topic.subfield.id:1702|1707,type:article|review|preprint"
    )
    by_name = {spec["name"]: spec for spec in specs}
    assert by_name["study_population_all"]["params"] == {
        "filter": expected,
        "group_by": "publication_year",
    }
    assert by_name["study_population_primary_non_retracted"]["params"] == {
        "filter": f"{expected},is_retracted:false",
        "group_by": "publication_year",
    }
    assert all(spec["params"]["filter"].startswith(expected) for spec in specs)
    assert all(
        spec["params"]["filter"].endswith("is_retracted:false")
        or ",is_retracted:false,topics.id:" in spec["params"]["filter"]
        for spec in specs
        if spec["estimand_role"] == "primary"
    )
    assert all("search." not in spec["params"] for spec in specs)


def test_overlapping_categories_remain_separate_by_layer() -> None:
    matches = classify_work(_work(), load_config("config/topics.yaml"))
    assert matches.openalex_native == frozenset(
        {"natural_language_processing", "multimodal_machine_learning_applications"}
    )
    assert matches.custom_emerging == frozenset(
        {"large_language_models", "retrieval_augmented_generation"}
    )


def test_primary_topic_corpus_membership_requires_all_boundaries() -> None:
    study = load_config("config/topics.yaml")["study"]
    assert is_primary_corpus_work(_work(), study)
    assert not is_primary_corpus_work(_work(publication_year=2026), study)
    assert not is_primary_corpus_work(_work(type="book"), study)
    assert not is_primary_corpus_work(
        _work(primary_topic={"subfield": {"id": "https://openalex.org/subfields/2701"}}),
        study,
    )


def test_missing_affiliation_requires_usable_nested_values() -> None:
    assert missing_affiliation_metadata(_work(authorships=None)) == (True, True)
    assert missing_affiliation_metadata(
        _work(authorships=[{"institutions": [{"id": None}], "countries": [""]}])
    ) == (True, True)
    assert missing_affiliation_metadata(
        _work(
            authorships=[
                {
                    "institutions": [{"id": "https://openalex.org/I1"}],
                    "countries": ["VN"],
                }
            ]
        )
    ) == (False, False)


def test_retractions_are_retained_but_excluded_from_primary_analysis() -> None:
    assert include_in_primary_analysis(_work()) is True
    assert include_in_primary_analysis(_work(is_retracted=True)) is False
    assert include_in_primary_analysis(_work(is_retracted=None)) is True
