"""Relocated active products and deduplicated historical summaries retain bytes."""

import json
from pathlib import Path

from ai_research_trends.analysis.web_data import verify as verify_web
from ai_research_trends.artifact_paths import application_artifacts
from ai_research_trends.preprocessing.validate_tables import file_sha256

ROOT = Path(__file__).resolve().parents[2]


def test_web_and_model_aliases_are_verified_without_duplicate_payloads() -> None:
    paths = application_artifacts()
    web = paths["web_data"]
    model = paths["model_bundle"]
    assert verify_web(web)["outputs_verified"] == 22
    assert (ROOT / "data/analysis/finalization_p2_web_data_20261101_v3").resolve() == web
    assert (ROOT / "models/finalization_p3/topic_placement_v2").resolve() == model
    model_manifest = json.loads((model / "manifest.json").read_text())
    assert file_sha256(web / "manifest.json") == model_manifest["web_manifest_sha256"]
    for name, entry in model_manifest["files"].items():
        assert file_sha256(model / name) == entry["sha256"]


def test_historical_duplicates_are_byte_identical_canonical_links() -> None:
    published = ROOT / "data/analysis/finalization_p1_published_v1"
    manifest = json.loads((published / "reproducibility_manifest.json").read_text())
    aliases = {
        "data_gap.csv": "finalization_p1_gap_20261101_v1/data_gap.csv",
        "by_year.csv": "finalization_p1_quality_20261101_v2/by_year.csv",
        "by_type.csv": "finalization_p1_quality_20261101_v2/by_type.csv",
        "by_language.csv": "finalization_p1_quality_20261101_v2/by_language.csv",
        "topic_support.csv": "finalization_p1_quality_20261101_v2/topic_support.csv",
        "label_drift_summary.json": "finalization_p1_label_drift_20261101_v1/summary.json",
        "label_drift_transitions.csv": "finalization_p1_label_drift_20261101_v1/transitions.csv",
    }
    for name, canonical in aliases.items():
        alias = published / name
        target = ROOT / "data/analysis" / canonical
        assert alias.is_symlink() and alias.resolve() == target
        assert file_sha256(alias) == manifest["files"][name]["sha256"]
    phase5 = ROOT / "data/analysis"
    alias = phase5 / "phase5_reassessment_20261028_v2/query_eligibility.csv"
    canonical = phase5 / "phase5_literature_pilot_20261028_v4/query_eligibility.csv"
    assert alias.is_symlink() and alias.resolve() == canonical
    assert file_sha256(alias) == file_sha256(canonical)


def test_historical_configuration_aliases_preserve_original_bytes() -> None:
    names = (
        "phase6_topic_catalogue.yaml",
        "finalization_phase1_collection.yaml",
        "finalization_phase2_integration.yaml",
    )
    for name in names:
        alias = ROOT / "config" / name
        canonical = ROOT / "config/historical" / name
        assert alias.is_symlink() and alias.resolve() == canonical
        assert file_sha256(alias) == file_sha256(canonical)
