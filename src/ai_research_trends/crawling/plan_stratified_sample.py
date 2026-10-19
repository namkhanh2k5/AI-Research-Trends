"""Create (but do not execute) the 12,000-work proportional sampling plan."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from ai_research_trends.crawling.openalex_client import utc_now
from ai_research_trends.crawling.sampling import allocate_largest_remainder


PRIMARY_POPULATION_QUERY = "study_population_primary_non_retracted"
EXPECTED_YEARS = tuple(range(2020, 2026))


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
        "design": "proportional_publication_year_stratified_largest_remainder",
        "population_query_name": PRIMARY_POPULATION_QUERY,
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


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    source = Path(args.population_counts)
    source_bytes = source.read_bytes()
    payload = json.loads(source_bytes)
    plan = build_sampling_plan(payload, args.sample_size)
    plan["population_counts_source"] = str(source)
    plan["population_counts_sha256"] = hashlib.sha256(source_bytes).hexdigest()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"sample_size": plan["allocated_sample_size"], "output": str(output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
