"""Pure, conservative rules for the RQ7.1 metadata-quality audit.

Provider metadata and automated syntax checks are evidence, not human adjudication.
"""

from __future__ import annotations

import ast
import hashlib
import json
import math
import re
import unicodedata
from collections import Counter
from typing import Any
from urllib.parse import urlparse

import pandas as pd


STRATA = ("S1_PUBLISHER", "S2_LICENSE", "S3_CONFLICT", "S4_CROSSREF_404")
REVIEW_STATUS = "PENDING_HUMAN_REVIEW"
CONFLICT_CLASSES = ("TAXONOMY_DIFFERENCE", "DATE_DEFINITION_DIFFERENCE",
                    "NORMALIZATION_DIFFERENCE", "SEMANTIC_METADATA_CONFLICT",
                    "SCHEMA_INCOMPATIBILITY", "UNRESOLVED")


def stable_key(seed: int, value: str) -> str:
    return hashlib.sha256(f"{seed}:{value}".encode()).hexdigest()


def select_review_sample(canonical: pd.DataFrame, conflicts: pd.DataFrame, *,
                         seed: int = 20261104, targets: tuple[int, int, int, int] = (30, 30, 20, 20)) -> pd.DataFrame:
    """Draw mutually exclusive diagnostic strata, retaining secondary issue flags."""
    if len(canonical) != canonical.work_id.nunique() or len(targets) != 4 or any(n < 0 for n in targets):
        raise ValueError("Invalid canonical frame or targets")
    frame = canonical.copy()
    conflicting = set(conflicts.work_id)
    frame["publisher_recovered"] = frame.publisher_source.eq("crossref")
    frame["license_recovered"] = frame.license_source.eq("crossref")
    frame["has_provider_conflict"] = frame.work_id.isin(conflicting)
    frame["crossref_404"] = frame.match_status.eq("CROSSREF_NOT_FOUND")
    masks = ("publisher_recovered", "license_recovered", "has_provider_conflict", "crossref_404")
    selected: list[dict[str, Any]] = []
    taken: set[str] = set()
    for label, flag, target in zip(STRATA, masks, targets):
        eligible = frame.loc[frame[flag] & ~frame.work_id.isin(taken)].copy()
        # Domain-separate from the original cohort's 20261104 ordering. Reusing
        # its hash would preferentially draw Group A, which was selected first.
        eligible["sampling_order_key"] = eligible.work_id.map(lambda x: stable_key(seed, "rq7_1_review:" + str(x)))
        eligible = eligible.sort_values(["sampling_order_key", "work_id"])
        if len(eligible) < target:
            raise ValueError(f"Insufficient disjoint records for {label}: {len(eligible)} < {target}")
        for row in eligible.head(target).to_dict("records"):
            taken.add(row["work_id"])
            selected.append({"work_id": row["work_id"], "doi": row["doi"],
                             "title": row["title"], "publication_year": int(row["publication_year"]),
                             "work_type": row["work_type"], "cohort_group": row["group"],
                             "primary_review_stratum": label,
                             "sampling_order_key": row["sampling_order_key"],
                             **{name: bool(row[name]) for name in masks},
                             "review_status": REVIEW_STATUS})
    sample = pd.DataFrame(selected)
    if len(sample) != sum(targets) or sample.work_id.duplicated().any():
        raise AssertionError("Review strata overlap")
    return sample.sort_values(["primary_review_stratum", "sampling_order_key", "work_id"]).reset_index(drop=True)


def normalized_publisher(value: Any) -> str | None:
    """Lexical normalization only; it does not prove publisher identity."""
    if not isinstance(value, str) or not value.strip():
        return None
    value = unicodedata.normalize("NFKC", value).casefold()
    return " ".join(re.findall(r"[\w]+", value))


