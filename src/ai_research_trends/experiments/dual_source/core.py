"""Pure cohort, provider normalization and RQ7 integration rules.

The OpenAlex Work ID remains the unit of analysis. Crossref is never allowed to
change membership in the pre-existing AI/CV research frame.
"""

from __future__ import annotations

import hashlib
import html
import re
from collections import Counter
from datetime import date
from typing import Any
from urllib.parse import unquote

import pandas as pd

from ai_research_trends.crawling.openalex_client import canonical_work_id
from ai_research_trends.experiments.venue_core import valid_issns
from ai_research_trends.preprocessing.common import clean_text, normalize_doi
from ai_research_trends.preprocessing.text import reconstruct_abstract


def stable_order(seed: int, value: str) -> str:
    return hashlib.sha256(f"{seed}:{value}".encode()).hexdigest()


def proportional_allocation(sizes: dict[str, int], total: int) -> dict[str, int]:
    """Largest-remainder allocation with stable key tie-breaking."""
    population = sum(sizes.values())
    if population < total or total < 0:
        raise ValueError("Invalid sample allocation")
    exact = {k: total * n / population for k, n in sizes.items()}
    result = {k: int(v) for k, v in exact.items()}
    remainder = total - sum(result.values())
    for key in sorted(sizes, key=lambda k: (-(exact[k] - result[k]), k))[:remainder]:
        result[key] += 1
    return result


def select_cohort(works: pd.DataFrame, venue: pd.DataFrame, *, seed: int = 20261104,
                  general_n: int = 1200, targeted_n: int = 300) -> pd.DataFrame:
    """Disjoint A/B cohort; A mirrors year×type×DOI frame, B targets repairable gaps."""
    frame = works.loc[works.publication_year.between(2020, 2024)].copy()
    if frame.work_id.duplicated().any() or frame.is_retracted.fillna(False).any():
        raise ValueError("Original frame is not unique or non-retracted")
    if len(frame) < general_n + targeted_n:
        raise ValueError("Historical frame cannot support requested cohort")
    frame["doi_available"] = frame.doi.notna()
    frame["stratum"] = (frame.publication_year.astype(str) + ":" +
                        frame.work_type.astype(str) + ":" + frame.doi_available.astype(str))
    sizes = {str(k): len(p) for k, p in frame.groupby("stratum")}
    allocation = proportional_allocation(sizes, general_n)
    frame["order"] = frame.work_id.map(lambda v: stable_order(seed, v))
    general = pd.concat([p.sort_values(["order", "work_id"]).head(allocation[key])
                         for key, p in frame.groupby("stratum")], ignore_index=True)
    general["group"] = "A_GENERAL"
    residual = frame.loc[~frame.work_id.isin(general.work_id)].copy()
    venue = venue.loc[venue.dataset_origin.eq("original_analytical_sample")].drop_duplicates("work_id")
    residual = residual.merge(venue[["work_id", "publisher", "source_name", "issn_l", "source_id"]],
                              on="work_id", how="left", validate="one_to_one")
    residual["quality_gap_count"] = (residual.publisher.isna().astype(int) +
                                     residual.source_name.isna().astype(int) +
                                     residual.issn_l.isna().astype(int) +
                                     residual.source_id.isna().astype(int))
    targeted = residual.loc[residual.doi.notna() & residual.quality_gap_count.gt(0)].copy()
    targeted = targeted.sort_values(["quality_gap_count", "order", "work_id"],
                                    ascending=[False, True, True]).head(targeted_n)
    if len(targeted) != targeted_n:
        raise ValueError("Insufficient DOI-bearing quality-gap records for Group B")
    targeted["group"] = "B_TARGETED_MISSINGNESS"
    selected = pd.concat([general, targeted], ignore_index=True)
    if selected.work_id.duplicated().any() or len(selected) != general_n + targeted_n:
        raise AssertionError("Cohort overlap or size mismatch")
    return selected[["work_id", "publication_year", "work_type", "doi", "group", "stratum",
                     "quality_gap_count"] if "quality_gap_count" in selected else
                    ["work_id", "publication_year", "work_type", "doi", "group", "stratum"]].sort_values("work_id").reset_index(drop=True)


