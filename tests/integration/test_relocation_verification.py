"""Fresh-clone verification must keep checksum requirements and reject ambiguity."""

import hashlib
import json
from pathlib import Path

import pytest

from ai_research_trends.crawling.verify_collection import (
    CollectionVerificationError,
    _relocated_path,
)
from ai_research_trends.preprocessing.validate_tables import (
    ProcessedValidationError,
    verified_processing_source,
)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _checkout(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "checkout"
    root.mkdir()
    (root / "pyproject.toml").write_text("[project]\nname='fixture'\n")
    run = root / "data/raw/openalex_stratified/run_1"
    run.mkdir(parents=True)
    return root, run


def test_old_absolute_collection_page_maps_only_to_same_run(tmp_path: Path) -> None:
    root, run = _checkout(tmp_path)
    expected = run / "year_2020/page_0001.json"
    expected.parent.mkdir()
    expected.write_bytes(b"page")
    old = "/old/machine/data/raw/openalex_stratified/run_1/year_2020/page_0001.json"
    assert _relocated_path(old, expected, run, "page") == expected
    with pytest.raises(CollectionVerificationError, match="run layout"):
        _relocated_path(old.replace("run_1", "other"), expected, run, "page")
    with pytest.raises(CollectionVerificationError, match="Unsafe"):
        _relocated_path("/old/data/../secret", expected, run, "page")


def test_missing_interim_uses_only_hash_equivalent_raw_bytes(tmp_path: Path) -> None:
    root, _ = _checkout(tmp_path)
    processed = root / "data/processed/openalex_stratified/run_1"
    processed.mkdir(parents=True)
    raw = root / "data/raw/openalex_stratified/run_1"
    payload = b'{"id":"https://openalex.org/W1"}\n'
    (raw / "works.jsonl").write_bytes(payload)
    raw_manifest = {"raw_jsonl_sha256": _sha(payload)}
    manifest_bytes = json.dumps(raw_manifest).encode()
    (raw / "manifest.json").write_bytes(manifest_bytes)
    processing_manifest = {"inputs": {
        "source_manifest": {
            "path": "/old/machine/data/raw/openalex_stratified/run_1/manifest.json",
            "sha256": _sha(manifest_bytes),
        }
    }}
    source = {
        "path": "/old/machine/data/interim/openalex_stratified/run_1/works.jsonl",
        "sha256": _sha(payload),
    }
    path, status = verified_processing_source("source_jsonl", source, processed, processing_manifest)
    assert path == raw / "works.jsonl"
    assert status == "verified_identical_raw_fallback"
    source["sha256"] = _sha(b"different")
    with pytest.raises(ProcessedValidationError, match="hashes differ"):
        verified_processing_source("source_jsonl", source, processed, processing_manifest)
    source["sha256"] = _sha(payload)
    (raw / "works.jsonl").write_bytes(b"tampered")
    with pytest.raises(ProcessedValidationError, match="missing or changed"):
        verified_processing_source("source_jsonl", source, processed, processing_manifest)


def test_retained_source_mismatch_is_not_replaced_by_fallback(tmp_path: Path) -> None:
    root, _ = _checkout(tmp_path)
    processed = root / "data/processed/openalex_stratified/run_1"
    processed.mkdir(parents=True)
    interim = root / "data/interim/openalex_stratified/run_1/works.jsonl"
    interim.parent.mkdir(parents=True)
    interim.write_bytes(b"tampered")
    source = {"path": "data/interim/openalex_stratified/run_1/works.jsonl", "sha256": _sha(b"good")}
    with pytest.raises(ProcessedValidationError, match="checksum differs"):
        verified_processing_source("source_jsonl", source, processed, {"inputs": {}})
