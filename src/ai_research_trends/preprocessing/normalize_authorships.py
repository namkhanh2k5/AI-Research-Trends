"""Deduplicated work-level affiliation bridges with explicit coverage states."""

from __future__ import annotations

from typing import Any

from ai_research_trends.preprocessing.common import clean_text, country_code, entity_id


def normalize_authorships(
    source: dict[str, Any], work_id: str
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, Any],
    list[dict[str, Any]],
]:
    """Return authorships, unique institutions/countries, features, and issues."""
    source_authorships = source.get("authorships")
    if source_authorships is None:
        source_authorships = []
    if not isinstance(source_authorships, list):
        raise ValueError(f"{work_id} authorships must be a list or null")
    corresponding_ids_raw = source.get("corresponding_institution_ids") or []
    if not isinstance(corresponding_ids_raw, list):
        raise ValueError(f"{work_id} corresponding_institution_ids must be a list")
    corresponding_ids = {
        entity_id(value, "I", nullable=False) for value in corresponding_ids_raw
    }

    authorships: list[dict[str, Any]] = []
    institutions: dict[str, dict[str, Any]] = {}
    countries: dict[str, set[str]] = {}
    identified_authors: set[str] = set()
    issues: list[dict[str, Any]] = []
    institution_coverage: list[bool] = []
    country_coverage: list[bool] = []

    for index, entry in enumerate(source_authorships, start=1):
        if not isinstance(entry, dict):
            raise ValueError(f"{work_id} authorship {index} is not an object")
        author = entry.get("author") or {}
        if not isinstance(author, dict):
            raise ValueError(f"{work_id} authorship {index} has malformed author")
        author_id = entity_id(author.get("id"), "A")
        if author_id is not None:
            identified_authors.add(author_id)
        is_corresponding = entry.get("is_corresponding")
        if is_corresponding is not None and not isinstance(is_corresponding, bool):
            raise ValueError(f"{work_id} authorship {index} has invalid is_corresponding")
        position = clean_text(entry.get("author_position"))
        if position is not None and position not in {"first", "middle", "last"}:
            raise ValueError(f"{work_id} authorship {index} has unknown author_position")
        authorships.append(
            {
                "work_id": work_id,
                "author_id": author_id,
                "author_name": clean_text(author.get("display_name"))
                or clean_text(entry.get("raw_author_name")),
                "author_position": position,
                "is_corresponding": is_corresponding,
                "authorship_index": index,
            }
        )

        raw_institutions = entry.get("institutions") or []
        raw_countries = entry.get("countries") or []
        if not isinstance(raw_institutions, list) or not isinstance(raw_countries, list):
            raise ValueError(f"{work_id} authorship {index} has malformed affiliations")
        author_has_institution = False
        author_has_country = False
        for raw_country in raw_countries:
            code = country_code(raw_country)
            countries.setdefault(code, set()).add("authorship_countries")
            author_has_country = True
        for institution in raw_institutions:
            if not isinstance(institution, dict):
                raise ValueError(f"{work_id} authorship {index} has malformed institution")
            institution_id = entity_id(institution.get("id"), "I")
            institution_country = institution.get("country_code")
            code = country_code(institution_country) if institution_country else None
            if code is not None:
                countries.setdefault(code, set()).add("institution_country_code")
                author_has_country = True
            if institution_id is None:
                issues.append(
                    {
                        "work_id": work_id,
                        "field": "institution_id",
                        "reason": f"missing ID in authorship {index}",
                    }
                )
                continue
            author_has_institution = True
            existing = institutions.get(institution_id)
            if existing is None:
                institutions[institution_id] = {
                    "work_id": work_id,
                    "institution_id": institution_id,
                    "institution_name": clean_text(institution.get("display_name")),
                    "institution_type": clean_text(institution.get("type")),
                    "country_code": code,
                    "is_corresponding_institution": bool(is_corresponding)
                    or institution_id in corresponding_ids,
                }
            else:
                if existing["country_code"] and code and existing["country_code"] != code:
                    raise ValueError(f"{work_id} has conflicting countries for {institution_id}")
                for field, candidate in (
                    ("institution_name", clean_text(institution.get("display_name"))),
                    ("institution_type", clean_text(institution.get("type"))),
                    ("country_code", code),
                ):
                    if existing[field] is None:
                        existing[field] = candidate
                existing["is_corresponding_institution"] |= (
                    bool(is_corresponding) or institution_id in corresponding_ids
                )
        institution_coverage.append(author_has_institution)
        country_coverage.append(author_has_country)

    n_authorships = len(authorships)
    n_institutions = len(institutions)
    n_countries = len(countries)
    full_institution_coverage = n_authorships > 0 and all(institution_coverage)
    full_country_coverage = n_authorships > 0 and all(country_coverage)
    features = {
        "authorship_count": n_authorships,
        "identified_author_count": len(identified_authors),
        "unique_institution_count": n_institutions,
        "unique_country_count": n_countries,
        "has_institution_affiliation": n_institutions > 0,
        "has_country_affiliation": n_countries > 0,
        "institution_affiliation_complete": full_institution_coverage,
        "country_affiliation_complete": full_country_coverage,
        "institutional_collaboration": (
            True if n_institutions >= 2 else False if n_institutions == 1 and full_institution_coverage else None
        ),
        "international_collaboration": (
            True if n_countries >= 2 else False if n_countries == 1 and full_country_coverage else None
        ),
    }
    country_rows = [
        {
            "work_id": work_id,
            "country_code": code,
            "country_provenance": "|".join(sorted(provenance)),
        }
        for code, provenance in sorted(countries.items())
    ]
    return authorships, list(institutions.values()), country_rows, features, issues
