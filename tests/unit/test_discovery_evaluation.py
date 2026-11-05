"""Review preparation and scoring are offline and contain no invented labels."""

import csv
import json

import pytest

from ai_research_trends.web.discovery_evaluation import (
    DEFAULT_QUERIES, FIELDS, load_queries, prepare_package, ranking_metrics, score_package,
)


def test_illustrative_query_set_is_complete_and_label_free():
    queries = load_queries(DEFAULT_QUERIES)
    assert len(queries) == 20
    assert len({query["query_id"] for query in queries}) == 20
    assert all(set(query) == {"query_id", "title", "abstract"} for query in queries)


def test_relevance_math_is_graded_and_uses_fixed_denominator():
    precision, ndcg = ranking_metrics([2, 1, 0, 0, 0])
    assert precision == pytest.approx(0.2)
    assert ndcg == pytest.approx(1.0)
    assert ranking_metrics([]) == (0.0, 0.0)
    assert ranking_metrics([0, 2])[1] < 1.0
    with pytest.raises(ValueError):
        ranking_metrics([3])


def test_prepare_has_blank_labels_and_score_requires_real_entries(tmp_path, monkeypatch):
    index_dir = tmp_path / "index"
    index_dir.mkdir()
    (index_dir / "manifest.json").write_text("{}")

    class TinyDiscovery:
        manifest = {"scope": "historical_sample_plus_application_sync"}
        def __init__(self, path):
            assert path == index_dir
        def search(self, title, abstract, *, top_k):
            assert top_k == 5
            return {"items": [{"work_id": "https://openalex.org/W1", "title": "A relevant-looking title"}]}

    monkeypatch.setattr("ai_research_trends.web.discovery_evaluation.PaperDiscovery", TinyDiscovery)
    output = tmp_path / "review"
    manifest = prepare_package(index_dir, DEFAULT_QUERIES, output)
    assert manifest["status"] == "awaiting_human_judgments"
    assert manifest["query_count"] == manifest["retrieved_pairs"] == 20
    with (output / "judgments.csv").open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert all(row["relevance"] == "" for row in rows)
    with pytest.raises(ValueError, match="missing"):
        score_package(output, annotator_id="reviewer_test")
    # Synthetic grades are used only inside this unit test, never published as
    # actual human judgments or project retrieval results.
    for row in rows:
        row["relevance"] = "2"
    with (output / "judgments.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    scored = score_package(output, annotator_id="reviewer_test")
    assert scored["query_count"] == 20
    assert scored["precision_at_5_grade_2_mean"] == pytest.approx(0.2)
    assert scored["ndcg_at_5_graded_mean"] == pytest.approx(1.0)
    with pytest.raises(FileExistsError):
        score_package(output, annotator_id="reviewer_test")


def test_tampered_retrieval_identity_is_rejected(tmp_path, monkeypatch):
    index_dir = tmp_path / "index"
    index_dir.mkdir()
    (index_dir / "manifest.json").write_text("{}")
    class TinyDiscovery:
        manifest = {"scope": "original_12000_work_detailed_sample_only"}
        def __init__(self, path):
            pass
        def search(self, *args, **kwargs):
            return {"items": [{"work_id": "https://openalex.org/W1", "title": "Paper"}]}
    monkeypatch.setattr("ai_research_trends.web.discovery_evaluation.PaperDiscovery", TinyDiscovery)
    output = tmp_path / "review"
    prepare_package(index_dir, DEFAULT_QUERIES, output)
    sheet = output / "judgments.csv"
    with sheet.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    rows[0]["work_id"] = "https://openalex.org/W999"
    for row in rows:
        row["relevance"] = "2"
    with sheet.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    with pytest.raises(ValueError, match="identities"):
        score_package(output, annotator_id="reviewer_test")


def test_tampered_review_display_text_is_rejected(tmp_path, monkeypatch):
    index_dir = tmp_path / "index"
    index_dir.mkdir()
    (index_dir / "manifest.json").write_text("{}")
    class TinyDiscovery:
        manifest = {"scope": "original_12000_work_detailed_sample_only"}
        def __init__(self, path):
            pass
        def search(self, *args, **kwargs):
            return {"items": [{"work_id": "https://openalex.org/W1", "title": "Paper"}]}
    monkeypatch.setattr("ai_research_trends.web.discovery_evaluation.PaperDiscovery", TinyDiscovery)
    output = tmp_path / "review"
    prepare_package(index_dir, DEFAULT_QUERIES, output)
    sheet = output / "judgments.csv"
    with sheet.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    rows[0]["paper_title"] = "Altered title"
    for row in rows:
        row["relevance"] = "2"
    with sheet.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    with pytest.raises(ValueError, match="result text changed"):
        score_package(output, annotator_id="reviewer_test")
