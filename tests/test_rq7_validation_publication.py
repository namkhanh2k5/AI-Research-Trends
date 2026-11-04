"""Aggregate publication must resolve links and exclude private record-level data."""

from __future__ import annotations

import json
import re
from pathlib import Path

from ai_research_trends.preprocessing.validate_tables import file_sha256


ROOT = Path(__file__).resolve().parents[1]
FIGURES = ROOT / "reports/figures/rq7_validation"
REPORTS = [ROOT / "reports/RQ7_1_INDEPENDENT_METADATA_VALIDATION_REPORT.md",
           ROOT / "reports/RQ7_1_REVIEW_HANDOFF.md",
           *[ROOT / "reports/experiments" / name for name in (
               "RQ7_METADATA_VALIDATION_SAMPLING.md",
               "RQ7_PUBLISHER_CORRECTNESS_AUDIT.md",
               "RQ7_LICENSE_SEMANTICS_AUDIT.md",
               "RQ7_CONFLICT_RECLASSIFICATION.md",
               "RQ7_CROSSREF_404_AUDIT.md",
               "RQ7_VALIDATED_DATA_QUALITY.md")],
           ROOT / "reports/experiments/RQ7_12000_WORK_SCALE_UP_DECISION.md"]


def test_rq7_figure_manifest_and_png_hashes():
    manifest = json.loads((FIGURES / "manifest.json").read_text())
    assert len(manifest["figures"]) == 7
    for name, meta in manifest["figures"].items():
        path = FIGURES / name
        assert path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
        assert path.stat().st_size == meta["bytes"] > 1000
        assert file_sha256(path) == meta["sha256"]


def test_rq7_reports_have_resolving_links_and_no_record_level_identifiers():
    assert len(set(REPORTS)) == 9
    for report in REPORTS:
        assert report.is_file(), report
        body = report.read_text(encoding="utf-8")
        assert not re.search(r"https://openalex\.org/W\d+", body)
        assert not re.search(r"10\.\d{4,9}/[A-Za-z0-9]", body)
        for target in re.findall(r"\]\(([^)]+)\)", body):
            if target.startswith(("http://", "https://", "#")):
                continue
            assert (report.parent / target).is_file(), f"{report}: {target}"


def test_rq7_language_keeps_human_gate_pending():
    main = (ROOT / "reports/RQ7_1_INDEPENDENT_METADATA_VALIDATION_REPORT.md").read_text()
    assert "PENDING_HUMAN_REVIEW" in main
    assert "NO-GO for immediate full 12,000-work" in main
    assert "not population-representative" in main
