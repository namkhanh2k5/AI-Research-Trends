"""Checkpointed collector for the planned publication-year-stratified sample."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

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

RESUME_VERIFICATION_MODES = ("all", "sampled", "minimal")


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
        "--resume-verify",
        choices=RESUME_VERIFICATION_MODES,
        default="all",
        help=(
            "Checkpoint membership verification on resume: all pages (default), "
            "first/last pages per stratum, or the first page per stratum"
        ),
    )
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


def _write_bytes_atomic(
    path: Path,
    value: bytes,
    *,
    before_replace: Callable[[Path], None] | None = None,
) -> None:
    """Durably write raw evidence without exposing a partial final page path."""
    if path.exists():
        raise FileExistsError(f"Refusing to overwrite existing raw evidence: {path}")
    temporary = path.with_suffix(f"{path.suffix}.part")
    if temporary.exists():
        raise FileExistsError(f"Interrupted raw-page temporary file already exists: {temporary}")
    with temporary.open("xb") as handle:
        handle.write(value)
        handle.flush()
        os.fsync(handle.fileno())
    if before_replace is not None:
        before_replace(temporary)
    temporary.replace(path)
    try:
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except OSError:
        # Some filesystems do not support directory fsync; the file rename is still atomic.
        pass


def _validate_records_for_year(
    records: list[dict[str, Any]], *, year: int, study: dict[str, Any]
) -> list[str]:
    page_ids: list[str] = []
    for record in records:
        work_id = canonical_work_id(record.get("id", ""))
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
        page_ids.append(work_id)
    return page_ids


def _ensure_diagnostics(manifest: dict[str, Any]) -> dict[str, Any]:
    """Create or upgrade the manifest diagnostics container."""
    diagnostics = manifest.setdefault("diagnostics", {})
    expected_pages = sum(
        math.ceil(int(stratum["sample_size"]) / int(manifest["per_page"]))
        for stratum in manifest.get("strata", [])
    )
    diagnostics.setdefault("pages_expected", expected_pages)
    diagnostics.setdefault(
        "pages_checkpointed",
        sum(len(stratum.get("pages", [])) for stratum in manifest.get("strata", [])),
    )
    diagnostics.setdefault("raw_page_bytes", 0)
    diagnostics.setdefault("resume_probe_pages", 0)
    diagnostics.setdefault("resume_probe_bytes", 0)
    diagnostics.setdefault("api_requests_attempted", 0)
    diagnostics.setdefault("api_requests_succeeded", 0)
    diagnostics.setdefault("api_failures", [])
    diagnostics.setdefault("run_failures", [])
    diagnostics.setdefault(
        "duplicate_check",
        {
            "work_id_validation_operations": 0,
            "duplicate_work_ids_detected": 0,
            "passed": None,
        },
    )
    diagnostics.setdefault("run_complete", False)
    diagnostics.setdefault(
        "work_ids_location", "strata[].pages[].work_ids and resume_consistency_probes[]"
    )
    diagnostics.setdefault(
        "memory_model",
        (
            "This collector retains validated records and Work IDs in memory until final "
            "JSONL creation; appropriate for 12,000 works, not an unbounded crawl."
        ),
    )
    return diagnostics


def _refresh_disk_diagnostics(manifest: dict[str, Any], run_dir: Path) -> None:
    diagnostics = _ensure_diagnostics(manifest)
    raw_pages = sorted(run_dir.glob("year_*/page_*.json"))
    diagnostics["raw_page_files_on_disk"] = len(raw_pages)
    diagnostics["raw_page_bytes_on_disk"] = sum(path.stat().st_size for path in raw_pages)


def _request_with_diagnostics(
    *,
    client: OpenAlexClient,
    params: dict[str, Any],
    manifest: dict[str, Any],
    manifest_path: Path,
    context: dict[str, Any],
):
    diagnostics = _ensure_diagnostics(manifest)
    diagnostics["api_requests_attempted"] += 1
    try:
        response = client.request("works", params)
    except Exception as exc:
        diagnostics["api_failures"].append(
            {
                "failed_at_utc": utc_now(),
                **context,
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
        )
        _write_json_atomic(manifest_path, manifest)
        raise
    diagnostics["api_requests_succeeded"] += 1
    return response


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
    diagnostics: dict[str, Any],
) -> list[str]:
    page_ids = _validate_records_for_year(records, year=year, study=study)
    for work_id in page_ids:
        diagnostics["duplicate_check"]["work_id_validation_operations"] += 1
        if work_id in seen_ids:
            diagnostics["duplicate_check"]["duplicate_work_ids_detected"] += 1
            diagnostics["duplicate_check"]["passed"] = False
            raise OpenAlexError(f"Duplicate Work ID across sample pages: {work_id}")
        seen_ids.add(work_id)
    return page_ids


def _work_ids(records: list[dict[str, Any]]) -> list[str]:
    """Return ordered canonical Work IDs for a page-membership comparison."""
    return [canonical_work_id(record.get("id", "")) for record in records]


def _select_resume_checkpoints(
    manifest: dict[str, Any], verification_mode: str
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """Select deterministic checkpoints; recovered orphans are always verified."""
    if verification_mode not in RESUME_VERIFICATION_MODES:
        raise ValueError(
            f"resume verification mode must be one of {RESUME_VERIFICATION_MODES}"
        )
    selected: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for stratum in sorted(manifest["strata"], key=lambda row: int(row["publication_year"])):
        pages = sorted(stratum.get("pages", []), key=lambda row: int(row["page_number"]))
        if not pages:
            continue
        if verification_mode == "all":
            page_numbers = {int(page["page_number"]) for page in pages}
        elif verification_mode == "sampled":
            page_numbers = {int(pages[0]["page_number"]), int(pages[-1]["page_number"])}
        else:
            page_numbers = {int(pages[0]["page_number"])}
        page_numbers.update(
            int(page["page_number"])
            for page in pages
            if page.get("resume_verification_required") is True
        )
        selected.extend(
            (stratum, page)
            for page in pages
            if int(page["page_number"]) in page_numbers
        )
    return selected


def _quarantine_file(
    *,
    path: Path,
    run_dir: Path,
    manifest: dict[str, Any],
    reason: str,
    error: str | None = None,
) -> Path:
    """Atomically move suspect raw evidence aside and record its provenance."""
    raw_bytes = path.read_bytes()
    quarantine_dir = run_dir / "quarantine"
    quarantine_dir.mkdir(parents=True, exist_ok=True)
    target = quarantine_dir / f"{path.parent.name}__{path.name}__{_sha256(raw_bytes)[:12]}"
    if target.exists():
        target = quarantine_dir / (
            f"{path.parent.name}__{path.name}__{_sha256(raw_bytes)[:12]}__"
            f"{len(manifest.get('quarantined_files', [])) + 1:04d}"
        )
    path.replace(target)
    manifest.setdefault("quarantined_files", []).append(
        {
            "quarantined_at_utc": utc_now(),
            "original_path": str(path),
            "quarantine_path": str(target),
            "sha256": _sha256(raw_bytes),
            "bytes": len(raw_bytes),
            "reason": reason,
            "error": error,
        }
    )
    return target


def _reconcile_orphan_pages(
    *,
    manifest: dict[str, Any],
    manifest_path: Path,
    run_dir: Path,
    config: dict[str, Any],
    per_page: int,
) -> None:
    """Quarantine partial/malformed orphans and register valid ones for probing."""
    changed = False
    for partial_path in sorted(run_dir.glob("resume_probe_*/*.part")):
        _quarantine_file(
            path=partial_path,
            run_dir=run_dir,
            manifest=manifest,
            reason="interrupted_atomic_probe_write",
        )
        changed = True
    for stratum in manifest["strata"]:
        year = int(stratum["publication_year"])
        requested = int(stratum["sample_size"])
        known_pages = {int(page["page_number"]) for page in stratum.get("pages", [])}
        stratum_dir = run_dir / f"year_{year}"
        stratum_dir.mkdir(parents=True, exist_ok=True)
        for page_number in range(1, math.ceil(requested / per_page) + 1):
            raw_path = stratum_dir / f"page_{page_number:04d}.json"
            partial_path = raw_path.with_suffix(f"{raw_path.suffix}.part")
            if partial_path.exists():
                _quarantine_file(
                    path=partial_path,
                    run_dir=run_dir,
                    manifest=manifest,
                    reason="interrupted_atomic_raw_write",
                )
                changed = True
            if page_number in known_pages or not raw_path.exists():
                continue
            raw_bytes = raw_path.read_bytes()
            try:
                envelope = validate_sample_page(
                    json.loads(raw_bytes),
                    requested_records=requested,
                    page_number=page_number,
                    per_page=per_page,
                )
                page_ids = _validate_records_for_year(
                    envelope.results, year=year, study=config["study"]
                )
            except Exception as exc:
                _quarantine_file(
                    path=raw_path,
                    run_dir=run_dir,
                    manifest=manifest,
                    reason="malformed_or_invalid_orphan_page",
                    error=f"{type(exc).__name__}: {exc}",
                )
                changed = True
                continue
            stratum.setdefault("pages", []).append(
                {
                    "page_number": page_number,
                    "path": str(raw_path),
                    "sha256": _sha256(raw_bytes),
                    "raw_bytes": len(raw_bytes),
                    "result_count": len(envelope.results),
                    "work_ids": page_ids,
                    "checkpointed_at_utc": utc_now(),
                    "source": "recovered_orphan",
                    "resume_verification_required": True,
                }
            )
            stratum["pages"].sort(key=lambda page: int(page["page_number"]))
            changed = True
    if changed:
        diagnostics = _ensure_diagnostics(manifest)
        diagnostics["pages_checkpointed"] = sum(
            len(stratum.get("pages", [])) for stratum in manifest["strata"]
        )
        _refresh_disk_diagnostics(manifest, run_dir)
        _write_json_atomic(manifest_path, manifest)


def _probe_resume_consistency(
    *,
    manifest: dict[str, Any],
    manifest_path: Path,
    run_dir: Path,
    client: OpenAlexClient,
    per_page: int,
    verification_mode: str,
) -> None:
    """Re-fetch selected checkpoint pages and compare ordered Work IDs."""
    probes = manifest.setdefault("resume_consistency_probes", [])
    disk_probe_numbers = []
    for path in run_dir.glob("resume_probe_*"):
        try:
            disk_probe_numbers.append(int(path.name.rsplit("_", 1)[-1]))
        except ValueError:
            continue
    prior_attempts = manifest.get("resume_verification_attempts", [])
    probe_number = max([len(prior_attempts), *disk_probe_numbers], default=0) + 1
    probe_dir = run_dir / f"resume_probe_{probe_number:04d}"
    probe_dir.mkdir(parents=True, exist_ok=False)
    selected = _select_resume_checkpoints(manifest, verification_mode)
    total_checkpoints = sum(len(stratum.get("pages", [])) for stratum in manifest["strata"])
    attempt = {
        "probe_number": probe_number,
        "started_at_utc": utc_now(),
        "verification_mode": verification_mode,
        "checkpoint_pages_available": total_checkpoints,
        "checkpoint_pages_selected": len(selected),
        "status": "running",
        "limitation": (
            "OpenAlex provides no snapshot isolation. Matching IDs establish only that "
            "the checked seeded pages matched when probed; metadata, unchecked pages, "
            "and subsequent source changes are not guaranteed stable."
        ),
    }
    manifest.setdefault("resume_verification_attempts", []).append(attempt)
    if not selected:
        probes.append(
            {
                "probe_number": probe_number,
                "checked_at_utc": utc_now(),
                "verification_mode": verification_mode,
                "status": "skipped_no_checkpointed_pages",
                "limitation": "No prior page existed, so there was no mixed-snapshot risk to test.",
            }
        )
        attempt.update({"status": "skipped_no_checkpointed_pages", "finished_at_utc": utc_now()})
        _write_json_atomic(manifest_path, manifest)
        return

    for stratum, checkpoint in selected:
        year = int(stratum["publication_year"])
        requested = int(stratum["sample_size"])
        page_number = int(checkpoint["page_number"])
        checkpoint_path = run_dir / f"year_{year}" / f"page_{page_number:04d}.json"
        checkpoint_bytes = checkpoint_path.read_bytes()
        if _sha256(checkpoint_bytes) != checkpoint["sha256"]:
            raise OpenAlexError(f"Checkpoint checksum mismatch for {checkpoint_path}")

        params = {
            "filter": stratum["filter"],
            "sample": requested,
            "seed": stratum["seed"],
            "per_page": per_page,
            "page": page_number,
        }
        response = _request_with_diagnostics(
            client=client,
            params=params,
            manifest=manifest,
            manifest_path=manifest_path,
            context={
                "request_role": "resume_consistency_probe",
                "publication_year": year,
                "page_number": page_number,
            },
        )
        probe_path = probe_dir / f"year_{year}_page_{page_number:04d}.json"
        _write_bytes_atomic(probe_path, response.content)
        diagnostics = _ensure_diagnostics(manifest)
        diagnostics["resume_probe_pages"] += 1
        diagnostics["resume_probe_bytes"] += len(response.content)
        record: dict[str, Any] = {
            "probe_number": probe_number,
            "checked_at_utc": utc_now(),
            "verification_mode": verification_mode,
            "publication_year": year,
            "page_number": page_number,
            "query_parameters": params,
            "checkpoint_path": str(checkpoint_path),
            "checkpoint_sha256": checkpoint["sha256"],
            "probe_raw_path": str(probe_path),
            "probe_raw_sha256": _sha256(response.content),
            "probe_raw_bytes": len(response.content),
        }
        try:
            checkpoint_envelope = validate_sample_page(
                json.loads(checkpoint_bytes),
                requested_records=requested,
                page_number=page_number,
                per_page=per_page,
            )
            probe_envelope = validate_sample_page(
                json.loads(response.content),
                requested_records=requested,
                page_number=page_number,
                per_page=per_page,
            )
            checkpoint_ids = _work_ids(checkpoint_envelope.results)
            probe_ids = _work_ids(probe_envelope.results)
            record.update(
                {
                    "checkpoint_work_ids": checkpoint_ids,
                    "probe_work_ids": probe_ids,
                    "ordered_ids_match": checkpoint_ids == probe_ids,
                    "status": "passed" if checkpoint_ids == probe_ids else "failed",
                }
            )
        except Exception as exc:
            record.update(
                {
                    "ordered_ids_match": False,
                    "status": "invalid_probe_response",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            )
            probes.append(record)
            _write_json_atomic(manifest_path, manifest)
            raise

        probes.append(record)
        if record["ordered_ids_match"]:
            checkpoint["resume_verification_required"] = False
            checkpoint["resume_verified_at_utc"] = utc_now()
        _write_json_atomic(manifest_path, manifest)
        if not record["ordered_ids_match"]:
            attempt.update({"status": "failed", "finished_at_utc": utc_now()})
            _write_json_atomic(manifest_path, manifest)
            raise OpenAlexError(
                "OpenAlex seeded sample membership changed since the checkpoint for "
                f"year {year}, page {page_number}; refusing to mix retrieval snapshots"
            )
    attempt.update({"status": "passed", "finished_at_utc": utc_now()})
    _write_json_atomic(manifest_path, manifest)


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
    resume_verify: str = "all",
    plan_sha256: str | None = None,
) -> dict[str, Any]:
    """Collect or resume all planned strata, checkpointing after each valid page."""
    strata = validate_collection_plan(plan)
    if not 1 <= per_page <= 100:
        raise ValueError("per_page must be between 1 and 100")
    if resume_verify not in RESUME_VERIFICATION_MODES:
        raise ValueError(f"resume_verify must be one of {RESUME_VERIFICATION_MODES}")
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
        _ensure_diagnostics(manifest)["run_complete"] = False
        _write_json_atomic(manifest_path, manifest)
    else:
        run_id = datetime.now(timezone.utc).strftime("stratified_%Y%m%dT%H%M%SZ")
        run_dir = raw_root_path / run_id
        interim_dir = interim_root_path / run_id
        run_dir.mkdir(parents=True, exist_ok=False)
        interim_dir.mkdir(parents=True, exist_ok=False)
        manifest_path = run_dir / "manifest.json"
        manifest = {
            "schema_version": 2,
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
        _ensure_diagnostics(manifest)
        _write_json_atomic(manifest_path, manifest)

    seen_ids: set[str] = set()
    collected_records: list[dict[str, Any]] = []
    try:
        if resume_manifest:
            _reconcile_orphan_pages(
                manifest=manifest,
                manifest_path=manifest_path,
                run_dir=run_dir,
                config=config,
                per_page=per_page,
            )
            _probe_resume_consistency(
                manifest=manifest,
                manifest_path=manifest_path,
                run_dir=run_dir,
                client=client,
                per_page=per_page,
                verification_mode=resume_verify,
            )
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
                    raise OpenAlexError(
                        f"Unregistered raw page remained after orphan reconciliation: {raw_path}"
                    )
                else:
                    params = {
                        "filter": stratum["filter"],
                        "sample": requested,
                        "seed": stratum["seed"],
                        "per_page": per_page,
                        "page": page_number,
                    }
                    response = _request_with_diagnostics(
                        client=client,
                        params=params,
                        manifest=manifest,
                        manifest_path=manifest_path,
                        context={
                            "request_role": "sample_page",
                            "publication_year": year,
                            "page_number": page_number,
                        },
                    )
                    raw_bytes = response.content
                    _write_bytes_atomic(raw_path, raw_bytes)
                    _refresh_disk_diagnostics(manifest, run_dir)
                    payload = json.loads(raw_bytes)
                    source = "api"

                envelope = validate_sample_page(
                    payload,
                    requested_records=requested,
                    page_number=page_number,
                    per_page=per_page,
                )
                page_ids = _validate_page_records(
                    envelope.results,
                    year=year,
                    study=config["study"],
                    seen_ids=seen_ids,
                    diagnostics=_ensure_diagnostics(manifest),
                )
                collected_records.extend(envelope.results)
                if not entry:
                    stratum["pages"].append(
                        {
                            "page_number": page_number,
                            "path": str(raw_path),
                            "sha256": _sha256(raw_bytes),
                            "raw_bytes": len(raw_bytes),
                            "result_count": len(envelope.results),
                            "work_ids": page_ids,
                            "checkpointed_at_utc": utc_now(),
                            "source": source,
                        }
                    )
                    diagnostics = _ensure_diagnostics(manifest)
                    diagnostics["pages_checkpointed"] = sum(
                        len(item.get("pages", [])) for item in manifest["strata"]
                    )
                    diagnostics["raw_page_bytes"] = sum(
                        int(page.get("raw_bytes", 0))
                        for item in manifest["strata"]
                        for page in item.get("pages", [])
                    )
                    _write_json_atomic(manifest_path, manifest)
                else:
                    recorded_ids = entry.get("work_ids")
                    if recorded_ids is not None and recorded_ids != page_ids:
                        raise OpenAlexError(
                            f"Checkpoint Work ID manifest mismatch for year {year}, "
                            f"page {page_number}"
                        )
                    entry.setdefault("work_ids", page_ids)
                    entry.setdefault("raw_bytes", len(raw_bytes))
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
        diagnostics = _ensure_diagnostics(manifest)
        _refresh_disk_diagnostics(manifest, run_dir)
        diagnostics.update(
            {
                "pages_checkpointed": sum(
                    len(item.get("pages", [])) for item in manifest["strata"]
                ),
                "raw_page_bytes": sum(
                    int(page.get("raw_bytes", 0))
                    for item in manifest["strata"]
                    for page in item.get("pages", [])
                ),
                "retrieved_work_id_count": len(seen_ids),
                "retrieved_work_ids_sha256": _sha256(
                    "\n".join(_work_ids(collected_records)).encode()
                ),
                "raw_jsonl_bytes": raw_jsonl.stat().st_size,
                "interim_jsonl_bytes": interim_jsonl.stat().st_size,
                "duplicate_check": {
                    **diagnostics["duplicate_check"],
                    "unique_work_ids": len(seen_ids),
                    "passed": diagnostics["duplicate_check"][
                        "duplicate_work_ids_detected"
                    ]
                    == 0,
                },
                "run_complete": True,
            }
        )
        diagnostics["total_bytes_written"] = (
            diagnostics["raw_page_bytes_on_disk"]
            + diagnostics["resume_probe_bytes"]
            + diagnostics["raw_jsonl_bytes"]
            + diagnostics["interim_jsonl_bytes"]
        )
        _write_json_atomic(manifest_path, manifest)
        return manifest
    except Exception as exc:
        diagnostics = _ensure_diagnostics(manifest)
        for attempt in manifest.get("resume_verification_attempts", []):
            if attempt.get("status") == "running":
                attempt.update(
                    {
                        "status": "failed",
                        "finished_at_utc": utc_now(),
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    }
                )
        _refresh_disk_diagnostics(manifest, run_dir)
        diagnostics["run_complete"] = False
        diagnostics["pages_checkpointed"] = sum(
            len(item.get("pages", [])) for item in manifest.get("strata", [])
        )
        diagnostics["run_failures"].append(
            {
                "failed_at_utc": utc_now(),
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
        )
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
        resume_verify=args.resume_verify,
        plan_sha256=_sha256(plan_bytes),
    )
    diagnostics = result["diagnostics"]
    print(
        json.dumps(
            {
                "status": result["status"],
                "complete": result["complete"],
                "run_id": result["run_id"],
                "pages": {
                    "checkpointed": diagnostics["pages_checkpointed"],
                    "expected": diagnostics["pages_expected"],
                },
                "raw_page_bytes": diagnostics["raw_page_bytes_on_disk"],
                "unique_work_ids": result["unique_work_ids"],
                "api_failures": len(diagnostics["api_failures"]),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
