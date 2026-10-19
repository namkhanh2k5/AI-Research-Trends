"""Create (but do not execute) the 12,000-work proportional sampling plan."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any

from ai_research_trends.config import FIXED_CORPUS, build_primary_analysis_filter
from ai_research_trends.crawling.openalex_client import utc_now
from ai_research_trends.crawling.sampling import allocate_largest_remainder


PRIMARY_POPULATION_QUERY = "study_population_primary_non_retracted"
EXPECTED_YEARS = tuple(range(2020, 2026))
SAMPLING_DESIGN = "proportional_publication_year_stratified_largest_remainder"
APPROVED_PRIMARY_FILTER = build_primary_analysis_filter(FIXED_CORPUS)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Allocate a proportional year-stratified sample from a complete, validated "
            "OpenAlex population-count file. This command performs no API collection."
        )
    )
    parser.add_argument(
        "--population-counts",
        default="data/metadata/population_counts.json",
        help="Complete output from openalex-collect-aggregates",
    )
    parser.add_argument("--sample-size", type=int, default=12000)
    parser.add_argument(
        "--output",
        default="data/metadata/phase2_sampling_plan.json",
        help="Sampling plan output path",
    )
    return parser


def build_sampling_plan(payload: dict[str, Any], target_size: int) -> dict[str, Any]:
    """Validate the population artifact and produce auditable stratum allocations."""
    if payload.get("complete") is not True:
        raise ValueError("Population counts must be explicitly marked complete")
    queries = payload.get("queries")
    if not isinstance(queries, list):
        raise ValueError("Population counts are missing the queries list")
    matches = [row for row in queries if row.get("name") == PRIMARY_POPULATION_QUERY]
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one {PRIMARY_POPULATION_QUERY!r} query")
    query = matches[0]
    if query.get("estimand_role") != "primary" or query.get("retraction_scope") != (
        "primary_non_retracted"
    ):
        raise ValueError("Sampling population is not the primary non-retracted estimand")
    expected_parameters = {
        "filter": APPROVED_PRIMARY_FILTER,
        "group_by": "publication_year",
    }
    if query.get("query_parameters") != expected_parameters:
        raise ValueError("Population query does not match the approved primary corpus filter")

    raw_counts = query.get("counts_by_year")
    if not isinstance(raw_counts, dict) or set(raw_counts) != {
        str(year) for year in EXPECTED_YEARS
    }:
        raise ValueError("Sampling population must contain exactly the six study years")
    population = {int(year): count for year, count in raw_counts.items()}
    if query.get("meta_count") != sum(population.values()):
        raise ValueError("Population stratum counts do not sum to query meta_count")

    allocations = allocate_largest_remainder(population, target_size)
    return {
        "schema_version": 1,
        "created_at_utc": utc_now(),
        "design": SAMPLING_DESIGN,
        "population_query_name": PRIMARY_POPULATION_QUERY,
        "population_query_parameters": expected_parameters,
        "population_total": sum(population.values()),
        "target_sample_size": target_size,
        "allocated_sample_size": sum(row.sample_size for row in allocations),
        "probability_note": (
            "Inclusion probabilities and weights are nominal n_h/N_h values. They require "
            "the unverified assumption that OpenAlex sample+seed is uniform within each "
            "stratum; deterministic repeatability alone does not establish that property."
        ),
        "strata": [row.as_dict() for row in allocations],
    }


def validate_sampling_plan(
    plan: dict[str, Any], *, population_source_bytes: bytes | None = None
) -> list[dict[str, Any]]:
    """Recompute and validate allocation, weights, provenance, and optional source bytes."""
    if plan.get("schema_version") != 1 or plan.get("design") != SAMPLING_DESIGN:
        raise ValueError("Unsupported sampling-plan schema or design")
    if plan.get("population_query_name") != PRIMARY_POPULATION_QUERY:
        raise ValueError("Sampling plan names an unapproved population query")
    expected_parameters = {
        "filter": APPROVED_PRIMARY_FILTER,
        "group_by": "publication_year",
    }
    if plan.get("population_query_parameters") != expected_parameters:
        raise ValueError("Sampling plan does not declare the approved primary corpus filter")

    source = plan.get("population_counts_source")
    source_sha = plan.get("population_counts_sha256")
    if not isinstance(source, str) or not source.strip():
        raise ValueError("Sampling plan must declare its population-count source")
    if not isinstance(source_sha, str) or not re.fullmatch(r"[0-9a-f]{64}", source_sha):
        raise ValueError("Sampling plan has an invalid population source SHA-256")

    target_size = plan.get("target_sample_size")
    allocated_size = plan.get("allocated_sample_size")
    population_total = plan.get("population_total")
    if not isinstance(target_size, int) or isinstance(target_size, bool) or target_size <= 0:
        raise ValueError("Sampling plan target_sample_size must be a positive integer")
    if allocated_size != target_size:
        raise ValueError("Allocated sample size must equal target_sample_size")

    strata = plan.get("strata")
    if not isinstance(strata, list) or len(strata) != len(EXPECTED_YEARS):
        raise ValueError("Sampling plan must contain six publication-year strata")
    if not all(isinstance(row, dict) for row in strata):
        raise ValueError("Every sampling stratum must be an object")
    years = [row.get("publication_year") for row in strata]
    if years != list(EXPECTED_YEARS):
        raise ValueError("Sampling strata must be unique and ordered from 2020 through 2025")

    population: dict[int, int] = {}
    for row in strata:
        year = row["publication_year"]
        size = row.get("population_size")
        if not isinstance(size, int) or isinstance(size, bool) or size <= 0:
            raise ValueError(f"Population size for {year} must be a positive integer")
        population[year] = size
    if population_total != sum(population.values()):
        raise ValueError(
            "Sampling plan population_total does not equal stratum population_size values"
        )

    expected = allocate_largest_remainder(population, target_size)
    expected_by_year = {row.publication_year: row for row in expected}
    for actual in strata:
        year = actual["publication_year"]
        wanted = expected_by_year[year]
        for field in ("population_size", "sample_size", "remainder_numerator"):
            if actual.get(field) != getattr(wanted, field):
                raise ValueError(f"Sampling plan has inconsistent {field} for year {year}")
        sample_size = actual["sample_size"]
        if not 1 <= sample_size <= 10_000:
            raise ValueError(f"Sample size for year {year} is outside OpenAlex limits")
        for field in ("inclusion_probability", "sampling_weight"):
            value = actual.get(field)
            if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
                raise ValueError(f"Sampling plan has invalid {field} for year {year}")
            if not math.isclose(value, getattr(wanted, field), rel_tol=1e-12, abs_tol=1e-15):
                raise ValueError(f"Sampling plan has inconsistent {field} for year {year}")
    if sum(row["sample_size"] for row in strata) != allocated_size:
        raise ValueError("Stratum sample sizes do not match allocated_sample_size")

    if population_source_bytes is not None:
        digest = hashlib.sha256(population_source_bytes).hexdigest()
        if digest != source_sha:
            raise ValueError("Population-count source checksum does not match the plan")
        try:
            source_payload = json.loads(population_source_bytes)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ValueError("Population-count source is not valid JSON") from exc
        rebuilt = build_sampling_plan(source_payload, target_size)
        for field in (
            "population_query_name",
            "population_query_parameters",
            "population_total",
            "target_sample_size",
            "allocated_sample_size",
            "strata",
        ):
            if plan.get(field) != rebuilt.get(field):
                raise ValueError(f"Sampling plan does not match its source field {field!r}")
    return strata


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    source = Path(args.population_counts)
    source_bytes = source.read_bytes()
    payload = json.loads(source_bytes)
    plan = build_sampling_plan(payload, args.sample_size)
    plan["population_counts_source"] = str(source)
    plan["population_counts_sha256"] = hashlib.sha256(source_bytes).hexdigest()
    validate_sampling_plan(plan, population_source_bytes=source_bytes)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"sample_size": plan["allocated_sample_size"], "output": str(output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
