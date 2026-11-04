"""Pure venue-identity and provider parsing rules; never infer identity from names alone."""

from __future__ import annotations

import re
from typing import Any

from ai_research_trends.experiments.common import normalize_issn, valid_issns
from ai_research_trends.preprocessing.common import normalize_doi


SOURCE_ID = re.compile(r"^(?:https://openalex\.org/)?(S\d+)$", re.I)
VENUE_TYPES = {"journal", "conference", "book series", "repository", "ebook platform"}
RANKABLE_TYPES = {"journal", "conference"}


def source_id(value: Any) -> str | None:
    if value is None or value == "":
        return None
    if not isinstance(value, str) or not (match := SOURCE_ID.fullmatch(value.strip())):
        raise ValueError(f"Invalid OpenAlex Source ID: {value!r}")
    return "https://openalex.org/" + match.group(1).upper()


def normalize_source_type(value: Any) -> str:
    if not isinstance(value, str):
        return "unknown"
    normalized = value.strip().casefold().replace("_", " ").replace("-", " ")
    if normalized in {"conference", "conference series"}:
        return "conference"
    if normalized in {"book series", "bookseries"}:
        return "book series"
    if normalized in {"ebook platform", "ebook"}:
        return "ebook platform"
    return normalized if normalized in VENUE_TYPES else "unknown"


def _source(location: Any) -> dict[str, Any] | None:
    if not isinstance(location, dict):
        return None
    candidate = location.get("source")
    return candidate if isinstance(candidate, dict) else None


def extract_openalex_venue(work: dict[str, Any]) -> dict[str, Any]:
    """Use a published journal/conference location, never repository hosting as venue."""
    primary = work.get("primary_location") or {}
    locations = work.get("locations") or []
    if not isinstance(locations, list):
        raise ValueError("Malformed OpenAlex locations")
    sources: dict[str, dict[str, Any]] = {}
    published: set[str] = set()
    repositories: set[str] = set()
    warnings: list[str] = []
    for location in [primary, *locations]:
        src = _source(location)
        if not src:
            continue
        try:
            sid = source_id(src.get("id"))
        except ValueError:
            warnings.append("invalid_source_id")
            continue
        if not sid:
            warnings.append("missing_source_id")
            continue
        sources[sid] = src
        kind = normalize_source_type(src.get("type"))
        if kind == "repository":
            repositories.add(sid)
        if isinstance(location, dict) and (
            location.get("is_published") is True or location.get("version") == "publishedVersion"
        ) and kind in RANKABLE_TYPES:
            published.add(sid)
    primary_src = _source(primary)
    primary_id = source_id(primary_src.get("id")) if primary_src and primary_src.get("id") else None
    primary_kind = normalize_source_type(primary_src.get("type")) if primary_src else "unknown"
    candidates = sorted(published)
    method = "published_location"
    if not candidates and primary_id and primary_kind in RANKABLE_TYPES:
        candidates = [primary_id]
        method = "primary_source_unverified_version"
        warnings.append("publication_version_not_explicit")
    if len(candidates) != 1:
        chosen = None
        status = "AMBIGUOUS" if len(candidates) > 1 else "UNMATCHED"
        if len(candidates) > 1:
            warnings.append("multiple_published_sources")
    else:
        chosen = candidates[0]
        status = "EXACT_IDENTIFIER_MATCH"
    src = sources.get(chosen, {}) if chosen else {}
    issns, bad_issns = valid_issns(src.get("issn"))
    issn_l = None
    try:
        issn_l = normalize_issn(src.get("issn_l"))
    except ValueError:
        bad_issns.append(str(src.get("issn_l")))
    if bad_issns:
        warnings.append("invalid_issn")
    try:
        doi = normalize_doi(work.get("doi"))
    except ValueError:
        doi = None
        warnings.append("invalid_doi")
    return {
        "work_id": work["id"], "doi": doi,
        "publication_year": work.get("publication_year"),
        "publication_date": work.get("publication_date"),
        "work_type": work.get("type"),
        "primary_topic_id": (work.get("primary_topic") or {}).get("id"),
        "is_retracted": work.get("is_retracted"),
        "primary_source_id": primary_id,
        "primary_source_type": primary_kind,
        "source_id": chosen,
        "source_name": src.get("display_name"),
        "source_type": normalize_source_type(src.get("type")),
        "publisher": src.get("host_organization_name"),
        "issn_l": issn_l,
        "issns": issns,
        "all_source_ids": sorted(sources),
        "source_count": len(sources),
        "has_repository_host": bool(repositories),
        "has_primary_source": primary_id is not None,
        "match_status": status,
        "match_method": method if chosen else None,
        "warnings": sorted(set(warnings)),
    }


