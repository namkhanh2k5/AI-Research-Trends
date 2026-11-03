"""Read-only checksum and publication verification for a Phase 5 audit run."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from ai_research_trends.ml.literature_audit import REPORT_NAMES
from ai_research_trends.preprocessing.validate_tables import file_sha256


def verify_audit(directory: Path, processed_dir: Path, report_dir: Path,
                 published_figure_dir: Path) -> dict:
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("status") != "complete" or manifest.get("complete") is not True:
        raise ValueError("Phase 5 audit manifest is incomplete")
    source_manifest_path = processed_dir / "manifest.json"
    if file_sha256(source_manifest_path) != manifest["source_phase3_manifest_sha256"]:
        raise ValueError("Source Phase 3 manifest changed")
    source_manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))
    for name, digest in manifest["source_tables_sha256"].items():
        if file_sha256(processed_dir / f"{name}.parquet") != digest:
            raise ValueError(f"Source Parquet changed: {name}")
    for name, item in manifest["outputs"].items():
        path = directory / name
        if file_sha256(path) != item["sha256"] or path.stat().st_size != item["bytes"]:
            raise ValueError(f"Audit output checksum/size mismatch: {name}")
        if name in REPORT_NAMES and file_sha256(report_dir / name) != item["sha256"]:
            raise ValueError(f"Published report differs from audit: {name}")
        if name.startswith("figures/") and file_sha256(
            published_figure_dir / Path(name).name) != item["sha256"]:
            raise ValueError(f"Published figure differs from audit: {name}")
    eligibility = pd.read_csv(directory / "query_eligibility.csv")
    coverage = pd.read_csv(directory / "coverage_queries.csv")
    if not eligibility.work_id.is_unique or len(eligibility) != source_manifest["tables"]["works"]["rows"]:
        raise ValueError("Audit eligibility lost unique sampled-work grain")
    if int(eligibility.eligible.sum()) != manifest["query_eligibility"]:
        raise ValueError("Audit query-eligibility count differs from manifest")
    if coverage.duplicated(["work_id", "minimum_citers"]).any():
        raise ValueError("Coverage query/threshold key duplicated")
    return {"valid": True, "decision": manifest["decision"],
            "source_tables_verified": len(manifest["source_tables_sha256"]),
            "outputs_verified": len(manifest["outputs"]),
            "published_reports_verified": len(REPORT_NAMES),
            "published_figures_verified": sum(name.startswith("figures/") for name in manifest["outputs"])}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only verification of a Phase 5 audit")
    parser.add_argument("audit_dir", type=Path)
    parser.add_argument("--processed-dir", type=Path, required=True)
    parser.add_argument("--report-dir", type=Path, default=Path("reports"))
    parser.add_argument("--published-figure-dir", type=Path,
                        default=Path("reports/figures/phase5"))
    args = parser.parse_args(argv)
    print(json.dumps(verify_audit(args.audit_dir, args.processed_dir, args.report_dir,
                                  args.published_figure_dir), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
