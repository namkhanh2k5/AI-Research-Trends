"""Portable manifest paths and strict retained-input verification."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from ai_research_trends.artifact_paths import resolve_manifest_input
from ai_research_trends.ml.validate_integrated_data import verify_input_hashes


def _checkout(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "new_checkout"
    root.mkdir()
    (root / "pyproject.toml").write_text("[project]\nname='fixture'\n")
    run = root / "data/processed/integrated"
    run.mkdir(parents=True)
    return root, run


def _entry(path: str, payload: bytes) -> dict[str, str]:
    return {"path": path, "sha256": hashlib.sha256(payload).hexdigest()}


def test_historical_absolute_path_resolves_inside_fresh_checkout(tmp_path: Path) -> None:
    root, run = _checkout(tmp_path)
    local = root / "data/metadata/population.json"
    local.parent.mkdir(parents=True)
    local.write_bytes(b"verified")
    old = "/home/another-user/AI-Research-Trends/data/metadata/population.json"
    assert resolve_manifest_input(old, run) == local
    assert resolve_manifest_input("data/metadata/population.json", run) == local


def test_manifest_path_missing_traversal_and_symlink_escape(tmp_path: Path) -> None:
    root, run = _checkout(tmp_path)
    missing = resolve_manifest_input("data/metadata/missing.json", run)
    assert missing == root / "data/metadata/missing.json" and not missing.exists()
    with pytest.raises(ValueError, match="traverses"):
        resolve_manifest_input("data/../.env", run)
    with pytest.raises(ValueError, match="Ambiguous"):
        resolve_manifest_input("/old/data/archive/data/metadata/file.json", run)
    outside = tmp_path / "outside.json"
    outside.write_text("secret")
    link = root / "data/metadata/escape.json"
    link.parent.mkdir(parents=True)
    link.symlink_to(outside)
    with pytest.raises(ValueError, match="escapes"):
        resolve_manifest_input("data/metadata/escape.json", run)


def test_only_retired_interim_may_be_missing_and_hashes_still_enforced(tmp_path: Path) -> None:
    root, run = _checkout(tmp_path)
    retained = root / "data/metadata/source.json"
    retained.parent.mkdir(parents=True)
    retained.write_bytes(b"retained")
    inputs = {
        "source": _entry("data/metadata/source.json", b"retained"),
        "expansion_interim": _entry("data/interim/expansion/records.jsonl", b"historic"),
    }
    assert verify_input_hashes(run, inputs) == ["expansion_interim"]
    retained.write_bytes(b"changed")
    with pytest.raises(ValueError, match="source"):
        verify_input_hashes(run, inputs)
    retained.write_bytes(b"retained")
    interim = root / inputs["expansion_interim"]["path"]
    interim.parent.mkdir(parents=True)
    interim.write_bytes(b"changed")
    with pytest.raises(ValueError, match="expansion_interim"):
        verify_input_hashes(run, inputs)
    interim.write_bytes(b"historic")
    assert verify_input_hashes(run, inputs) == []
    retained.unlink()
    with pytest.raises(ValueError, match="source"):
        verify_input_hashes(run, inputs)