def parse_crossref(payload: dict[str, Any], requested_doi: str) -> dict[str, Any]:
    message = payload.get("message")
    if not isinstance(message, dict):
        raise ValueError("Crossref response lacks message object")
    doi = normalize_doi(message.get("DOI"))
    if doi != normalize_doi(requested_doi):
        raise ValueError("Crossref DOI does not match requested DOI")
    issns, invalid = valid_issns(message.get("ISSN"))
    published = message.get("published") or message.get("published-print") or message.get("published-online") or {}
    parts = published.get("date-parts") if isinstance(published, dict) else None
    year = parts[0][0] if isinstance(parts, list) and parts and isinstance(parts[0], list) and parts[0] else None
    title = message.get("title") or []
    container = message.get("container-title") or []
    updates = message.get("update-to") or []
    if not isinstance(updates, list):
        updates = []
    update_types = sorted({str(item.get("type", "")).casefold() for item in updates if isinstance(item, dict)})
    return {
        "doi": doi, "title": title[0] if title else None,
        "container_title": container[0] if container else None,
        "crossref_type": message.get("type"), "publisher": message.get("publisher"),
        "issns": issns, "invalid_issns": invalid,
        "published_year": year, "event": message.get("event"),
        "update_types": update_types, "relations": message.get("relation"),
        "crossref_retraction_evidence": any("retract" in kind for kind in update_types),
        "crossref_update_evidence_present": bool(update_types),
    }


def resolve_venue(local: dict[str, Any], crossref: dict[str, Any] | None = None) -> dict[str, Any]:
    """Keep provider values separate; assign only identifier-backed venue identities."""
    sid = local.get("source_id")
    local_issns = set(local.get("issns") or [])
    if local.get("issn_l"):
        local_issns.add(local["issn_l"])
    cross_issns = set((crossref or {}).get("issns") or [])
    conflict = bool(local_issns and cross_issns and not local_issns.intersection(cross_issns))
    if local.get("match_status") == "AMBIGUOUS":
        status, venue_id = "AMBIGUOUS", None
    elif sid:
        status = "CONFLICT" if conflict else "EXACT_IDENTIFIER_MATCH"
        venue_id = sid if not conflict else None
    elif len(cross_issns) == 1 and crossref and crossref.get("container_title"):
        # An ISSN is a real identifier; the Crossref name alone is not.
        venue_id = "issn:" + next(iter(cross_issns))
        status = "EXACT_IDENTIFIER_MATCH"
    else:
        venue_id, status = None, "UNMATCHED"
    local_type = local.get("source_type") or "unknown"
    cross_type = (crossref or {}).get("crossref_type")
    type_conflict = (
        (local_type == "journal" and cross_type == "proceedings-article")
        or (local_type == "conference" and cross_type == "journal-article")
    )
    if type_conflict:
        status, venue_id = "CONFLICT", None
    return {
        "work_id": local["work_id"], "doi": local.get("doi"),
        "canonical_venue_id": venue_id,
        "display_name": local.get("source_name") or (crossref or {}).get("container_title"),
        "venue_type": local_type if sid else (
            "journal" if cross_type == "journal-article" and venue_id else "unknown"
        ),
        "openalex_source_id": sid,
        "issns": sorted(local_issns | cross_issns),
        "issn_l": local.get("issn_l"),
        "openalex_publisher": local.get("publisher"),
        "crossref_publisher": (crossref or {}).get("publisher"),
        "openalex_name": local.get("source_name"),
        "crossref_name": (crossref or {}).get("container_title"),
        "crossref_type": cross_type,
        "identity_status": status,
        "ambiguity_flag": status in {"AMBIGUOUS", "CONFLICT"},
        "issn_conflict": conflict,
        "type_conflict": bool(type_conflict),
        "publication_year_conflict": bool(crossref and crossref.get("published_year") and
            local.get("publication_year") and crossref["published_year"] != local["publication_year"]),
        "provider_provenance": ["openalex"] + (["crossref"] if crossref else []),
        "dataset_origin": local.get("dataset_origin"),
        "publication_year": local.get("publication_year"),
        "work_type": local.get("work_type"),
        "primary_topic_id": local.get("primary_topic_id"),
    }


def retraction_comparison(openalex_is_retracted: bool | None,
                          crossref: dict[str, Any] | None) -> dict[str, Any]:
    evidence = None if crossref is None else bool(crossref["crossref_retraction_evidence"])
    # No Crossref update is absence of evidence, not explicit evidence of no retraction.
    return {"openalex_is_retracted": openalex_is_retracted,
            "crossref_retraction_evidence": evidence,
            "crossref_update_type": (crossref or {}).get("update_types", []),
            "status_conflict": False,
            "status_unknown": crossref is None or not evidence,
            "decision_policy": "retain_separate_evidence_manual_review"}
