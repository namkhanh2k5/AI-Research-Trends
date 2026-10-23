"""Strict, loss-aware scalar normalization shared by Phase 3 tables."""

from __future__ import annotations

import math
import re
from datetime import date, datetime, timezone
from typing import Any

from ai_research_trends.crawling.openalex_client import canonical_openalex_id


DOI_PATTERN = re.compile(r"^10\.\d{4,9}/\S+$", re.IGNORECASE)
DOI_PREFIX = re.compile(r"^(?:https?://(?:dx\.)?doi\.org/|doi:)", re.IGNORECASE)


def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"Expected text or null, got {type(value).__name__}")
    cleaned = " ".join(value.split())
    return cleaned or None


def normalize_doi(value: Any) -> str | None:
    text = clean_text(value)
    if text is None:
        return None
    suffix = DOI_PREFIX.sub("", text).strip()
    if not DOI_PATTERN.fullmatch(suffix):
        raise ValueError(f"Malformed DOI: {text!r}")
    return f"https://doi.org/{suffix.lower()}"


def entity_id(value: Any, prefix: str, *, nullable: bool = True) -> str | None:
    if value is None or value == "":
        if nullable:
            return None
        raise ValueError(f"Missing OpenAlex {prefix} ID")
    canonical = canonical_openalex_id(value)
    if canonical.rsplit("/", 1)[-1][0] != prefix:
        raise ValueError(f"Expected OpenAlex {prefix} ID: {value!r}")
    return canonical


def taxonomy_id(value: Any, kind: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"Invalid {kind} ID: {value!r}")
    if value.startswith("https://openalex.org/"):
        parts = value.rstrip("/").split("/")
        if len(parts) < 2 or parts[-2] != kind:
            raise ValueError(f"Invalid {kind} ID: {value!r}")
        value = parts[-1]
    if not value.isdigit():
        raise ValueError(f"Invalid {kind} ID: {value!r}")
    return value


def country_code(value: Any) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z]{2}", value.strip()):
        raise ValueError(f"Invalid affiliation country code: {value!r}")
    return value.strip().upper()


def nonnegative_int(value: Any, label: str, *, nullable: bool = False) -> int | None:
    if value is None and nullable:
        return None
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{label} must be a nonnegative integer")
    return value


def nonnegative_float(value: Any, label: str) -> float | None:
    if value is None:
        return None
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"{label} must be a nonnegative finite number or null")
    result = float(value)
    if not math.isfinite(result) or result < 0:
        raise ValueError(f"{label} must be a nonnegative finite number or null")
    return result


def parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Retrieval timestamp must carry a UTC offset")
    return parsed.astimezone(timezone.utc)


def publication_age_years(publication_date: date, observation_time: datetime) -> float:
    days = (observation_time.date() - publication_date).days
    if days < 0:
        raise ValueError("Publication date is after the observation date")
    return days / 365.2425
