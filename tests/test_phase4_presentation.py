"""Repository-visible Phase 4 publication and scientific-message checks."""

from __future__ import annotations

import hashlib
import inspect
import json
import re
from pathlib import Path

import matplotlib.image as mpimg
import pandas as pd
import pytest

from ai_research_trends.analysis.figure_publication import publish_figures
from ai_research_trends.analysis.report import publish_verified_report, render_report
from ai_research_trends.analysis.validation import verify_run


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "data/analysis/phase4_stratified_20261019T155909Z_v3"
PUBLISHED = ROOT / "reports/figures/phase4"
PUBLICATION = ROOT / "reports/PHASE4_FIGURE_PUBLICATION.json"
REPORT = ROOT / "reports/PHASE4_ANALYSIS_REPORT.md"
README = ROOT / "README.md"
BRIEF = ROOT / "docs/PHASE4_PRESENTATION_BRIEF.md"
IMAGE_LINK = re.compile(r"!?(?:\[[^\]]*\])\(([^)]+\.png)\)")


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _links(path: Path) -> list[Path]:
    return [path.parent / relative for relative in IMAGE_LINK.findall(path.read_text(encoding="utf-8"))]


def test_published_figure_manifest_and_decodable_images() -> None:
    manifest = json.loads(PUBLICATION.read_text(encoding="utf-8"))
    files = manifest["files"]
    assert manifest["figure_count"] == len(files) == 22
    assert len({item["name"] for item in files}) == 22
    assert {path.name for path in PUBLISHED.glob("*.png")} == {item["name"] for item in files}
    assert manifest["total_published_bytes"] == sum(item["published_bytes"] for item in files)
    for item in files:
        path = PUBLISHED / item["name"]
        assert path.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
        pixels = mpimg.imread(path)
        assert pixels.ndim in (2, 3) and min(pixels.shape[:2]) >= 400
        assert path.stat().st_size == item["published_bytes"] > 1000
        assert _hash(path) == item["published_sha256"] == item["source_sha256"]
        assert item["source_bytes"] == item["published_bytes"]
        assert item["transformation"] == "byte-identical copy"


def test_report_readme_and_brief_figure_links() -> None:
    expected = {PUBLISHED / item["name"] for item in json.loads(PUBLICATION.read_text())["files"]}
    report_links = _links(REPORT)
    readme_links = _links(README)
    brief_links = _links(BRIEF)
    assert len(report_links) == len(expected) == 22
    assert set(report_links) == expected
    assert len(readme_links) == 5
    assert len(set(readme_links)) == 5
    assert len(brief_links) == 8
    assert all(path.is_file() for path in report_links + readme_links + brief_links)
    text = REPORT.read_text(encoding="utf-8")
    assert "*Figure RQ1. Annual publication counts from complete OpenAlex population aggregates" in text
    assert "*Figure RQ2. Descriptive log1p citation distribution for 12,000 sampled works" in text
    assert "*Figure RQ3b. Adjusted six-status OLS associations in the sampled works" in text
    assert "*Figure RQ4. Selected country co-affiliation links among sampled works" in text


def test_rq3_scientific_language_and_model_identity() -> None:
    report = REPORT.read_text(encoding="utf-8")
    brief = BRIEF.read_text(encoding="utf-8")
    readme = README.read_text(encoding="utf-8")
    source = inspect.getsource(render_report)
    for text in (report, brief, source):
        assert "unadjusted_binary" in text
        assert "adjusted_status_year" in text
        assert "geometric mean" in text
    for text in (report, brief):
        assert "2,506" in text and "3,559" in text and "2,678" in text
        assert "not a causal sign reversal" in text
    for text in (report, brief, readme):
        lower = text.lower()
        for unsupported in (
            "open access increases citations", "gold oa causes papers to be cited more",
            "oa improves research quality", "all oa papers outperform closed papers",
            "results prove the open access advantage",
        ):
            assert unsupported not in lower


@pytest.mark.skipif(not (RUN / "manifest.json").is_file(), reason="local Phase 4 run is Git-ignored")
def test_verified_source_and_publication_correspondence(tmp_path: Path) -> None:
    summary = verify_run(RUN)
    assert summary["output_files"] == 64
    manifest = json.loads((RUN / "manifest.json").read_text())
    publication = json.loads(PUBLICATION.read_text())
    assert _hash(RUN / "manifest.json") == publication["source_manifest_sha256"]
    assert {name for name in manifest["outputs"] if name.endswith(".png")} == {
        f"figures/{item['name']}" for item in publication["files"]
    }
    for item in publication["files"]:
        assert _hash(RUN / "figures" / item["name"]) == item["source_sha256"]
    result = publish_figures(RUN, tmp_path / "figures", tmp_path / "publication.json")
    assert result["files"] == publication["files"]
    with pytest.raises(ValueError, match="differs"):
        (tmp_path / "figures" / publication["files"][0]["name"]).write_bytes(b"bad PNG")
        publish_figures(RUN, tmp_path / "figures", tmp_path / "publication.json")


@pytest.mark.skipif(not (RUN / "manifest.json").is_file(), reason="local Phase 4 run is Git-ignored")
def test_report_generator_sync_and_verified_rq3_values(tmp_path: Path) -> None:
    regenerated = tmp_path / "report.md"
    publish_verified_report(RUN, regenerated)
    assert regenerated.read_bytes() == REPORT.read_bytes()
    with pytest.raises(ValueError, match="completed Phase 4"):
        publish_verified_report(RUN, RUN / "PHASE4_ANALYSIS_REPORT.md")
    models = pd.read_csv(RUN / "oa_regression_results.csv")
    report = REPORT.read_text(encoding="utf-8")
    brief = BRIEF.read_text(encoding="utf-8").replace("−", "-")
    for model, term in (("unadjusted_binary", "oa_open"),
                        ("adjusted_status_year", "oa_gold"),
                        ("adjusted_status_year", "oa_green")):
        row = models.loc[(models.model == model) & (models.term == term)].iloc[0]
        coefficient = f"{row.estimate_log1p:+.3f}"
        assert coefficient in report and coefficient in brief
        if model == "adjusted_status_year":
            interval = f"[{row.ci95_low:+.3f}, {row.ci95_high:+.3f}]"
            assert interval in report and interval in brief
    composition = pd.read_csv(RUN / "oa_composition.csv")
    green_preprints = composition.loc[
        (composition.oa_status == "green") & (composition.group_by == "work_type") &
        (composition["group"] == "preprint"), "works"
    ].iloc[0]
    assert f"{int(green_preprints):,}" in report and f"{int(green_preprints):,}" in brief
