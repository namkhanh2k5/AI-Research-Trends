"""Study configuration and population-frame invariants."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import yaml


FIXED_CORPUS = {
    "start_date": "2020-01-01",
    "end_date": "2025-12-31",
    "work_types": ("article", "review", "preprint"),
    "primary_subfield_ids": ("1702", "1707"),
    "primary_retraction_scope": "non_retracted",
}

RETRACTION_SCOPES = {"all", "non_retracted"}


@dataclass(frozen=True)
class CorpusValidation:
    """Result of validating one work against the fixed population frame."""

    valid: bool
    errors: tuple[str, ...]
    publication_date_year_inconsistent: bool


def load_config(path: str | Path = "config/topics.yaml") -> dict[str, Any]:
    """Load the study configuration and reject structurally unsafe inputs."""
    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)

    required_sections = {
        "study",
        "openalex_native_categories",
        "custom_emerging_technologies",
    }
    if not isinstance(config, dict) or not required_sections.issubset(config):
        raise ValueError(
            "Configuration must contain study, openalex_native_categories, and "
            "custom_emerging_technologies mappings"
        )

    validate_fixed_corpus(config["study"])
    native = config["openalex_native_categories"]
    custom = config["custom_emerging_technologies"]
    if not isinstance(native, dict) or not native:
        raise ValueError("At least one OpenAlex-native category is required")
    if not isinstance(custom, dict) or not custom:
        raise ValueError("At least one custom emerging-technology category is required")
    for slug, category in native.items():
        if not isinstance(category, dict) or not category.get("topic_ids"):
            raise ValueError(f"Native category {slug!r} needs at least one topic ID")
    for slug, category in custom.items():
        if not isinstance(category, dict) or not category.get("rule_groups"):
            raise ValueError(f"Custom category {slug!r} needs at least one rule group")
    return config


def validate_fixed_corpus(study: dict[str, Any]) -> None:
    """Reject configuration drift from the approved Phase 1 population estimand."""
    for key, expected in FIXED_CORPUS.items():
        actual = study.get(key)
        if isinstance(expected, tuple):
            actual = tuple(str(value) for value in (actual or []))
        if actual != expected:
            raise ValueError(
                f"Study {key!r} must be {expected!r} for the approved AI/CV corpus; "
                f"got {actual!r}"
            )


def build_study_filter(
    study: dict[str, Any], *, retraction_scope: str = "all"
) -> str:
    """Build the population filter for either all works or the primary estimand."""
    validate_fixed_corpus(study)
    if retraction_scope not in RETRACTION_SCOPES:
        raise ValueError(f"Unsupported retraction scope: {retraction_scope!r}")
    work_types = "|".join(str(value) for value in study["work_types"])
    subfields = "|".join(str(value) for value in study["primary_subfield_ids"])
    value = (
        f"from_publication_date:{study['start_date']},"
        f"to_publication_date:{study['end_date']},"
        f"primary_topic.subfield.id:{subfields},"
        f"type:{work_types}"
    )
    if retraction_scope == "non_retracted":
        value = f"{value},is_retracted:false"
    return value


def build_primary_analysis_filter(study: dict[str, Any]) -> str:
    """Build the non-retracted filter used by every primary analysis estimand."""
    return build_study_filter(study, retraction_scope=study["primary_retraction_scope"])


def build_year_stratum_filter(study: dict[str, Any], year: int) -> str:
    """Build the exact non-retracted filter for one complete study year."""
    validate_fixed_corpus(study)
    if year not in range(2020, 2026):
        raise ValueError(f"Year {year!r} is outside the approved study period")
    work_types = "|".join(str(value) for value in study["work_types"])
    subfields = "|".join(str(value) for value in study["primary_subfield_ids"])
    return (
        f"from_publication_date:{year}-01-01,"
        f"to_publication_date:{year}-12-31,"
        f"primary_topic.subfield.id:{subfields},"
        f"type:{work_types},is_retracted:false"
    )


def primary_subfield_id(work: dict[str, Any]) -> str | None:
    """Return the short subfield ID attached to a work's primary topic."""
    value = (((work.get("primary_topic") or {}).get("subfield") or {}).get("id"))
    if not isinstance(value, str) or not value:
        return None
    return value.rstrip("/").split("/")[-1]


def validate_corpus_work(
    work: dict[str, Any],
    study: dict[str, Any],
    *,
    require_non_retracted: bool = False,
) -> CorpusValidation:
    """Validate exact dates and all fixed-corpus membership invariants."""
    validate_fixed_corpus(study)
    errors: list[str] = []

    publication_date = work.get("publication_date")
    parsed_date: date | None = None
    if not isinstance(publication_date, str):
        errors.append("missing_or_invalid_publication_date")
    else:
        try:
            parsed_date = date.fromisoformat(publication_date)
        except ValueError:
            errors.append("missing_or_invalid_publication_date")

    year = work.get("publication_year")
    if not isinstance(year, int) or isinstance(year, bool):
        errors.append("missing_or_invalid_publication_year")

    inconsistent = bool(parsed_date and isinstance(year, int) and parsed_date.year != year)
    if inconsistent:
        errors.append("publication_date_year_inconsistent")

    if parsed_date is not None:
        start = date.fromisoformat(study["start_date"])
        end = date.fromisoformat(study["end_date"])
        if not start <= parsed_date <= end:
            errors.append("publication_date_out_of_bounds")

    if work.get("type") not in set(study["work_types"]):
        errors.append("work_type_out_of_scope")
    if primary_subfield_id(work) not in set(study["primary_subfield_ids"]):
        errors.append("primary_subfield_out_of_scope")
    if require_non_retracted and work.get("is_retracted") is not False:
        errors.append("not_explicitly_non_retracted")

    return CorpusValidation(
        valid=not errors,
        errors=tuple(errors),
        publication_date_year_inconsistent=inconsistent,
    )


def is_primary_corpus_work(work: dict[str, Any], study: dict[str, Any]) -> bool:
    """Return whether a work belongs to the fixed date/type/subfield frame."""
    return validate_corpus_work(work, study).valid
