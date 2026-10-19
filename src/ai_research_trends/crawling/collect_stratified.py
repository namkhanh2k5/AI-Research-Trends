"""Checkpointed collector for the planned publication-year-stratified sample."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ai_research_trends.config import (
    build_year_stratum_filter,
    load_config,
    validate_corpus_work,
)
from ai_research_trends.crawling.openalex_client import (
    OpenAlexClient,
    OpenAlexError,
    canonical_work_id,
    utc_now,
    validate_sample_page,
)
from ai_research_trends.crawling.plan_stratified_sample import validate_sampling_plan
from ai_research_trends.env import load_project_env


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Collect a validated year-stratified OpenAlex sample with page checkpoints. "
            "Without --execute, only validate and summarize the plan."
        )
    )
    parser.add_argument(
        "--plan", default="data/metadata/phase2_sampling_plan.json", help="Sampling plan"
    )
    parser.add_argument("--config", default="config/topics.yaml", help="Study YAML")
    parser.add_argument("--raw-root", default="data/raw/openalex_stratified")
    parser.add_argument("--interim-root", default="data/interim/openalex_stratified")
    parser.add_argument("--seed", type=int, default=20251019)
    parser.add_argument("--per-page", type=int, default=100)
    parser.add_argument("--resume-manifest", help="Manifest inside --raw-root to resume")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Required safety switch: perform API requests and write collection outputs",
    )
    return parser


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical_hash(value: dict[str, Any]) -> str:
    return _sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode())


def _write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _write_jsonl_atomic(path: Path, rows: list[dict[str, Any]]) -> None:
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")))
            handle.write("\n")
    temporary.replace(path)


def validate_collection_plan(plan: dict[str, Any]) -> list[dict[str, Any]]:
    """Backward-compatible name for the full sampling-plan integrity check."""
    return validate_sampling_plan(plan)


def _safe_resume_manifest(value: str | Path, raw_root: Path) -> Path:
    root = raw_root.resolve()
    manifest = Path(value).resolve()
    if not manifest.is_relative_to(root) or manifest.name != "manifest.json":
        raise ValueError("Resume manifest must be a manifest.json located inside --raw-root")
    return manifest


def _validate_page_records(
    records: list[dict[str, Any]],
    *,
    year: int,
    study: dict[str, Any],
    seen_ids: set[str],
) -> None:
    for record in records:
        work_id = canonical_work_id(record.get("id", ""))
        if work_id in seen_ids:
            raise OpenAlexError(f"Duplicate Work ID across sample pages: {work_id}")
        validation = validate_corpus_work(record, study, require_non_retracted=True)
        if not validation.valid:
            raise OpenAlexError(
                f"Work {work_id} violates corpus invariants: {list(validation.errors)}"
            )
        if record.get("publication_year") != year:
            raise OpenAlexError(
                f"Work {work_id} returned in year {year} stratum with publication_year "
                f"{record.get('publication_year')!r}"
            )
        if not str(record["publication_date"]).startswith(f"{year}-"):
            raise OpenAlexError(f"Work {work_id} has a date outside year stratum {year}")
        seen_ids.add(work_id)


def collect_stratified_sample(
    *,
    plan: dict[str, Any],
    config: dict[str, Any],
    client: OpenAlexClient,
    raw_root: str | Path,
    interim_root: str | Path,
    base_seed: int,
    per_page: int = 100,
    resume_manifest: str | Path | None = None,
    plan_sha256: str | None = None,
) -> dict[str, Any]:
    """Collect or resume all planned strata, checkpointing after each valid page."""
    strata = validate_collection_plan(plan)
    if not 1 <= per_page <= 100:
        raise ValueError("per_page must be between 1 and 100")
    raw_root_path = Path(raw_root).resolve()
    interim_root_path = Path(interim_root).resolve()
    if (
        raw_root_path == interim_root_path
        or raw_root_path.is_relative_to(interim_root_path)
        or interim_root_path.is_relative_to(raw_root_path)
    ):
        raise ValueError("Raw and interim roots must be separate, non-nested directories")
    raw_root_path.mkdir(parents=True, exist_ok=True)
    interim_root_path.mkdir(parents=True, exist_ok=True)

    plan_digest = plan_sha256 or _canonical_hash(plan)
    config_digest = _canonical_hash(config)
    if resume_manifest:
        manifest_path = _safe_resume_manifest(resume_manifest, raw_root_path)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("plan_sha256") != plan_digest:
            raise ValueError("Resume plan checksum does not match the original run")
        if manifest.get("config_sha256") != config_digest:
            raise ValueError("Resume config checksum does not match the original run")
        if manifest.get("base_seed") != base_seed or manifest.get("per_page") != per_page:
            raise ValueError("Resume seed and per-page settings must match the original run")
        run_dir = manifest_path.parent
        interim_dir = interim_root_path / manifest["run_id"]
        interim_dir.mkdir(parents=True, exist_ok=True)
        manifest.update({"status": "running", "complete": False, "resumed_at_utc": utc_now()})
        manifest.pop("error", None)
        manifest.pop("error_type", None)
        _write_json_atomic(manifest_path, manifest)
    else:
        run_id = datetime.now(timezone.utc).strftime("stratified_%Y%m%dT%H%M%SZ")
        run_dir = raw_root_path / run_id
        interim_dir = interim_root_path / run_id
        run_dir.mkdir(parents=True, exist_ok=False)
        interim_dir.mkdir(parents=True, exist_ok=False)
        manifest_path = run_dir / "manifest.json"
        manifest = {
            "schema_version": 1,
            "run_id": run_id,
            "created_at_utc": utc_now(),
            "status": "running",
            "complete": False,
            "endpoint": f"{client.base_url}/works",
            "plan_sha256": plan_digest,
            "config_sha256": config_digest,
            "base_seed": base_seed,
            "per_page": per_page,
            "requested_records": plan["allocated_sample_size"],
            "sampling_semantics": (
                "OpenAlex documents sample as random and seed as reproducible. Uniform "
                "within-stratum inclusion and stability across database updates are not "
                "established API guarantees; recorded weights are therefore nominal."
            ),
            "strata": [
                {
                    **row,
                    "seed": base_seed + int(row["publication_year"]),
                    "filter": build_year_stratum_filter(
                        config["study"], int(row["publication_year"])
                    ),
                    "status": "pending",
                    "pages": [],
                }
                for row in strata
            ],
        }
        _write_json_atomic(manifest_path, manifest)

    seen_ids: set[str] = set()
    collected_records: list[dict[str, Any]] = []
    try:
        for stratum in manifest["strata"]:
            year = int(stratum["publication_year"])
            requested = int(stratum["sample_size"])
            total_pages = math.ceil(requested / per_page)
            stratum_dir = run_dir / f"year_{year}"
            stratum_dir.mkdir(parents=True, exist_ok=True)
            by_page = {int(page["page_number"]): page for page in stratum["pages"]}
            for page_number in range(1, total_pages + 1):
                raw_path = stratum_dir / f"page_{page_number:04d}.json"
                entry = by_page.get(page_number)
                if entry:
                    raw_bytes = raw_path.read_bytes()
                    if _sha256(raw_bytes) != entry["sha256"]:
                        raise OpenAlexError(f"Checkpoint checksum mismatch for {raw_path}")
                    payload = json.loads(raw_bytes)
                    source = "checkpoint"
                elif raw_path.exists():
                    # Recover a complete response written immediately before a crash.
                    raw_bytes = raw_path.read_bytes()
                    payload = json.loads(raw_bytes)
                    source = "recovered_orphan"
                else:
                    params = {
                        "filter": stratum["filter"],
                        "sample": requested,
                        "seed": stratum["seed"],
                        "per_page": per_page,
                        "page": page_number,
                    }
                    response = client.request("works", params)
                    raw_bytes = response.content
                    raw_path.write_bytes(raw_bytes)
                    payload = json.loads(raw_bytes)
                    source = "api"

                envelope = validate_sample_page(
                    payload,
                    requested_records=requested,
                    page_number=page_number,
                    per_page=per_page,
                )
                _validate_page_records(
                    envelope.results, year=year, study=config["study"], seen_ids=seen_ids
                )
                collected_records.extend(envelope.results)
                if not entry:
                    stratum["pages"].append(
                        {
                            "page_number": page_number,
                            "path": str(raw_path),
                            "sha256": _sha256(raw_bytes),
                            "result_count": len(envelope.results),
                            "checkpointed_at_utc": utc_now(),
                            "source": source,
                        }
                    )
                    _write_json_atomic(manifest_path, manifest)
            stratum["status"] = "complete"
            stratum["collected_records"] = requested
            _write_json_atomic(manifest_path, manifest)

        expected_total = int(manifest["requested_records"])
        if len(collected_records) != expected_total or len(seen_ids) != expected_total:
            raise OpenAlexError(
                f"Collected {len(collected_records)} records ({len(seen_ids)} unique); "
                f"expected {expected_total}"
            )
        raw_jsonl = run_dir / "works.jsonl"
        interim_jsonl = interim_dir / "works.jsonl"
        _write_jsonl_atomic(raw_jsonl, collected_records)
        _write_jsonl_atomic(interim_jsonl, collected_records)
        manifest.update(
            {
                "status": "complete",
                "complete": True,
                "completed_at_utc": utc_now(),
                "raw_records": len(collected_records),
                "unique_work_ids": len(seen_ids),
                "raw_jsonl": str(raw_jsonl),
                "raw_jsonl_sha256": _sha256(raw_jsonl.read_bytes()),
                "interim_jsonl": str(interim_jsonl),
            }
        )
        _write_json_atomic(manifest_path, manifest)
        return manifest
    except Exception as exc:
        manifest.update(
            {
                "status": "failed",
                "complete": False,
                "failed_at_utc": utc_now(),
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
        )
        _write_json_atomic(manifest_path, manifest)
        raise


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    plan_path = Path(args.plan)
    plan_bytes = plan_path.read_bytes()
    plan = json.loads(plan_bytes)
    source = Path(plan.get("population_counts_source", ""))
    if not source.is_file():
        raise ValueError(f"Declared population-count source does not exist: {source}")
    validate_sampling_plan(plan, population_source_bytes=source.read_bytes())
    if not args.execute:
        print(
            json.dumps(
                {
                    "validated": True,
                    "executed": False,
                    "planned_records": plan["allocated_sample_size"],
                    "message": "Re-run with --execute to start or resume API collection.",
                }
            )
        )
        return 0

    load_project_env()
    result = collect_stratified_sample(
        plan=plan,
        config=load_config(args.config),
        client=OpenAlexClient(),
        raw_root=args.raw_root,
        interim_root=args.interim_root,
        base_seed=args.seed,
        per_page=args.per_page,
        resume_manifest=args.resume_manifest,
        plan_sha256=_sha256(plan_bytes),
    )
    print(json.dumps({"status": result["status"], "run_id": result["run_id"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
