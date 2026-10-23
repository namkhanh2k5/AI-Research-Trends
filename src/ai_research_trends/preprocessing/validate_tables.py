"""Critical relational, sampling, field, and on-disk integrity checks."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

from ai_research_trends.config import load_config
from ai_research_trends.crawling.openalex_client import canonical_work_id
from ai_research_trends.crawling.plan_stratified_sample import validate_sampling_plan
from ai_research_trends.preprocessing.normalize_population import normalize_population
from ai_research_trends.preprocessing.schemas import KEYS, SCHEMAS


class ProcessedValidationError(ValueError):
    """A critical processed-table invariant failed."""


def expected_collaboration_flag(unique_count: int, complete_coverage: bool) -> bool | None:
    if unique_count >= 2:
        return True
    if unique_count == 1 and complete_coverage:
        return False
    return None


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_rows(
    tables: dict[str, list[dict[str, Any]]],
    plan: dict[str, Any],
    population_rows: list[dict[str, Any]],
    config: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """Return named PASS/FAIL checks, failing once all safe checks have run."""
    results: dict[str, dict[str, Any]] = {}

    def check(name: str, condition: bool, detail: str) -> None:
        results[name] = {"status": "PASS" if condition else "FAIL", "detail": detail}

    works = tables["works"]
    ids = [row["work_id"] for row in works]
    work_ids = set(ids)
    expected = int(plan["allocated_sample_size"])
    check("work_count", len(works) == expected, f"actual={len(works)}, expected={expected}")
    check("work_id_unique", len(work_ids) == len(works), f"unique={len(work_ids)}")
    check(
        "work_id_canonical",
        all(canonical_work_id(value) == value for value in ids),
        "all Work IDs must be canonical",
    )
    check("no_retractions", all(row["is_retracted"] is False for row in works), "primary sample")
    study = config["study"]
    lower = date.fromisoformat(study["start_date"])
    upper = date.fromisoformat(study["end_date"])
    check(
        "corpus_date_type_subfield",
        all(
            lower <= row["publication_date"] <= upper
            and row["publication_date"].year == row["publication_year"]
            and row["work_type"] in study["work_types"]
            and row["primary_subfield_id"] in study["primary_subfield_ids"]
            for row in works
        ),
        "approved complete-year primary AI/CV frame",
    )
    year_counts = Counter(row["publication_year"] for row in works)
    expected_years = {row["publication_year"]: row["sample_size"] for row in plan["strata"]}
    check("year_allocation", dict(year_counts) == expected_years, str(dict(sorted(year_counts.items()))))
    weights = {row["publication_year"]: row["sampling_weight"] for row in plan["strata"]}
    check(
        "nominal_weights",
        all(
            row["sample_stratum"] == str(row["publication_year"])
            and math.isclose(row["sampling_weight"], weights[row["publication_year"]], rel_tol=1e-12)
            for row in works
        ),
        "weight and stratum come from the validated plan",
    )
    check(
        "citation_fwci_features",
        all(
            isinstance(row["cited_by_count"], int)
            and row["cited_by_count"] >= 0
            and math.isclose(row["log1p_citations"], math.log1p(row["cited_by_count"]))
            and row["zero_citation_flag"] == (row["cited_by_count"] == 0)
            and row["has_fwci"] == (row["fwci"] is not None)
            and (row["fwci"] is None or row["fwci"] >= 0)
            and row["publication_age_years"] >= 0
            for row in works
        ),
        "raw citation outliers and nullable FWCI preserved",
    )
    check(
        "oa_consistency",
        all(
            (row["is_oa"] is None and row["oa_status"] is None and not row["has_oa_metadata"])
            or (
                row["is_oa"] is not None
                and row["has_oa_metadata"]
                and row["is_oa"] == (row["oa_status"] != "closed")
            )
            for row in works
        ),
        "binary and categorical OA values agree; missing is not closed",
    )

    for name, columns in KEYS.items():
        rows = tables[name]
        keys = [tuple(row[column] for column in columns) for row in rows]
        check(f"{name}_key_unique", len(keys) == len(set(keys)), f"rows={len(rows)}")
        if name not in {"works", "population_year_counts", "references"}:
            check(
                f"{name}_work_fk",
                all(row["work_id"] in work_ids for row in rows),
                "all bridge Work IDs exist in works",
            )

    references = tables["references"]
    check(
        "references_fk_and_membership",
        all(
            row["citing_work_id"] in work_ids
            and row["referenced_in_sample"] == (row["referenced_work_id"] in work_ids)
            and canonical_work_id(row["referenced_work_id"]) == row["referenced_work_id"]
            for row in references
        ),
        "external referenced works are retained with in-sample flag false",
    )
    topic_ids = {(row["work_id"], row["topic_id"]) for row in tables["work_topics"]}
    check(
        "primary_topic_relationship",
        all(
            row["primary_topic_id"] is None
            or (row["work_id"], row["primary_topic_id"]) in topic_ids
            for row in works
        ),
        "primary topic must appear in the work-topic bridge",
    )
    by_work = Counter(row["work_id"] for row in tables["authorships"])
    by_inst = Counter(row["work_id"] for row in tables["work_institutions"])
    by_country = Counter(row["work_id"] for row in tables["work_countries"])
    check(
        "collaboration_counts",
        all(
            row["authorship_count"] == by_work[row["work_id"]]
            and row["unique_institution_count"] == by_inst[row["work_id"]]
            and row["unique_country_count"] == by_country[row["work_id"]]
            and row["has_institution_affiliation"] == (by_inst[row["work_id"]] > 0)
            and row["has_country_affiliation"] == (by_country[row["work_id"]] > 0)
            for row in works
        ),
        "work-level counts equal deduplicated bridges",
    )
    check(
        "unknown_collaboration_preserved",
        all(
            row["international_collaboration"]
            is expected_collaboration_flag(
                row["unique_country_count"], row["country_affiliation_complete"]
            )
            and row["institutional_collaboration"]
            is expected_collaboration_flag(
                row["unique_institution_count"], row["institution_affiliation_complete"]
            )
            for row in works
        ),
        "missing affiliations cannot produce a negative collaboration claim",
    )
    allowed_native = set(config["openalex_native_categories"])
    allowed_custom = set(config["custom_emerging_technologies"])
    check(
        "category_layers",
        all(
            (
                row["analytical_layer"] == "openalex_native"
                and row["category"] in allowed_native
            )
            or (
                row["analytical_layer"] == "custom_emerging"
                and row["category"] in allowed_custom
            )
            for row in tables["category_membership"]
        ),
        "native topic and custom text layers remain distinct",
    )
    check(
        "category_provenance",
        all(
            row["matched_rule_or_topic_ids"]
            and row["classification_version"]
            and (
                row["analytical_layer"] != "openalex_native"
                or all(
                    (row["work_id"], f"https://openalex.org/{topic_id}") in topic_ids
                    and topic_id in config["openalex_native_categories"][row["category"]]["topic_ids"]
                    for topic_id in row["matched_rule_or_topic_ids"]
                )
            )
            and (
                row["analytical_layer"] != "custom_emerging"
                or all(
                    rule_name
                    in {
                        rule["name"]
                        for rule in config["custom_emerging_technologies"][row["category"]]["rule_groups"]
                    }
                    for rule_name in row["matched_rule_or_topic_ids"]
                )
            )
            for row in tables["category_membership"]
        ),
        "each membership records matching IDs or rule names",
    )
    check(
        "population_aggregate_separation",
        tables["population_year_counts"] == population_rows
        and len(population_rows) == 6 * len({row["series"] for row in population_rows}),
        "population counts originate only from verified API aggregate artifact",
    )

    if any(item["status"] == "FAIL" for item in results.values()):
        failed = [name for name, item in results.items() if item["status"] == "FAIL"]
        raise ProcessedValidationError(f"Critical processed-table checks failed: {failed}")
    return results


def validate_output_directory(
    output_dir: Path,
    plan: dict[str, Any],
    population_rows: list[dict[str, Any]],
    config: dict[str, Any],
    *,
    require_manifest: bool = True,
) -> tuple[dict[str, dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    manifest = None
    if require_manifest:
        manifest = json.loads((output_dir / "manifest.json").read_text())
        if manifest.get("status") != "complete" or manifest.get("complete") is not True:
            raise ProcessedValidationError("Processed manifest is not complete")
    tables: dict[str, list[dict[str, Any]]] = {}
    for name, schema in SCHEMAS.items():
        path = output_dir / f"{name}.parquet"
        table = pq.read_table(path)
        if table.schema != schema:
            raise ProcessedValidationError(f"{name} has unexpected Arrow schema")
        if manifest is not None:
            entry = manifest["tables"][name]
            if (
                entry["sha256"] != file_sha256(path)
                or entry["rows"] != table.num_rows
                or entry["columns"] != table.num_columns
                or entry["bytes"] != path.stat().st_size
            ):
                raise ProcessedValidationError(f"{name} file inventory mismatch")
        tables[name] = table.to_pylist()
    checks = validate_rows(tables, plan, population_rows, config)
    if manifest is not None:
        if manifest.get("validation") != checks:
            raise ProcessedValidationError("Stored validation summary differs from recheck")
    return checks, tables


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read-only validation of Phase 3 Parquet tables")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--population", required=True)
    parser.add_argument("--config", default="config/topics.yaml")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    plan_path = Path(args.plan)
    plan = json.loads(plan_path.read_text())
    validate_sampling_plan(plan, population_source_bytes=Path(plan["population_counts_source"]).read_bytes())
    population = json.loads(Path(args.population).read_text())
    config = load_config(args.config)
    population_rows = normalize_population(population, config)
    manifest = json.loads((Path(args.output_dir) / "manifest.json").read_text())
    for label, source in manifest["inputs"].items():
        path = Path(source["path"])
        if source["sha256"] != file_sha256(path):
            raise ProcessedValidationError(f"{label} source checksum differs from processing manifest")
    if manifest["inputs"]["plan"]["sha256"] != file_sha256(plan_path):
        raise ProcessedValidationError("Supplied plan differs from processing input")
    if manifest["inputs"]["population"]["sha256"] != file_sha256(Path(args.population)):
        raise ProcessedValidationError("Supplied population artifact differs from processing input")
    if manifest["inputs"]["config"]["sha256"] != file_sha256(Path(args.config)):
        raise ProcessedValidationError("Supplied study configuration differs from processing input")
    if manifest["quality_json_sha256"] != file_sha256(Path(args.output_dir) / "quality.json"):
        raise ProcessedValidationError("Quality-audit checksum mismatch")
    checks, tables = validate_output_directory(Path(args.output_dir), plan, population_rows, config)
    print(json.dumps({"valid": True, "checks_passed": len(checks), "tables": {k: len(v) for k,v in tables.items()}}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
