"""Reader-facing artifact and documentation navigation contracts."""

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import unquote

import pytest

from ai_research_trends.analysis.phase6_artifacts import resolve_historical_path, verify_phase6


ROOT = Path(__file__).resolve().parents[1]
MAP = ROOT / "reports" / "phase6" / "artifact_map.json"
CANONICAL_MARKDOWN = [
    ROOT / "README.md",
    ROOT / "PROJECT_HANDOFF.md",
    *sorted((ROOT / "docs").glob("*.md")),
    *sorted((ROOT / "reports").glob("**/*.md")),
    *sorted((ROOT / "deliverables").glob("**/*.md")),
]


def test_phase6_mapping_preserves_distinct_manifest_identities():
    entries = json.loads(MAP.read_text(encoding="utf-8"))["entries"]
    assert {entry["stage"] for entry in entries} == {
        "pilot_v12", "pilot_reproduction", "topic_metadata",
        "validation_v3", "integrated_rq6",
    }
    for entry in entries:
        manifest = ROOT / entry.get("manifest_path", str(Path(entry["path"]) / "manifest.json"))
        assert manifest.is_file(), entry["path"]
        assert hashlib.sha256(manifest.read_bytes()).hexdigest() == entry["manifest_sha256"]
        assert (ROOT / entry["published_aggregates"]).exists()


def test_pilot_and_reproduction_have_identical_outputs_but_distinct_manifests():
    result = verify_phase6(ROOT)
    assert result["status"] == "PASS"
    assert result["historical_runs"] == 6
    assert result["identical_pilot_outputs_physically_deduplicated"] == 16
    assert result["stages"]["rq6_publication_v2"]["outputs_verified"] == 13
    assert not (ROOT / "data/analysis/phase6a_reproduction_20261028_phase6b").exists()
    pilot = ROOT / "data/analysis/phase6/pilot"
    repeat_manifest = ROOT / "data/analysis/phase6/provenance/pilot_reproduction_manifest.json"
    assert hashlib.sha256((pilot / "manifest.json").read_bytes()).digest() != hashlib.sha256(repeat_manifest.read_bytes()).digest()


def test_historical_phase6_path_resolution():
    old = "data/analysis/phase6a_reproduction_20261028_phase6b/topic_summary.csv"
    target = resolve_historical_path(old, ROOT)
    assert target == ROOT / "data/analysis/phase6/pilot/topic_summary.csv"
    assert resolve_historical_path("data/analysis/phase6a_reproduction_20261028_phase6b/manifest.json", ROOT).name == "pilot_reproduction_manifest.json"
    assert hashlib.sha256(target.read_bytes()).hexdigest() == "239447fc2f925b19dbcc16e516bdc9e5a37016e21d0adae1a57d8bd72fc3d3c6"
    with pytest.raises(ValueError, match="traversal"):
        resolve_historical_path("data/analysis/phase6a_reproduction_20261028_phase6b/../other.csv", ROOT)


def test_phase6_migration_rejects_corrupted_manifest(tmp_path):
    import shutil
    shutil.copytree(ROOT / "data/analysis/phase6", tmp_path / "data/analysis/phase6")
    path = tmp_path / "data/analysis/phase6/provenance/pilot_reproduction_manifest.json"
    path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="Historical manifest mismatch"):
        verify_phase6(tmp_path)


def test_phase6_migration_rejects_changed_output(tmp_path):
    import shutil
    shutil.copytree(ROOT / "data/analysis/phase6", tmp_path / "data/analysis/phase6")
    path = tmp_path / "data/analysis/phase6/pilot/topic_summary.csv"
    path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="Migrated artifact mismatch"):
        verify_phase6(tmp_path)


def test_phase6_published_aggregates_are_at_canonical_paths():
    assert (ROOT / "reports/phase6/pilot/topic_summary.csv").is_file()
    assert (ROOT / "reports/phase6/validation/summary.json").is_file()
    assert not (ROOT / "reports/phase6a").exists()
    assert not (ROOT / "reports/phase6b").exists()


def test_moved_phase6_aggregate_csvs_still_match_original_run_hashes():
    for run_name, public_name in (
        ("phase6/pilot", "pilot"),
        ("phase6/validation", "validation"),
    ):
        run = ROOT / "data/analysis" / run_name
        manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
        declared = {Path(item["path"]).name: item["sha256"]
                    for item in manifest["outputs"].values()}
        published = sorted((ROOT / "reports/phase6" / public_name).glob("*.csv"))
        assert published
        for path in published:
            assert path.name in declared
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            assert digest == declared[path.name]
            assert digest == hashlib.sha256((run / path.name).read_bytes()).hexdigest()
    pilot_manifest = json.loads((ROOT / "data/analysis/phase6/pilot/manifest.json").read_text())
    figure = ROOT / "reports/phase6/figures/topic_support.png"
    declared_figure = next(item for item in pilot_manifest["outputs"].values()
                           if Path(item["path"]).name == figure.name)
    assert hashlib.sha256(figure.read_bytes()).hexdigest() == declared_figure["sha256"]


def test_canonical_markdown_relative_links_resolve():
    pattern = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
    broken = []
    for doc in CANONICAL_MARKDOWN:
        content = doc.read_text(encoding="utf-8")
        for raw in pattern.findall(content):
            destination = raw.strip().split("#", 1)[0]
            if not destination or "://" in destination or destination.startswith("mailto:"):
                continue
            target = doc.parent / unquote(destination).strip("<>")
            if not target.exists():
                broken.append(f"{doc.relative_to(ROOT)} -> {destination}")
    assert not broken, "\n".join(broken)
