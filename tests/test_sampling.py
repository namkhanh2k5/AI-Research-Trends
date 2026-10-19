import pytest

from ai_research_trends.crawling.plan_stratified_sample import build_sampling_plan
from ai_research_trends.crawling.sampling import allocate_largest_remainder


def test_largest_remainder_allocation_and_weights() -> None:
    allocations = allocate_largest_remainder({2020: 10, 2021: 20, 2022: 30}, 10)
    by_year = {row.publication_year: row for row in allocations}
    assert [row.sample_size for row in allocations] == [2, 3, 5]
    assert sum(row.sample_size for row in allocations) == 10
    assert by_year[2020].inclusion_probability == pytest.approx(0.2)
    assert by_year[2020].sampling_weight == pytest.approx(5.0)
    assert by_year[2021].sampling_weight == pytest.approx(20 / 3)


def test_largest_remainder_rejects_zero_sized_sample_strata() -> None:
    with pytest.raises(ValueError, match="zero observations"):
        allocate_largest_remainder({2021: 1, 2020: 1}, 1)


def _population_payload() -> dict:
    counts = {str(year): year - 2019 for year in range(2020, 2026)}
    return {
        "complete": True,
        "queries": [
            {
                "name": "study_population_primary_non_retracted",
                "estimand_role": "primary",
                "retraction_scope": "primary_non_retracted",
                "meta_count": sum(counts.values()),
                "counts_by_year": counts,
            }
        ],
    }


def test_sampling_plan_uses_only_validated_primary_population() -> None:
    plan = build_sampling_plan(_population_payload(), 12)
    assert plan["allocated_sample_size"] == 12
    assert plan["population_total"] == 21
    assert len(plan["strata"]) == 6
    assert "nominal" in plan["probability_note"]


def test_sampling_plan_rejects_incomplete_population_artifact() -> None:
    payload = _population_payload()
    payload["complete"] = False
    with pytest.raises(ValueError, match="complete"):
        build_sampling_plan(payload, 12)
