"""Work-grain normalization; all source records remain in immutable JSONL."""

from __future__ import annotations

import math
from datetime import date, datetime
from typing import Any

from ai_research_trends.config import validate_corpus_work
from ai_research_trends.crawling.openalex_client import canonical_work_id
from ai_research_trends.preprocessing.common import (
    clean_text,
    entity_id,
    nonnegative_float,
    nonnegative_int,
    normalize_doi,
    publication_age_years,
    taxonomy_id,
)
from ai_research_trends.preprocessing.text import reconstruct_abstract


OA_STATUSES = {"closed", "bronze", "green", "gold", "hybrid", "diamond"}


def normalize_work(
    source: dict[str, Any],
    *,
    study: dict[str, Any],
    observation_time: datetime,
    run_id: str,
    sampling_weight: float,
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    """Normalize one work and return nonfatal text quarantine evidence."""
    work_id = canonical_work_id(source.get("id", ""))
    validation = validate_corpus_work(source, study, require_non_retracted=True)
    if not validation.valid:
        raise ValueError(f"{work_id} violates the approved corpus: {validation.errors}")
    publication_date = date.fromisoformat(source["publication_date"])
    if not isinstance(sampling_weight, (int, float)) or not math.isfinite(sampling_weight):
        raise ValueError("Sampling weight is invalid")
    if sampling_weight <= 0:
        raise ValueError("Sampling weight must be positive")

    title = clean_text(source.get("title"))
    quarantine: list[dict[str, str]] = []
    try:
        abstract = clean_text(reconstruct_abstract(source.get("abstract_inverted_index")))
    except (TypeError, ValueError) as exc:
        abstract = None
        quarantine.append(
            {"work_id": work_id, "field": "abstract_inverted_index", "reason": str(exc)}
        )

    citations = nonnegative_int(source.get("cited_by_count"), "cited_by_count")
    fwci = nonnegative_float(source.get("fwci"), "fwci")
    oa = source.get("open_access")
    if oa is None:
        is_oa = None
        oa_status = None
    elif isinstance(oa, dict):
        is_oa = oa.get("is_oa")
        oa_status = oa.get("oa_status")
        if not isinstance(is_oa, bool) or oa_status not in OA_STATUSES:
            raise ValueError(f"{work_id} has malformed OA metadata")
        if is_oa != (oa_status != "closed"):
            raise ValueError(f"{work_id} has inconsistent OA status and is_oa")
    else:
        raise ValueError(f"{work_id} has malformed OA metadata")

    topic = source.get("primary_topic") or {}
    if not isinstance(topic, dict):
        raise ValueError(f"{work_id} has malformed primary_topic")
    references = source.get("referenced_works")
    if references is None:
        reference_status = "missing"
    elif not isinstance(references, list):
        raise ValueError(f"{work_id} has malformed referenced_works")
    else:
        reference_status = "empty" if not references else "present"
    source_ref_count = nonnegative_int(
        source.get("referenced_works_count"), "referenced_works_count", nullable=True
    )

    result = {
        "work_id": work_id,
        "doi": normalize_doi(source.get("doi")),
        "title": title,
        "abstract": abstract,
        "publication_date": publication_date,
        "publication_year": source["publication_year"],
        "work_type": source["type"],
        "language": clean_text(source.get("language")),
        "cited_by_count": citations,
        "fwci": fwci,
        "is_retracted": False,
        "is_oa": is_oa,
        "oa_status": oa_status,
        "primary_topic_id": entity_id(topic.get("id"), "T"),
        "primary_subfield_id": taxonomy_id((topic.get("subfield") or {}).get("id"), "subfields"),
        "primary_field_id": taxonomy_id((topic.get("field") or {}).get("id"), "fields"),
        "primary_domain_id": taxonomy_id((topic.get("domain") or {}).get("id"), "domains"),
        "sample_stratum": str(source["publication_year"]),
        "sampling_weight": float(sampling_weight),
        "collection_run_id": run_id,
        "retrieved_at_utc": observation_time,
        "publication_age_years": publication_age_years(publication_date, observation_time),
        "log1p_citations": math.log1p(citations),
        "zero_citation_flag": citations == 0,
        "has_fwci": fwci is not None,
        "has_oa_metadata": is_oa is not None,
        "has_abstract": abstract is not None,
        "title_length": len(title) if title is not None else None,
        "abstract_word_count": len(abstract.split()) if abstract is not None else None,
        "has_usable_text": title is not None or abstract is not None,
        "reference_list_status": reference_status,
        "referenced_works_count_reported": source_ref_count,
    }
    return result, quarantine
