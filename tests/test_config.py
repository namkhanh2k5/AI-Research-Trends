from pathlib import Path

import pytest

from ai_research_trends.config import (
    build_primary_analysis_filter,
    build_study_filter,
    load_config,
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
