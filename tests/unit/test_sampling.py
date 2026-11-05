import copy
import hashlib
import json

import pytest

from ai_research_trends.crawling.plan_stratified_sample import (
    APPROVED_PRIMARY_FILTER,
    build_sampling_plan,
    validate_sampling_plan,
)
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
                "query_parameters": {
                    "filter": APPROVED_PRIMARY_FILTER,
                    "group_by": "publication_year",
                },
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


def _complete_plan() -> tuple[dict, bytes]:
    source_bytes = json.dumps(_population_payload(), separators=(",", ":")).encode()
    plan = build_sampling_plan(json.loads(source_bytes), 12)
    plan["population_counts_source"] = "data/metadata/test_population.json"
    plan["population_counts_sha256"] = hashlib.sha256(source_bytes).hexdigest()
    return plan, source_bytes


def test_sampling_plan_recomputes_allocation_and_validates_source() -> None:
    plan, source_bytes = _complete_plan()
    assert validate_sampling_plan(plan, population_source_bytes=source_bytes) == plan["strata"]


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("population_total", 22, "population_total"),
        ("target_sample_size", 11, "Allocated sample size"),
        ("allocated_sample_size", 11, "target_sample_size"),
        ("population_query_name", "study_population_all", "unapproved"),
    ],
)
def test_sampling_plan_rejects_tampered_top_level_fields(
    field: str, value, message: str
) -> None:
    plan, _ = _complete_plan()
    plan[field] = value
    with pytest.raises(ValueError, match=message):
        validate_sampling_plan(plan)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("population_size", 999),
        ("sample_size", 2),
        ("inclusion_probability", 0.99),
        ("sampling_weight", 0.99),
        ("remainder_numerator", 999),
    ],
)
def test_sampling_plan_rejects_tampered_stratum_fields(field: str, value) -> None:
    plan, _ = _complete_plan()
    plan["strata"][0][field] = value
    with pytest.raises(ValueError, match=field):
        validate_sampling_plan(plan)


def test_sampling_plan_rejects_tampered_filter_and_source_checksum() -> None:
    plan, source_bytes = _complete_plan()
    altered = copy.deepcopy(plan)
    altered["population_query_parameters"]["filter"] = "is_retracted:true"
    with pytest.raises(ValueError, match="approved primary"):
        validate_sampling_plan(altered)

    altered = copy.deepcopy(plan)
    altered["population_counts_sha256"] = "f" * 64
    with pytest.raises(ValueError, match="checksum"):
        validate_sampling_plan(altered, population_source_bytes=source_bytes)
