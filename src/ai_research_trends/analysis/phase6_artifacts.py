"""Resolve migrated Phase 6 artifacts and verify immutable historical evidence.

The source manifests are never rewritten. This checks their original SHA-256
and each declared output against a single canonical physical artifact path.
It does not claim any historical experiment was rerun.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MAP = Path("data/analysis/phase6/manifest.json")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _stages(root: Path) -> list[dict]:
    data = json.loads((root / MAP).read_text(encoding="utf-8"))
    if data.get("schema_version") != 1 or len(data.get("stages", [])) != 6:
        raise ValueError("Unsupported or incomplete Phase 6 migration manifest")
    stages = data["stages"]
    if len({item["identity"] for item in stages}) != len(stages):
        raise ValueError("Duplicate Phase 6 identity")
    return stages


def resolve_historical_path(path: str | Path, root: Path = ROOT) -> Path:
    """Resolve an old Phase 6 path only through the explicit migration map.

    Callers must still verify the expected original SHA-256; path resolution
    alone is not evidence that an artifact is unchanged.
    """
    value = Path(path)
    if ".." in value.parts:
        raise ValueError(f"Historical path traversal: {path}")
    if value.is_absolute():
        return value
    direct = root / value
    if direct.exists():
        return direct
    for stage in _stages(root):
        old = Path(stage["original_dir"])
        if value == old / "manifest.json":
            return root / stage["manifest"]
        if value.parent == old:
            return root / stage["artifact_dir"] / value.name
        if old in value.parents:
            remainder = value.relative_to(old)
            return root / stage["artifact_dir"] / remainder
    return direct


def verify_phase6(root: Path = ROOT) -> dict:
    stages = _stages(root)
    checked = {}
    pilot_hashes: dict[str, str] | None = None
    for stage in stages:
        manifest_path = root / stage["manifest"]
        if not manifest_path.is_file() or file_sha256(manifest_path) != stage["manifest_sha256"]:
            raise ValueError(f"Historical manifest mismatch: {stage['identity']}")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        identity = stage["identity"]
        expected: dict[str, dict] = {}
        if identity == "topic_metadata":
            expected["topics.csv"] = {"sha256": manifest["topics_csv_sha256"]}
            expected.update({Path(item["path"]).name: item for item in manifest["responses"]})
        elif identity == "rq6_publication_v2":
            expected = manifest["files"]
        else:
            for name, entry in manifest["outputs"].items():
                relative = Path(entry.get("path", name))
                expected[str(relative.relative_to(stage["original_dir"])) if relative.is_relative_to(stage["original_dir"]) else str(relative)] = entry
        if len(expected) != stage["artifact_count"]:
            raise ValueError(f"Artifact-count mismatch: {identity}")
        actual_hashes = {}
        for relative, entry in expected.items():
            if Path(relative).is_absolute() or ".." in Path(relative).parts:
                raise ValueError(f"Unsafe historical artifact path: {relative}")
            target = root / stage["artifact_dir"] / relative
            if not target.is_file() or file_sha256(target) != entry["sha256"]:
                raise ValueError(f"Migrated artifact mismatch: {identity}/{relative}")
            if "bytes" in entry and target.stat().st_size != entry["bytes"]:
                raise ValueError(f"Migrated artifact size mismatch: {identity}/{relative}")
            actual_hashes[relative] = entry["sha256"]
        if identity == "pilot_v12":
            pilot_hashes = actual_hashes
        if identity == "pilot_reproduction" and actual_hashes != pilot_hashes:
            raise ValueError("Reproduction differs from canonical pilot outputs")
        checked[identity] = {"manifest_sha256": stage["manifest_sha256"], "outputs_verified": len(expected)}
    return {"status": "PASS", "historical_runs": len(checked), "identical_pilot_outputs_physically_deduplicated": len(pilot_hashes or {}), "stages": checked}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    print(json.dumps(verify_phase6(args.root), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