def parse_license_records(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (ValueError, TypeError):
            return []
    return [x for x in value if isinstance(x, dict)] if isinstance(value, list) else []


def license_url_info(url: Any) -> dict[str, Any]:
    parsed = urlparse(url) if isinstance(url, str) else urlparse("")
    valid = parsed.scheme in ("http", "https") and bool(parsed.hostname) and not parsed.username
    identifier = None
    if valid and parsed.hostname in ("creativecommons.org", "www.creativecommons.org"):
        match = re.fullmatch(r"/licenses/(by(?:-nc)?(?:-nd|-sa)?|zero)/(\d+(?:\.\d+)?)/?", parsed.path)
        if match:
            identifier = f"CC-{match.group(1).upper()}-{match.group(2)}"
    return {"url_syntax_valid": bool(valid), "license_identifier": identifier}


def license_evidence(value: Any) -> dict[str, Any]:
    records = parse_license_records(value)
    parsed = [license_url_info(x.get("URL")) for x in records]
    versions = sorted({str(x.get("content-version")) for x in records if x.get("content-version")})
    dates = [x.get("start", {}).get("date-time") for x in records if isinstance(x.get("start"), dict)]
    return {"license_metadata_present": bool(records),
            "license_urls": [x.get("URL") for x in records],
            "syntactically_valid_urls": sum(x["url_syntax_valid"] for x in parsed),
            "license_identifiers": sorted({x["license_identifier"] for x in parsed if x["license_identifier"]}),
            "content_versions": versions, "start_dates": [x for x in dates if x],
            "content_version_restriction": bool(versions and set(versions) != {"unspecified"}),
            "license_url_verified": False, "license_semantics_verified": False,
            "reuse_rights_status": "UNKNOWN", "license_conflict_status": "UNREVIEWED"}


def _listlike(value: Any) -> list[str] | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = ast.literal_eval(value)
    except (SyntaxError, ValueError):
        return None
    return [str(x) for x in parsed] if isinstance(parsed, list) else None


def classify_conflict(row: dict[str, Any]) -> dict[str, str | bool]:
    """Exactly one primary class; semantic conflicts are potential, not proven errors."""
    field, left, right = row["field"], row["openalex_value"], row["crossref_value"]
    norm = lambda x: " ".join(unicodedata.normalize("NFKC", str(x)).casefold().split())
    if field == "work_type":
        cls, rule, confidence = "TAXONOMY_DIFFERENCE", "different_provider_type_vocabularies", "HIGH"
    elif field in ("publication_date", "publication_year"):
        cls, rule, confidence = "DATE_DEFINITION_DIFFERENCE", "published_vs_online_print_or_snapshot_unknown", "MEDIUM"
    elif field == "license":
        cls, rule, confidence = "SCHEMA_INCOMPATIBILITY", "string_vs_versioned_license_array", "HIGH"
    elif field == "issns" and _listlike(left) is not None and _listlike(right) is not None and set(_listlike(left)) & set(_listlike(right)):
        cls, rule, confidence = "SCHEMA_INCOMPATIBILITY", "overlapping_issn_sets_with_different_coverage", "HIGH"
    elif norm(left) == norm(right) or (field == "issns" and _listlike(left) is not None and
                                      _listlike(right) is not None and set(_listlike(left)) == set(_listlike(right))):
        cls, rule, confidence = "NORMALIZATION_DIFFERENCE", "lexical_or_list_equivalence", "HIGH"
    elif field == "publisher" and normalized_publisher(left) == normalized_publisher(right):
        cls, rule, confidence = "NORMALIZATION_DIFFERENCE", "publisher_lexical_equivalence", "HIGH"
    elif field in ("publisher", "venue_name", "issns"):
        cls, rule, confidence = "SEMANTIC_METADATA_CONFLICT", "different_values_require_authoritative_review", "LOW"
    else:
        cls, rule, confidence = "UNRESOLVED", "insufficient_evidence_for_semantic_comparison", "LOW"
    return {"classification": cls, "classification_rule": rule,
            "confidence_category": confidence,
            "manual_review_required": cls in ("SEMANTIC_METADATA_CONFLICT", "UNRESOLVED", "DATE_DEFINITION_DIFFERENCE")}


def classify_404(doi: str | None, status_code: int, agency: str | None) -> str:
    if status_code != 404:
        raise ValueError("Only stored Crossref HTTP 404 cases may be classified")
    if doi is None or not re.match(r"^https://doi\.org/10\.\d{4,9}/\S+$", doi, re.I):
        return "DOI_IDENTITY_PROBLEM"
    if agency is None:
        return "UNKNOWN_REASON"
    if agency.casefold() == "crossref":
        return "CROSSREF_REGISTERED_NOT_FOUND"
    if agency.casefold() in ("unknown", "invalid doi", "doi does not exist"):
        return "UNKNOWN_REASON"
    return "NON_CROSSREF_REGISTRATION"


def wilson_interval(correct: int, denominator: int, z: float = 1.959963984540054) -> tuple[float, float] | None:
    if denominator == 0:
        return None
    if not 0 <= correct <= denominator:
        raise ValueError("Invalid correctness denominator")
    p = correct / denominator
    center = (p + z*z/(2*denominator)) / (1+z*z/denominator)
    spread = z*math.sqrt(p*(1-p)/denominator + z*z/(4*denominator*denominator))/(1+z*z/denominator)
    return center-spread, center+spread


def reviewed_correctness(statuses: list[str]) -> dict[str, Any]:
    counts = Counter(statuses)
    allowed = {REVIEW_STATUS, "VERIFIED_CORRECT", "VERIFIED_INCORRECT", "ACCEPTABLE_ALIAS",
               "AMBIGUOUS", "INSUFFICIENT_EVIDENCE", "NOT_REVIEWED"}
    if set(counts) - allowed:
        raise ValueError("Unknown review decision")
    verified = counts["VERIFIED_CORRECT"] + counts["VERIFIED_INCORRECT"] + counts["ACCEPTABLE_ALIAS"]
    correct = counts["VERIFIED_CORRECT"] + counts["ACCEPTABLE_ALIAS"]
    return {"selected": len(statuses), "reviewed": len(statuses)-counts[REVIEW_STATUS]-counts["NOT_REVIEWED"],
            "authoritatively_verifiable": verified, "correct_or_acceptable_alias": correct,
            "verified_incorrect": counts["VERIFIED_INCORRECT"],
            "verification_yield": verified / len(statuses) if statuses else None,
            "correctness_among_verifiable": correct / verified if verified else None,
            "wilson_95": wilson_interval(correct, verified), "status_counts": dict(counts)}
