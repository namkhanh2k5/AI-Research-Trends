from pathlib import Path

import pandas as pd
import pytest

from ai_research_trends.web.review import ratings_path, save_rating
from ai_research_trends.ml import final_test_gate


def test_reviewer_isolation_and_atomic_progress(tmp_path):
    blind = pd.DataFrame([{"example_id": "E1", "randomized_topic_options": "T1 — One | T2 — Two"},
                          {"example_id": "E2", "randomized_topic_options": "T2 — Two | T1 — One"}])
    path = save_rating(tmp_path, "reviewer_a", "calibration", blind, "E1", "T1", note="A note")
    assert path == ratings_path(tmp_path, "reviewer_a", "calibration")
    assert not ratings_path(tmp_path, "reviewer_b", "calibration").exists()
    frame = pd.read_csv(path, keep_default_na=False)
    assert frame.best_topic.tolist() == ["T1", ""]
    assert "randomized_topic_options" not in frame.columns
    with pytest.raises(ValueError):
        save_rating(tmp_path, "reviewer_a", "calibration", blind, "E1", "T3")
    assert pd.read_csv(path, keep_default_na=False).best_topic.tolist() == ["T1", ""]


def test_project_level_final_test_registry_blocks_second_run(tmp_path, monkeypatch):
    monkeypatch.setattr(final_test_gate, "verify_human_gate", lambda *args: {"valid": True})
    model = tmp_path / "model"
    model.mkdir()
    integrated = tmp_path / "integrated"
    integrated.mkdir()
    (integrated / "split_manifest.json").write_text('{"outputs":{"test_2025_sealed.parquet":{"sha256":"not-read"}}}')
    (model / "manifest.json").write_text('{"source_paths":{"integrated":"' + str(integrated) + '"}}')
    gate = tmp_path / "gate.json"
    protocol = tmp_path / "protocol.yaml"
    gate.write_text("{}")
    protocol.write_text("{}")
    registry = tmp_path / "registry.json"
    registry.write_text('{"status":"attempt_started"}')
    with pytest.raises(FileExistsError, match="registry"):
        final_test_gate.evaluate_once(gate, model, tmp_path, tmp_path / "SEALED.parquet",
                                      tmp_path, tmp_path, protocol, tmp_path / "new_run", registry)
    assert not (tmp_path / "new_run").exists()
    assert registry.read_text() == '{"status":"attempt_started"}'