def safe_doi(value: Any) -> tuple[str | None, str]:
    if value is None or value == "":
        return None, "DOI_MISSING"
    try:
        return normalize_doi(unquote(value) if isinstance(value, str) else value), "VALID"
    except ValueError:
        return None, "DOI_INVALID"


def _date_parts(value: Any) -> str | None:
    parts = value.get("date-parts") if isinstance(value, dict) else None
    if not isinstance(parts, list) or not parts or not isinstance(parts[0], list):
        return None
    nums = parts[0]
    if not nums or not all(isinstance(x, int) for x in nums[:3]):
        return None
    try:
        return date(nums[0], nums[1] if len(nums) > 1 else 1,
                    nums[2] if len(nums) > 2 else 1).isoformat()
    except ValueError:
        return None


def plain_crossref_abstract(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = re.sub(r"<[^>]+>", " ", value)
    return clean_text(html.unescape(text))


def normalize_openalex(work: dict[str, Any]) -> dict[str, Any]:
    wid = canonical_work_id(work.get("id"))
    publication_date = work.get("publication_date")
    if publication_date is not None:
        if not isinstance(publication_date, str):
            raise ValueError("OpenAlex publication_date must be ISO text or null")
        try:
            parsed_date = date.fromisoformat(publication_date)
        except ValueError as exc:
            raise ValueError("OpenAlex publication_date is invalid") from exc
        if work.get("publication_year") is not None and parsed_date.year != work["publication_year"]:
            raise ValueError("OpenAlex publication year/date inconsistency")
    doi, doi_status = safe_doi(work.get("doi"))
    location = work.get("primary_location") or {}
    source = location.get("source") or {} if isinstance(location, dict) else {}
    if not isinstance(source, dict):
        source = {}
    issns, invalid_issns = valid_issns(source.get("issn"))
    if source.get("issn_l"):
        more, bad = valid_issns([source["issn_l"]])
        issns = sorted(set(issns + more))
        invalid_issns += bad
    try:
        abstract = reconstruct_abstract(work.get("abstract_inverted_index"))
        abstract_status = "AVAILABLE" if abstract else "MISSING"
    except ValueError:
        abstract, abstract_status = None, "MALFORMED"
    return {
        "work_id": wid, "doi": doi, "doi_status": doi_status,
        "title": clean_text(work.get("display_name") or work.get("title")),
        "abstract": abstract, "abstract_status": abstract_status,
        "publication_date": publication_date,
        "publication_year": work.get("publication_year"), "work_type": work.get("type"),
        "primary_topic_id": (work.get("primary_topic") or {}).get("id"),
        "primary_subfield_id": ((work.get("primary_topic") or {}).get("subfield") or {}).get("id"),
        "publisher": clean_text(source.get("host_organization_name")),
        "venue_name": clean_text(source.get("display_name")),
        "source_id": source.get("id"), "issns": issns,
        "invalid_issns": invalid_issns,
        "license": (location.get("license") if isinstance(location, dict) else None),
        "cited_by_count": work.get("cited_by_count"), "fwci": work.get("fwci"),
        "is_oa": (work.get("open_access") or {}).get("is_oa"),
        "oa_status": (work.get("open_access") or {}).get("oa_status"),
        "is_retracted": work.get("is_retracted"),
        "authorship_count": len(work.get("authorships") or []),
        "reference_count": len(work.get("referenced_works") or []),
    }


def normalize_crossref(payload: dict[str, Any], requested_doi: str) -> dict[str, Any]:
    message = payload.get("message")
    if not isinstance(message, dict):
        raise ValueError("Crossref message missing")
    doi, status = safe_doi(message.get("DOI"))
    if status != "VALID" or doi != normalize_doi(requested_doi):
        raise ValueError("Crossref DOI mismatch")
    issns, invalid = valid_issns(message.get("ISSN"))
    title = message.get("title") or []
    container = message.get("container-title") or []
    title = title[0] if isinstance(title, list) and title else None
    container = container[0] if isinstance(container, list) and container else None
    dates = {key: _date_parts(message.get(key)) for key in
             ("published", "published-online", "published-print", "issued")}
    updates = message.get("update-to") or []
    relations = message.get("relation") or {}
    update_kinds = {str(item.get("type", "")).casefold() for item in updates if isinstance(item, dict)} if isinstance(updates, list) else set()
    relation_text = str(relations).casefold()
    return {"doi": doi, "title": clean_text(title), "abstract": plain_crossref_abstract(message.get("abstract")),
            "venue_name": clean_text(container), "work_type": message.get("type"),
            "publisher": clean_text(message.get("publisher")), "issns": issns,
            "invalid_issns": invalid, "dates": dates,
            "publication_year": int(dates["published"][:4]) if dates["published"] else None,
            "license": message.get("license") or [], "funder": message.get("funder") or [],
            "authors": message.get("author") or [], "references": message.get("reference") or [],
            "retraction_evidence": any("retract" in x for x in update_kinds) or "retract" in relation_text,
            "update_kinds": sorted(update_kinds), "relations": relations}


INTEGRATED_FIELDS = ("publisher", "venue_name", "issns", "license")


def integrate_record(openalex: dict[str, Any], crossref: dict[str, Any] | None,
                     match_status: str) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    """Conservative field precedence; never overwrite OpenAlex frame/bibliometrics."""
    row = dict(openalex)
    row["match_status"] = match_status
    provenance = []
    conflicts = []
    for field in ("title", "abstract", "publication_date", "publication_year", "work_type",
                  "publisher", "venue_name", "issns", "license", "is_retracted"):
        oa_value = openalex.get(field)
        cr_value = None if crossref is None else (crossref["dates"].get("published") if field == "publication_date" else
                                                  (True if crossref.get("retraction_evidence") else None) if field == "is_retracted" else
                                                  crossref.get(field))
        present = lambda v: v is not None and v != "" and v != []
        source = "openalex" if present(oa_value) else "missing"
        if field in INTEGRATED_FIELDS and not present(oa_value) and present(cr_value):
            row[field] = cr_value
            source = "crossref"
        if present(oa_value) and present(cr_value) and oa_value != cr_value:
            # Provider differences are evidence, not automatic errors.
            conflicts.append({"work_id": row["work_id"], "field": field,
                              "openalex_value": str(oa_value)[:500], "crossref_value": str(cr_value)[:500],
                              "resolution": "preserve_openalex",
                              "difference_kind": ("provider_type_taxonomy" if field == "work_type" else
                                                  "date_definition_or_drift" if field in ("publication_year", "publication_date") else
                                                  "provider_license_schema" if field == "license" else
                                                  "lexical_difference" if field == "title" else "value_difference")})
        provenance.append({"work_id": row["work_id"], "field": field, "selected_source": source,
                           "openalex_available": present(oa_value), "crossref_available": present(cr_value)})
    row["crossref_retraction_evidence"] = crossref.get("retraction_evidence") if crossref else None
    row["quality_warnings"] = [x for x in ("invalid_doi" if row["doi_status"] == "DOI_INVALID" else None,
                                                    "malformed_abstract" if row["abstract_status"] == "MALFORMED" else None,
                                                    "crossref_retraction_evidence" if row["crossref_retraction_evidence"] else None) if x]
    return row, provenance, conflicts


QUALITY_FIELDS = ("doi", "abstract", "publisher", "venue_name", "issns",
                  "publication_date", "license")


def quality_counts(records: list[dict[str, Any]]) -> dict[str, int]:
    return {field: sum(bool(r.get(field)) for r in records) for field in QUALITY_FIELDS} | {
        "records": len(records),
        "valid_doi": sum(r.get("doi_status") == "VALID" for r in records),
        "invalid_doi": sum(r.get("doi_status") == "DOI_INVALID" for r in records),
        "duplicate_work_ids": len(records) - len({r["work_id"] for r in records}),
        "duplicate_dois": sum(n - 1 for n in Counter(r.get("doi") for r in records if r.get("doi")).values() if n > 1),
    }
