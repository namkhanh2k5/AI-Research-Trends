"""The application has one authoritative, safe set of artifact locations."""

from pathlib import Path

import pytest

from ai_research_trends.artifact_paths import application_artifacts


def test_active_artifacts_resolve_to_functional_locations() -> None:
    paths = application_artifacts()
    assert paths["web_data"].parts[-3:] == ("artifacts", "web", "topic_explorer")
    assert paths["model_bundle"].parts[-2:] == ("models", "topic_placement_v2")
    assert paths["paper_discovery"].parts[-3:] == ("artifacts", "web", "paper_discovery")


@pytest.mark.parametrize("bad", ["/tmp/web", "data/../.env", "models/wrong", "data/escape", "."])
def test_application_paths_reject_invalid_or_escaping_values(tmp_path: Path, bad: str) -> None:
    config = tmp_path / "config" / "application.yaml"
    config.parent.mkdir()
    config.write_text(
        "schema_version: 1\nartifacts:\n"
        f"  web_data: {bad}\n"
        "  model_bundle: models/frozen\n"
        "  paper_discovery: data/artifacts/web/paper_discovery\n",
        encoding="utf-8",
    )
    if bad == "data/escape":
        (tmp_path / "data").mkdir()
        (tmp_path / "data" / "escape").symlink_to(tmp_path.parent)
    with pytest.raises(ValueError, match="Unsafe|escapes"):
        application_artifacts(config)
