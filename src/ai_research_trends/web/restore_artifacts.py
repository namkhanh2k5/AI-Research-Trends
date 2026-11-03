"""Copy only approved local web/model packages with manifest checksum verification.

This command does not download, rebuild, deserialize, or publish any artifact.
It deliberately refuses to overwrite an existing destination.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tempfile
from pathlib import Path, PurePosixPath


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_package(source: Path, kind: str) -> tuple[dict[str, dict[str, object]], str]:
    source = source.resolve(strict=True)
    if not source.is_dir() or source.is_symlink():
        raise ValueError("Artifact source must be an existing regular directory")
    manifest_path = source / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("status") != "complete" or (kind == "web" and manifest.get("complete") is not True):
        raise ValueError("Artifact manifest is not complete")
    files = manifest.get("outputs" if kind == "web" else "files")
    if not isinstance(files, dict) or not files:
        raise ValueError("Artifact manifest has no file inventory")
    for name, expected in files.items():
        rel = PurePosixPath(name)
        if rel.is_absolute() or ".." in rel.parts or not isinstance(expected, dict):
            raise ValueError(f"Unsafe artifact inventory entry: {name}")
        path = source.joinpath(*rel.parts)
        if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(source):
            raise ValueError(f"Missing or unsafe artifact file: {name}")
        if path.stat().st_size != expected.get("bytes") or sha256(path) != expected.get("sha256"):
            raise ValueError(f"Artifact checksum/size mismatch: {name}")
    return files, sha256(manifest_path)


def restore_package(source: Path, destination: Path, kind: str, *, execute: bool = False) -> dict[str, object]:
    files, manifest_hash = verify_package(source, kind)
    source = source.resolve(strict=True)
    destination = destination.resolve(strict=False)
    if destination == source or destination.exists():
        raise ValueError("Destination already exists; refusing to overwrite")
    if destination == Path("/") or destination.is_relative_to(source):
        raise ValueError("Destination must be a separate, explicit directory")
    result = {"kind": kind, "files": len(files), "manifest_sha256": manifest_hash, "destination": str(destination), "copied": False}
    if not execute:
        return result
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".artifact_restore_", dir=destination.parent) as stage_name:
        stage = Path(stage_name)
        shutil.copy2(source / "manifest.json", stage / "manifest.json")
        for name in files:
            target = stage / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source / name, target)
        verify_package(stage, kind)
        # Move the staged package atomically into an unused versioned destination.
        stage.rename(destination)
    verify_package(destination, kind)
    result["copied"] = True
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=("web", "model"))
    parser.add_argument("--source", type=Path, required=True, help="Authorized local package directory")
    parser.add_argument("--destination", type=Path, required=True, help="New directory; never overwritten")
    parser.add_argument("--execute", action="store_true", help="Copy after source verification (default: dry-run)")
    args = parser.parse_args(argv)
    print(json.dumps(restore_package(args.source, args.destination, args.kind, execute=args.execute), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
