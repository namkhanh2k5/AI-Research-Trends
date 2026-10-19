"""Pure allocation logic for the proportional year-stratified Phase 2 design."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Mapping


@dataclass(frozen=True)
class StratumAllocation:
    publication_year: int
    population_size: int
    sample_size: int
    inclusion_probability: float
    sampling_weight: float
    remainder_numerator: int

    def as_dict(self) -> dict:
        return asdict(self)


def allocate_largest_remainder(
    population_by_year: Mapping[int, int], target_size: int
) -> list[StratumAllocation]:
    """Allocate a proportional sample with Hamilton's largest-remainder method."""
    if not isinstance(target_size, int) or isinstance(target_size, bool) or target_size <= 0:
        raise ValueError("target_size must be a positive integer")
    if not population_by_year:
        raise ValueError("At least one population stratum is required")

    normalized: dict[int, int] = {}
    for year, size in population_by_year.items():
        if not isinstance(year, int) or isinstance(year, bool):
            raise ValueError("Publication-year keys must be integers")
        if not isinstance(size, int) or isinstance(size, bool) or size <= 0:
            raise ValueError(f"Population size for {year} must be a positive integer")
        normalized[year] = size

    population_total = sum(normalized.values())
    if target_size > population_total:
        raise ValueError("target_size cannot exceed the stratum population total")

    base = {
        year: (target_size * size) // population_total
        for year, size in normalized.items()
    }
    remainders = {
        year: (target_size * size) % population_total
        for year, size in normalized.items()
    }
    seats_left = target_size - sum(base.values())
    ranked = sorted(normalized, key=lambda year: (-remainders[year], year))
    for year in ranked[:seats_left]:
        base[year] += 1

    allocations: list[StratumAllocation] = []
    for year in sorted(normalized):
        population_size = normalized[year]
        sample_size = base[year]
        if sample_size <= 0:
            raise ValueError(
                f"Target size gives zero observations to year {year}; increase target_size"
            )
        allocations.append(
            StratumAllocation(
                publication_year=year,
                population_size=population_size,
                sample_size=sample_size,
                inclusion_probability=sample_size / population_size,
                sampling_weight=population_size / sample_size,
                remainder_numerator=remainders[year],
            )
        )
    return allocations
