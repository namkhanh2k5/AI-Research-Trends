"""Verified, deterministic Phase 3 JSONL-to-Parquet processing pipeline."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from ai_research_trends.config import load_config
from ai_research_trends.crawling.collect_stratified import _canonical_hash
from ai_research_trends.crawling.openalex_client import canonical_work_id, utc_now
from ai_research_trends.crawling.plan_stratified_sample import validate_sampling_plan
from ai_research_trends.crawling.verify_collection import verify_completed_collection
from ai_research_trends.features.bibliometric import add_category_features
from ai_research_trends.preprocessing.common import parse_utc
from ai_research_trends.preprocessing.normalize_authorships import normalize_authorships
from ai_research_trends.preprocessing.normalize_categories import normalize_categories
from ai_research_trends.preprocessing.normalize_population import normalize_population
from ai_research_trends.preprocessing.normalize_references import normalize_references
from ai_research_trends.preprocessing.normalize_topics import normalize_topics
from ai_research_trends.preprocessing.normalize_works import normalize_work
from ai_research_trends.preprocessing.schemas import KEYS, SCHEMAS
from ai_research_trends.preprocessing.validate_tables import (
    file_sha256,
    validate_output_directory,
    validate_rows,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build eight verified Phase 3 Parquet tables")
    parser.add_argument("--source-jsonl", required=True)
    parser.add_argument("--source-manifest", required=True)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--population", required=True)
    parser.add_argument("--phase2-profile", required=True)
    parser.add_argument("--config", default="config/topics.yaml")
    parser.add_argument("--output-dir", required=True, help="New, previously nonexistent directory")
    return parser


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _source_code_sha256() -> str:
    root = Path(__file__).resolve().parents[1]
    paths = sorted((root / "preprocessing").glob("*.py"))
    paths.extend(sorted((root / "features").glob("*.py")))
    digest = hashlib.sha256()
    for path in paths:
        digest.update(str(path.relative_to(root)).encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _git_head() -> str | None:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False
    )
    return result.stdout.strip() if result.returncode == 0 else None


def validate_inputs(
    *,
    source_jsonl: Path,
    source_manifest: Path,
    plan_path: Path,
    population_path: Path,
    profile_path: Path,
    config_path: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    """Verify Phase 2 evidence and all source-to-plan links before processing."""
    verified = verify_completed_collection(source_manifest)
    manifest = json.loads(source_manifest.read_text())
    if source_jsonl.resolve() != Path(manifest["interim_jsonl"]).resolve():
        raise ValueError("Source JSONL is not the verified interim output of this manifest")
    if file_sha256(source_jsonl) != manifest["interim_jsonl_sha256"]:
        raise ValueError("Source JSONL checksum differs from the collection manifest")
    plan_bytes = plan_path.read_bytes()
    plan = json.loads(plan_bytes)
    population_bytes = population_path.read_bytes()
    if Path(plan["population_counts_source"]).resolve() != population_path.resolve():
        raise ValueError("Sampling plan names a different population artifact")
    validate_sampling_plan(plan, population_source_bytes=population_bytes)
    if manifest["plan_sha256"] != _sha256_bytes(plan_bytes):
        raise ValueError("Collection manifest does not match the supplied sampling plan")
    config = load_config(config_path)
    if manifest["config_sha256"] != _canonical_hash(config):
        raise ValueError("Collection manifest does not match the supplied study configuration")
    if manifest["requested_records"] != plan["allocated_sample_size"]:
        raise ValueError("Collection size and sampling-plan allocation differ")
    population = json.loads(population_bytes)
    population_rows = normalize_population(population, config)
    profile = json.loads(profile_path.read_text())
    if profile.get("source_sha256") != manifest["raw_jsonl_sha256"]:
        raise ValueError("Phase 2 quality profile does not match the verified raw JSONL")
    if profile.get("records") != verified["verified_unique_work_ids"]:
        raise ValueError("Phase 2 quality profile record count is inconsistent")
    return manifest, plan, config, profile, population_rows


def _quality_summary(
    works: list[dict[str, Any]], issues: list[dict[str, Any]], profile: dict[str, Any]
) -> dict[str, Any]:
    fields = {
        "title": lambda row: row["title"] is None,
        "doi": lambda row: row["doi"] is None,
        "abstract": lambda row: row["abstract"] is None,
        "fwci": lambda row: row["fwci"] is None,
        "institution": lambda row: not row["has_institution_affiliation"],
        "country": lambda row: not row["has_country_affiliation"],
        "language": lambda row: row["language"] is None,
        "open_access": lambda row: not row["has_oa_metadata"],
    }
    overall = {name: sum(flag(row) for row in works) for name, flag in fields.items()}
    grouped: dict[str, dict[str, Any]] = {}
    for group_name, selector in (
        ("publication_year", lambda row: str(row["publication_year"])),
        ("work_type", lambda row: row["work_type"]),
    ):
        groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in works:
            groups[selector(row)].append(row)
        grouped[group_name] = {
            key: {
                "records": len(group),
                "missing": {name: sum(flag(row) for row in group) for name, flag in fields.items()},
            }
            for key, group in sorted(groups.items())
        }
    phase2_counts = {
        "title": profile["missing_count"]["title"],
        "doi": profile["missing_count"]["doi"],
        "abstract": profile["missing_count"]["abstract_inverted_index"],
        "fwci": profile["missing_count"]["fwci"],
        "institution": profile["missing_authorship_institution_count"],
        "country": profile["missing_authorship_country_count"],
        "language": profile["missing_count"]["language"],
        "open_access": profile["missing_count"]["open_access"],
    }
    return {
        "records": len(works),
        "missing": overall,
        "phase2_missing": phase2_counts,
        "missing_difference_vs_phase2": {
            name: overall[name] - phase2_counts[name] for name in fields
        },
        "by": grouped,
        "issues": issues,
        "issue_counts": dict(Counter(item["field"] for item in issues)),
        "unknown_international_collaboration": sum(
            row["international_collaboration"] is None for row in works
        ),
        "unknown_institutional_collaboration": sum(
            row["institutional_collaboration"] is None for row in works
        ),
        "reference_list_status": dict(Counter(row["reference_list_status"] for row in works)),
    }


def process_collection(
    *,
    source_jsonl: Path,
    source_manifest: Path,
    plan_path: Path,
    population_path: Path,
    profile_path: Path,
    config_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    """Validate, normalize, stage and atomically publish a complete new run."""
    if output_dir.exists():
        raise FileExistsError(f"Refusing to overwrite existing processed output: {output_dir}")
    manifest, plan, config, profile, population_rows = validate_inputs(
        source_jsonl=source_jsonl,
        source_manifest=source_manifest,
        plan_path=plan_path,
        population_path=population_path,
        profile_path=profile_path,
        config_path=config_path,
    )
    observation_time = parse_utc(manifest["completed_at_utc"])
    sample_ids = {
        work_id
        for stratum in manifest["strata"]
        for page in stratum["pages"]
        for work_id in page["work_ids"]
    }
    if len(sample_ids) != manifest["requested_records"]:
        raise ValueError("Manifest sample ID inventory has duplicates or missing IDs")
    weights = {int(row["publication_year"]): row["sampling_weight"] for row in plan["strata"]}
    config_sha = file_sha256(config_path)
    tables: dict[str, list[dict[str, Any]]] = {name: [] for name in SCHEMAS}
    tables["population_year_counts"] = population_rows
    issues: list[dict[str, Any]] = []
    seen: set[str] = set()

    with source_jsonl.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            try:
                source = json.loads(line)
                if not isinstance(source, dict):
                    raise ValueError("JSONL row is not an object")
                work_id = canonical_work_id(source.get("id", ""))
                if work_id not in sample_ids or work_id in seen:
                    raise ValueError(f"Unexpected or duplicate Work ID {work_id}")
                seen.add(work_id)
                year = source.get("publication_year")
                if year not in weights:
                    raise ValueError(f"Unknown publication-year stratum {year!r}")
                work, text_issues = normalize_work(
                    source,
                    study=config["study"],
                    observation_time=observation_time,
                    run_id=manifest["run_id"],
                    sampling_weight=weights[year],
                )
                authors, institutions, countries, collaboration, affiliation_issues = (
                    normalize_authorships(source, work_id)
                )
                work.update(collaboration)
                memberships, quarantine_reason = normalize_categories(
                    source, work_id, config, config_sha
                )
                add_category_features(work, memberships)
                if quarantine_reason and not text_issues:
                    text_issues.append(
                        {"work_id": work_id, "field": "abstract_inverted_index", "reason": quarantine_reason}
                    )
                refs, reference_issues = normalize_references(source, work_id, sample_ids)
                if work["referenced_works_count_reported"] is not None and source.get("referenced_works") is not None:
                    if work["referenced_works_count_reported"] != len(source["referenced_works"]):
                        reference_issues.append(
                            {"work_id": work_id, "field": "referenced_works_count", "reason": "source count differs from list length"}
                        )
                issues.extend(text_issues + affiliation_issues + reference_issues)
                tables["works"].append(work)
                tables["work_topics"].extend(normalize_topics(source, work_id))
                tables["authorships"].extend(authors)
                tables["work_institutions"].extend(institutions)
                tables["work_countries"].extend(countries)
                tables["references"].extend(refs)
                tables["category_membership"].extend(memberships)
            except Exception as exc:
                raise ValueError(f"Source JSONL line {line_number}: {exc}") from exc

    if seen != sample_ids:
        raise ValueError(f"Processed {len(seen)} IDs but manifest contains {len(sample_ids)}")
    for name, rows in tables.items():
        keys = KEYS[name]
        rows.sort(key=lambda row: tuple(row[key] for key in keys))
    checks = validate_rows(tables, plan, population_rows, config)
    quality = _quality_summary(tables["works"], issues, profile)
    # Directly comparable source fields should remain missing in exactly the same works.
    for field in ("title", "doi", "abstract", "fwci", "institution", "language", "open_access"):
        if quality["missing_difference_vs_phase2"][field] != 0:
            raise ValueError(f"Processed {field} missingness differs from the Phase 2 profile")

    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".phase3_staging_", dir=output_dir.parent) as temporary:
        stage = Path(temporary)
        inventory: dict[str, dict[str, Any]] = {}
        for name, rows in tables.items():
            table = pa.Table.from_pylist(rows, schema=SCHEMAS[name])
            path = stage / f"{name}.parquet"
            pq.write_table(table, path, compression="zstd", version="2.6")
            inventory[name] = {
                "rows": table.num_rows,
                "columns": table.num_columns,
                "unique_keys": len({tuple(row[key] for key in KEYS[name]) for row in rows}),
                "bytes": path.stat().st_size,
                "sha256": file_sha256(path),
                "grain_key": list(KEYS[name]),
            }
        validation_again, _ = validate_output_directory(
            stage, plan, population_rows, config, require_manifest=False
        )
        if validation_again != checks:
            raise ValueError("Parquet round-trip changed the validation results")
        (stage / "quality.json").write_text(json.dumps(quality, indent=2) + "\n")
        input_paths = {
            "source_jsonl": source_jsonl,
            "source_manifest": source_manifest,
            "plan": plan_path,
            "population": population_path,
            "phase2_profile": profile_path,
            "config": config_path,
        }
        result = {
            "schema_version": 1,
            "pipeline_version": "phase3-v1",
            "processed_at_utc": utc_now(),
            "status": "complete",
            "complete": True,
            "source_run_id": manifest["run_id"],
            "observation_time_utc": manifest["completed_at_utc"],
            "source_code_sha256": _source_code_sha256(),
            "git_head_at_processing": _git_head(),
            "sampling_weight_interpretation": "nominal N_h/n_h; uniform OpenAlex inclusion is unverified",
            "inputs": {
                name: {"path": str(path.resolve()), "sha256": file_sha256(path)}
                for name, path in input_paths.items()
            },
            "tables": inventory,
            "validation": checks,
            "quality_json_sha256": file_sha256(stage / "quality.json"),
        }
        (stage / "manifest.json").write_text(json.dumps(result, indent=2) + "\n")
        stage.replace(output_dir)
    return result


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = process_collection(
            source_jsonl=Path(args.source_jsonl),
            source_manifest=Path(args.source_manifest),
            plan_path=Path(args.plan),
            population_path=Path(args.population),
            profile_path=Path(args.phase2_profile),
            config_path=Path(args.config),
            output_dir=Path(args.output_dir),
        )
    except Exception as exc:
        # A failed run never publishes a partial Parquet directory. Preserve a
        # small diagnostic beside it while leaving all source evidence intact.
        output = Path(args.output_dir)
        output.parent.mkdir(parents=True, exist_ok=True)
        stamp = utc_now().replace(":", "").replace("-", "")
        failure = output.parent / f"{output.name}.failure_{stamp}.json"
        evidence = {
            "status": "incomplete",
            "failed_at_utc": utc_now(),
            "error_type": type(exc).__name__,
            "error": str(exc),
            "requested_output": str(output),
            "inputs": {name: str(getattr(args, name)) for name in (
                "source_jsonl", "source_manifest", "plan", "population",
                "phase2_profile", "config",
            )},
        }
        temporary = failure.with_suffix(".part")
        temporary.write_text(json.dumps(evidence, indent=2) + "\n")
        temporary.replace(failure)
        raise
    print(json.dumps({"complete": result["complete"], "output_dir": args.output_dir,
                      "tables": {name: item["rows"] for name, item in result["tables"].items()},
                      "checks_passed": len(result["validation"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
