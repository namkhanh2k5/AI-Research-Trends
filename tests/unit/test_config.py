from pathlib import Path

import pytest

from ai_research_trends.config import (
    build_primary_analysis_filter,
    build_study_filter,
    build_year_stratum_filter,
    load_config,
    validate_corpus_work,
)


def test_project_config_loads() -> None:
    config = load_config(Path("config/topics.yaml"))
    assert config["study"]["pilot_size"] == 1000
    assert "retrieval_augmented_generation" in config["custom_emerging_technologies"]
    assert "natural_language_processing" in config["openalex_native_categories"]


def test_build_study_filter_is_explicit() -> None:
    value = build_study_filter(
        {
            "start_date": "2020-01-01",
            "end_date": "2025-12-31",
            "work_types": ["article", "review", "preprint"],
            "primary_subfield_ids": ["1702", "1707"],
            "primary_retraction_scope": "non_retracted",
        }
    )
    assert "from_publication_date:2020-01-01" in value
    assert "to_publication_date:2025-12-31" in value
    assert "primary_topic.subfield.id:1702|1707" in value
    assert "type:article|review|preprint" in value
    assert "is_retracted" not in value


def test_primary_filter_excludes_retracted_works() -> None:
    study = load_config("config/topics.yaml")["study"]
    assert build_primary_analysis_filter(study).endswith("is_retracted:false")


def test_year_stratum_filter_has_exact_boundaries() -> None:
    study = load_config("config/topics.yaml")["study"]
    value = build_year_stratum_filter(study, 2023)
    assert value.startswith(
        "from_publication_date:2023-01-01,to_publication_date:2023-12-31,"
    )
    assert value.endswith("is_retracted:false")
    with pytest.raises(ValueError, match="outside"):
        build_year_stratum_filter(study, 2026)


def test_build_study_filter_rejects_population_drift() -> None:
    with pytest.raises(ValueError, match="approved AI/CV corpus"):
        build_study_filter(
            {
                "start_date": "2021-01-01",
                "end_date": "2025-12-31",
                "work_types": ["article", "review", "preprint"],
                "primary_subfield_ids": ["1702", "1707"],
                "primary_retraction_scope": "non_retracted",
            }
        )


def _work(publication_date: str = "2020-01-01", publication_year: int = 2020) -> dict:
    return {
        "publication_date": publication_date,
        "publication_year": publication_year,
        "type": "article",
        "primary_topic": {
            "subfield": {"id": "https://openalex.org/subfields/1702"}
        },
        "is_retracted": False,
    }


def test_corpus_validation_enforces_inclusive_date_boundaries() -> None:
    study = load_config("config/topics.yaml")["study"]
    assert validate_corpus_work(_work("2020-01-01", 2020), study).valid
    assert validate_corpus_work(_work("2025-12-31", 2025), study).valid
    assert "publication_date_out_of_bounds" in validate_corpus_work(
        _work("2019-12-31", 2019), study
    ).errors
    assert "publication_date_out_of_bounds" in validate_corpus_work(
        _work("2026-01-01", 2026), study
    ).errors


def test_corpus_validation_flags_date_year_mismatch_and_retraction() -> None:
    study = load_config("config/topics.yaml")["study"]
    result = validate_corpus_work(
        {**_work("2024-12-31", 2025), "is_retracted": True},
        study,
        require_non_retracted=True,
    )
    assert result.publication_date_year_inconsistent is True
    assert "publication_date_year_inconsistent" in result.errors
    assert "not_explicitly_non_retracted" in result.errors
