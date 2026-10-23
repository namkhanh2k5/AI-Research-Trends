"""Publish byte-identical PNG copies from a verified immutable Phase 4 run."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import tempfile
from pathlib import Path

import pandas as pd

from ai_research_trends.analysis.validation import verify_run
from ai_research_trends.preprocessing.validate_tables import file_sha256


def publish_figures(analysis_dir: Path, published_dir: Path, manifest_path: Path) -> dict:
    """Verify all scientific outputs, then publish only original PNG bytes.

    Existing published files are accepted only when their checksum matches the
    verified source. No completed analytical output is modified.
    """
    verify_run(analysis_dir)
    source_manifest = json.loads((analysis_dir / "manifest.json").read_text(encoding="utf-8"))
    inventory = pd.read_csv(analysis_dir / "figure_inventory.csv")
    expected = {f"figures/{name}.png" for name in inventory["figure"]}
    actual = {name for name in source_manifest["outputs"] if name.endswith(".png")}
    if len(expected) != 22 or expected != actual:
        raise ValueError("Figure inventory and verified PNG outputs differ")
    if published_dir.resolve() == (analysis_dir / "figures").resolve():
        raise ValueError("Published directory must not be the immutable source directory")
    published_dir.mkdir(parents=True, exist_ok=True)
    files = []
    for name in sorted(expected):
        source = analysis_dir / name
        destination = published_dir / Path(name).name
        source_hash = source_manifest["outputs"][name]["sha256"]
        if destination.exists():
            if file_sha256(destination) != source_hash:
                raise ValueError(f"Published figure differs from verified original: {destination}")
        else:
            fd, temporary_name = tempfile.mkstemp(prefix=".phase4_png_", dir=published_dir)
            try:
                with os.fdopen(fd, "wb") as output, source.open("rb") as input_file:
                    shutil.copyfileobj(input_file, output)
                    output.flush()
                    os.fsync(output.fileno())
                if file_sha256(Path(temporary_name)) != source_hash:
                    raise ValueError(f"Copied PNG checksum differs from source: {name}")
                os.replace(temporary_name, destination)
            finally:
                if os.path.exists(temporary_name):
                    os.unlink(temporary_name)
        files.append({"name": destination.name, "source_sha256": source_hash,
                      "published_sha256": file_sha256(destination),
                      "source_bytes": source.stat().st_size,
                      "published_bytes": destination.stat().st_size,
                      "transformation": "byte-identical copy"})
    publication = {
        "schema_version": 1,
        "source_run": analysis_dir.name,
        "source_manifest_sha256": file_sha256(analysis_dir / "manifest.json"),
        "published_directory": published_dir.as_posix(),
        "figure_count": len(files),
        "total_published_bytes": sum(item["published_bytes"] for item in files),
        "files": files,
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(publication, indent=2, ensure_ascii=False) + "\n"
    if manifest_path.exists():
        if manifest_path.read_text(encoding="utf-8") != payload:
            raise ValueError(f"Existing publication manifest differs: {manifest_path}")
    else:
        fd, temporary_name = tempfile.mkstemp(prefix=".phase4_publication_", dir=manifest_path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as output:
                output.write(payload)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary_name, manifest_path)
        finally:
            if os.path.exists(temporary_name):
                os.unlink(temporary_name)
    return publication


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Publish verified Phase 4 PNGs without altering the run")
    parser.add_argument("analysis_dir", type=Path)
    parser.add_argument("--published-dir", type=Path, default=Path("reports/figures/phase4"))
    parser.add_argument("--manifest", type=Path, default=Path("reports/PHASE4_FIGURE_PUBLICATION.json"))
    args = parser.parse_args(argv)
    result = publish_figures(args.analysis_dir, args.published_dir, args.manifest)
    print(json.dumps({"figure_count": result["figure_count"],
                      "total_published_bytes": result["total_published_bytes"],
                      "manifest": str(args.manifest)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
