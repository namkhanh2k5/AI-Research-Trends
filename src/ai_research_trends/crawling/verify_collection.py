"""Read-only integrity verification for a completed stratified collection."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

from ai_research_trends.crawling.openalex_client import (
    canonical_work_id,
    validate_sample_page,
)


class CollectionVerificationError(RuntimeError):
    """Raised when completed collection evidence fails an integrity check."""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Verify a completed collection manifest and outputs without modifying them."
    )
    parser.add_argument("manifest", help="Path to a completed stratified manifest.json")
    return parser


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require_file(path: Path, label: str) -> None:
    if not path.is_file():
        raise CollectionVerificationError(f"Missing {label}: {path}")


def _verify_digest(path: Path, expected: Any, label: str) -> str:
    if not isinstance(expected, str) or len(expected) != 64:
        raise CollectionVerificationError(f"Manifest lacks a valid SHA-256 for {label}")
    actual = _file_sha256(path)
    if actual != expected:
        raise CollectionVerificationError(
            f"SHA-256 mismatch for {label}: expected {expected}, found {actual}"
        )
    return actual


def _jsonl_work_ids(path: Path) -> list[str]:
    work_ids: list[str] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise CollectionVerificationError(
                    f"Malformed JSONL at {path}:{line_number}: {exc}"
                ) from exc
            if not isinstance(record, dict):
                raise CollectionVerificationError(
                    f"JSONL record at {path}:{line_number} is not an object"
                )
            try:
                work_ids.append(canonical_work_id(record.get("id", "")))
            except ValueError as exc:
                raise CollectionVerificationError(
                    f"Invalid Work ID at {path}:{line_number}: {exc}"
                ) from exc
    return work_ids


def verify_completed_collection(manifest_path: str | Path) -> dict[str, Any]:
    """Verify immutable run evidence and return a summary; never write to disk."""
    path = Path(manifest_path).resolve()
    _require_file(path, "manifest")
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise CollectionVerificationError(f"Malformed manifest {path}: {exc}") from exc
    if not isinstance(manifest, dict):
        raise CollectionVerificationError("Manifest must be a JSON object")
    if manifest.get("complete") is not True or manifest.get("status") != "complete":
        raise CollectionVerificationError("Run is not declared complete")

    run_dir = path.parent
    per_page = manifest.get("per_page")
    requested_total = manifest.get("requested_records")
    if not isinstance(per_page, int) or not 1 <= per_page <= 100:
        raise CollectionVerificationError("Manifest per_page is invalid")
    if not isinstance(requested_total, int) or requested_total < 1:
        raise CollectionVerificationError("Manifest requested_records is invalid")

    page_work_ids: list[str] = []
    page_count = 0
    for stratum in manifest.get("strata", []):
        year = int(stratum["publication_year"])
        requested = int(stratum["sample_size"])
        entries = stratum.get("pages", [])
        if not isinstance(entries, list):
            raise CollectionVerificationError(f"Year {year} pages is not a list")
        expected_page_numbers = list(range(1, math.ceil(requested / per_page) + 1))
        actual_page_numbers = [int(entry["page_number"]) for entry in entries]
        if actual_page_numbers != expected_page_numbers:
            raise CollectionVerificationError(
                f"Year {year} page sequence {actual_page_numbers} != {expected_page_numbers}"
            )
        for entry in entries:
            page_number = int(entry["page_number"])
            expected_path = (run_dir / f"year_{year}" / f"page_{page_number:04d}.json").resolve()
            recorded_path = Path(entry.get("path", "")).resolve()
            if recorded_path != expected_path:
                raise CollectionVerificationError(
                    f"Recorded page path does not match run layout: {recorded_path}"
                )
            _require_file(expected_path, "raw page")
            _verify_digest(expected_path, entry.get("sha256"), "raw page")
            if entry.get("raw_bytes") != expected_path.stat().st_size:
                raise CollectionVerificationError(f"Raw byte count mismatch for {expected_path}")
            try:
                payload = json.loads(expected_path.read_bytes())
                envelope = validate_sample_page(
                    payload,
                    requested_records=requested,
                    page_number=page_number,
                    per_page=per_page,
                )
                ids = [canonical_work_id(row.get("id", "")) for row in envelope.results]
            except Exception as exc:
                raise CollectionVerificationError(
                    f"Invalid raw page {expected_path}: {type(exc).__name__}: {exc}"
                ) from exc
            if entry.get("result_count") != len(ids) or entry.get("work_ids") != ids:
                raise CollectionVerificationError(
                    f"Manifest membership mismatch for year {year}, page {page_number}"
                )
            page_work_ids.extend(ids)
            page_count += 1

    if len(page_work_ids) != requested_total or len(set(page_work_ids)) != requested_total:
        raise CollectionVerificationError(
            "Raw pages do not contain the declared number of unique Work IDs"
        )

    raw_jsonl = Path(manifest.get("raw_jsonl", "")).resolve()
    if raw_jsonl != (run_dir / "works.jsonl").resolve():
        raise CollectionVerificationError("Raw JSONL path does not match the run directory")
    interim_jsonl = Path(manifest.get("interim_jsonl", "")).resolve()
    _require_file(raw_jsonl, "raw JSONL")
    _require_file(interim_jsonl, "interim JSONL")
    raw_digest = _verify_digest(raw_jsonl, manifest.get("raw_jsonl_sha256"), "raw JSONL")
    interim_digest = _verify_digest(
        interim_jsonl, manifest.get("interim_jsonl_sha256"), "interim JSONL"
    )
    raw_ids = _jsonl_work_ids(raw_jsonl)
    interim_ids = _jsonl_work_ids(interim_jsonl)
    if raw_ids != page_work_ids or interim_ids != page_work_ids:
        raise CollectionVerificationError(
            "Raw pages, raw JSONL, and interim JSONL do not have identical ordered Work IDs"
        )

    diagnostics = manifest.get("diagnostics", {})
    expected_pages = sum(
        math.ceil(int(stratum["sample_size"]) / per_page) for stratum in manifest["strata"]
    )
    if page_count != expected_pages:
        raise CollectionVerificationError("Verified page count does not match planned page count")
    if diagnostics.get("pages_expected") != page_count:
        raise CollectionVerificationError("Diagnostic expected page count is inconsistent")
    if diagnostics.get("pages_checkpointed") != page_count:
        raise CollectionVerificationError("Diagnostic checkpointed page count is inconsistent")
    if diagnostics.get("run_complete") is not True:
        raise CollectionVerificationError("Diagnostics do not mark the run complete")

    return {
        "valid": True,
        "manifest": str(path),
        "run_id": manifest.get("run_id"),
        "verified_pages": page_count,
        "verified_unique_work_ids": len(set(page_work_ids)),
        "raw_jsonl_sha256": raw_digest,
        "interim_jsonl_sha256": interim_digest,
        "read_only": True,
    }


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    print(json.dumps(verify_completed_collection(args.manifest), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
