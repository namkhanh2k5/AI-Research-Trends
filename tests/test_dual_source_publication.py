"""Public RQ7 publication contains only aggregate evidence with valid links."""

from __future__ import annotations

import json
import re
from pathlib import Path

from ai_research_trends.experiments.dual_source.reporting import _table
from ai_research_trends.preprocessing.validate_tables import file_sha256


ROOT = Path(__file__).resolve().parents[1]
FIGURES = ROOT / "reports/figures/dual_source_etl"
REPORTS = [ROOT / "reports/DUAL_SOURCE_ETL_PILOT_FINAL_REPORT.md",
           ROOT / "reports/DUAL_SOURCE_ETL_REVIEW_HANDOFF.md",
           *sorted((ROOT / "reports/experiments").glob("*DUAL_SOURCE*.md"))]


def test_stage_table_uses_paired_denominators():
    stage = {name: {"records": 2, "publisher": n} for name, n in
             (("raw_openalex", 1), ("cleaned_openalex", 1), ("integrated", 2))}
    rendered = _table(stage)
    assert "| publisher | 1 | 1 | 2 | +1 |" in rendered
    assert "Work-level raw/provenance evidence | 2 | 2 | 2" in rendered


def test_published_figure_manifest_hashes_and_png_headers():
    manifest = json.loads((FIGURES / "manifest.json").read_text())
    assert len(manifest["figures"]) == 10
    for name, expected in manifest["figures"].items():
        path = FIGURES / name
        assert path.is_file() and path.stat().st_size == expected["bytes"] > 1000
        assert path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
        assert file_sha256(path) == expected["sha256"]


def test_report_relative_links_resolve():
    for report in REPORTS:
        assert report.is_file()
        for target in re.findall(r"\]\(([^)]+)\)", report.read_text(encoding="utf-8")):
            if target.startswith(("http://", "https://", "#")):
                continue
            assert (report.parent / target).is_file(), f"{report}: {target}"
