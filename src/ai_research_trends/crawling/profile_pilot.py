"""Generate a reproducible feasibility profile from a collected pilot JSONL."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable, Iterable

from ai_research_trends.config import load_config, primary_subfield_id, validate_corpus_work
from ai_research_trends.crawling.openalex_client import canonical_work_id, utc_now
from ai_research_trends.preprocessing.categories import all_category_keys, classify_work


MISSINGNESS_FIELDS = ("abstract", "fwci", "institution", "country")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Profile pilot missingness and category coverage without changing records."
    )
    parser.add_argument("jsonl", help="Pilot works JSONL created by openalex-collect-pilot")
    parser.add_argument("--config", default="config/topics.yaml", help="Study YAML path")
    parser.add_argument(
        "--output", default="data/metadata/pilot_profile.json", help="Profile JSON path"
    )
    return parser


def _missing(value: Any) -> bool:
    return value is None or value == [] or value == {}


def missing_affiliation_metadata(work: dict[str, Any]) -> tuple[bool, bool]:
    """Return missing usable institution and country flags from nested authorships."""
    authorships = work.get("authorships") or []
    has_institution = any(
        isinstance(institution, dict) and bool(institution.get("id"))
        for authorship in authorships
        if isinstance(authorship, dict)
        for institution in (authorship.get("institutions") or [])
    )
    has_country = any(
        isinstance(country, str) and bool(country.strip())
        for authorship in authorships
        if isinstance(authorship, dict)
        for country in (authorship.get("countries") or [])
    )
    return not has_institution, not has_country


def is_retracted(work: dict[str, Any]) -> bool:
    """Treat only the explicit boolean true value as a retraction."""
    return work.get("is_retracted") is True


def include_in_primary_analysis(work: dict[str, Any]) -> bool:
    """Phase 1 policy: retain retractions in storage, exclude from primary estimates."""
    return not is_retracted(work)


def _quality_flags(work: dict[str, Any]) -> dict[str, bool]:
    missing_institution, missing_country = missing_affiliation_metadata(work)
    return {
        "abstract": _missing(work.get("abstract_inverted_index")),
        "fwci": _missing(work.get("fwci")),
        "institution": missing_institution,
        "country": missing_country,
    }


def _summarize_subset(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    rows = list(rows)
    denominator = len(rows)
    missing_counts = Counter()
    for row in rows:
        missing_counts.update(name for name, value in _quality_flags(row).items() if value)
    return {
        "records": denominator,
        "missing": {
            name: {
                "count": missing_counts[name],
                "rate": (missing_counts[name] / denominator) if denominator else None,
            }
            for name in MISSINGNESS_FIELDS
        },
        "retracted_count": sum(is_retracted(row) for row in rows),
    }


def _grouped_profile(
    rows: list[dict[str, Any]], key: Callable[[dict[str, Any]], Any]
) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        value = key(row)
        groups["missing" if value is None or value == "" else str(value)].append(row)
    return {name: _summarize_subset(group) for name, group in sorted(groups.items())}


def _quantile(values: list[int], probability: float) -> float | None:
    """Return a linearly interpolated quantile without a numerical dependency."""
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def profile(jsonl_path: Path, config: dict[str, Any]) -> dict[str, Any]:
    raw_bytes = jsonl_path.read_bytes()
    rows = [json.loads(line) for line in raw_bytes.splitlines() if line.strip()]
    canonical_ids = [canonical_work_id(row.get("id", "")) for row in rows]

    fields = (
        "doi",
        "title",
        "abstract_inverted_index",
        "primary_topic",
        "topics",
        "fwci",
        "cited_by_count",
        "language",
        "open_access",
        "authorships",
    )
    missing = {field: sum(_missing(row.get(field)) for row in rows) for field in fields}
    affiliation_flags = [missing_affiliation_metadata(row) for row in rows]
    citation_counts = [
        int(row["cited_by_count"])
        for row in rows
        if isinstance(row.get("cited_by_count"), (int, float))
    ]
    languages = Counter(row.get("language") for row in rows if row.get("language"))

    matches_by_work = [classify_work(row, config) for row in rows]
    native_counts: Counter[str] = Counter()
    custom_counts: Counter[str] = Counter()
    membership_counts = {
        "openalex_native": Counter(),
        "custom_emerging": Counter(),
    }
    category_rows: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row, matches in zip(rows, matches_by_work, strict=True):
        native_counts.update(matches.openalex_native)
        custom_counts.update(matches.custom_emerging)
        membership_counts["openalex_native"][len(matches.openalex_native)] += 1
        membership_counts["custom_emerging"][len(matches.custom_emerging)] += 1
        for category_key in all_category_keys(matches):
            category_rows[category_key].append(row)

    study = config["study"]
    corpus_validation = [validate_corpus_work(row, study) for row in rows]
    corpus_membership = [result.valid for result in corpus_validation]
    retracted_count = sum(is_retracted(row) for row in rows)

    return {
        "schema_version": 2,
        "profiled_at_utc": utc_now(),
        "source_jsonl": str(jsonl_path),
        "source_sha256": hashlib.sha256(raw_bytes).hexdigest(),
        "records": len(rows),
        "unique_canonical_work_ids": len(set(canonical_ids)),
        "duplicate_canonical_work_ids": len(canonical_ids) - len(set(canonical_ids)),
        "primary_corpus_membership": {
            "matching_records": sum(corpus_membership),
            "violating_records": len(rows) - sum(corpus_membership),
            "definition": (
                "publication dates 2020-01-01 through 2025-12-31 inclusive; matching "
                "publication_year; types article/review/preprint; primary subfield 1702/1707"
            ),
            "violation_count_by_reason": dict(
                Counter(
                    error
                    for validation in corpus_validation
                    for error in validation.errors
                )
            ),
            "publication_date_year_inconsistent_count": sum(
                validation.publication_date_year_inconsistent
                for validation in corpus_validation
            ),
        },
        "publication_year": dict(
            sorted(Counter(row.get("publication_year") for row in rows).items(), key=str)
        ),
        "work_type": dict(Counter(row.get("type") for row in rows)),
        "language_available_count": len(rows) - missing["language"],
        "language_missing_count": missing["language"],
        "language_count": dict(languages.most_common()),
        "citation_distribution": {
            "available_count": len(citation_counts),
            "missing_count": missing["cited_by_count"],
            "zero_count": sum(value == 0 for value in citation_counts),
            "minimum": min(citation_counts) if citation_counts else None,
            "median": statistics.median(citation_counts) if citation_counts else None,
            "mean": statistics.fmean(citation_counts) if citation_counts else None,
            "p90_linear": _quantile(citation_counts, 0.90),
            "maximum": max(citation_counts) if citation_counts else None,
        },
        "primary_subfield": dict(Counter(primary_subfield_id(row) or "missing" for row in rows)),
        "missing_count": missing,
        "missing_authorship_institution_count": sum(value[0] for value in affiliation_flags),
        "missing_authorship_country_count": sum(value[1] for value in affiliation_flags),
        "missingness_by_publication_year": _grouped_profile(
            rows, lambda row: row.get("publication_year")
        ),
        "missingness_by_work_type": _grouped_profile(rows, lambda row: row.get("type")),
        "missingness_by_research_category": {
            f"{layer}:{slug}": _summarize_subset(category_subset)
            for (layer, slug), category_subset in sorted(category_rows.items())
        },
        "oa_status": dict(
            Counter((row.get("open_access") or {}).get("oa_status") for row in rows)
        ),
        "retractions": {
            "retracted_count": retracted_count,
            "not_retracted_count": len(rows) - retracted_count,
            "primary_analysis_included_count": sum(
                include_in_primary_analysis(row) for row in rows
            ),
            "policy": study["retraction_policy"],
        },
        "category_match_count": {
            "openalex_native": dict(native_counts),
            "custom_emerging": dict(custom_counts),
        },
        "research_category_memberships_per_work": {
            layer: dict(sorted(counter.items()))
            for layer, counter in membership_counts.items()
        },
        "notes": [
            "Native-topic and custom-text counts are separate, non-equivalent layers.",
            "Counts overlap within each layer and must not be summed.",
            "Custom text-rule counts are feasibility diagnostics, not classifier truth.",
            "Missing institution/country means no usable value in nested authorships.",
            "Retractions remain stored and flagged but are excluded from primary estimates.",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = profile(Path(args.jsonl), load_config(args.config))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"records": result["records"], "output": str(output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
