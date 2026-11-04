"""Read-only checksum and grain verifier for the isolated venue experiment."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

from ai_research_trends.preprocessing.validate_tables import file_sha256


def verify(directory: Path, figure_dir: Path = Path("reports/figures/venue_experiment")) -> dict:
    manifest = json.loads((directory / "experiment_manifest.json").read_text())
    if manifest.get("status") != "complete_with_quarantined_crossref_mismatch":
        raise ValueError("Experiment manifest does not record its known quality exception")
    code_digest = hashlib.sha256()
    for source in sorted(Path(__file__).parent.glob("*.py")):
        code_digest.update(source.name.encode())
        code_digest.update(source.read_bytes())
    if code_digest.hexdigest() != manifest.get("experiment_code_sha256"):
        raise ValueError("Experiment implementation differs from recorded code hash")
    for label, expected in manifest["input_sha256"].items():
        path = (Path("data/raw/openalex_stratified/stratified_20261019T155909Z/works.jsonl")
                if label == "original_raw" else
                Path("data/raw/openalex_ml_expansion/ml_expansion_20261101T052506Z/works.jsonl"))
        if not path.is_file() or file_sha256(path) != expected:
            raise ValueError(f"Changed source input: {label}")
    for name, evidence in manifest["output_files"].items():
        path = directory / name
        if not path.is_file() or path.stat().st_size != evidence["bytes"] or file_sha256(path) != evidence["sha256"]:
            raise ValueError(f"Changed experiment output: {name}")
    for name, evidence in manifest["published_figures"].items():
        path = figure_dir / name
        if not path.is_file() or path.stat().st_size != evidence["bytes"] or file_sha256(path) != evidence["sha256"]:
            raise ValueError(f"Changed published figure: {name}")
    links = pd.read_parquet(directory / "paper_venue_links.parquet", columns=["work_id", "canonical_venue_id"])
    venues = pd.read_parquet(directory / "canonical_venues.parquet", columns=["canonical_venue_id"])
    if links.work_id.duplicated().any() or venues.canonical_venue_id.duplicated().any():
        raise ValueError("Duplicate canonical paper or venue key")
    if not set(links.canonical_venue_id.dropna()).issubset(set(venues.canonical_venue_id)):
        raise ValueError("Paper link references missing canonical venue")
    predictions = pd.read_parquet(directory / "venue_benchmark_predictions.parquet", columns=["work_id"])
    if predictions.work_id.duplicated().any():
        raise ValueError("Duplicate 2024 development query")
    return {"valid": True, "read_only": True,
            "code_sha256_verified": True,
            "input_hashes_verified": len(manifest["input_sha256"]),
            "output_hashes_verified": len(manifest["output_files"]),
            "figure_hashes_verified": len(manifest["published_figures"]),
            "unique_work_links": len(links), "canonical_venues": len(venues),
            "development_queries": len(predictions),
            "2025_final_test": "SEALED; not inspected by this verifier"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--figure-dir", type=Path, default=Path("reports/figures/venue_experiment"))
    args = parser.parse_args(argv)
    print(json.dumps(verify(args.directory, args.figure_dir), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
