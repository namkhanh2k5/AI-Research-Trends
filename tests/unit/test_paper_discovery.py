"""Offline retrieval tests; no human relevance labels are inferred."""

import json
from pathlib import Path

import pandas as pd
import pytest

from ai_research_trends.preprocessing.validate_tables import file_sha256
from ai_research_trends.web.paper_discovery import PaperDiscovery, build_index, prepare_papers, verify_index
from ai_research_trends.web.service import suggestion_message


def _works() -> pd.DataFrame:
    text = [
        ("W1", "Neural machine translation with attention models", "We study neural machine translation with attention and multilingual language modelling for scientific communication.", "T10028", 2020, "article", "10.1/a"),
        ("W2", "Neural language translation with attention models", "We investigate neural language translation systems with attention and multilingual data for scientific communication.", "T10028", 2021, "article", "10.1/b"),
        ("W3", "Satellite image segmentation for forest monitoring", "We study satellite image segmentation for remote sensing and forest monitoring with convolutional vision networks.", "T10100", 2022, "review", "10.1/c"),
        ("W4", "Robotic reinforcement learning in simulated environments", None, "T10100", 2023, "preprint", None),
        ("W5", "Neural machine translation with attention models", "We study neural machine translation with attention and multilingual language modelling for scientific communication.", "T10028", 2020, "article", "10.1/e"),
        ("W6", None, None, "T10028", 2020, "article", None),
    ]
    return pd.DataFrame([{
        "work_id": f"https://openalex.org/{wid}", "title": title, "abstract": abstract,
        "publication_date": f"{year}-02-01", "publication_year": year,
        "work_type": kind, "doi": doi,
        "primary_topic_id": f"https://openalex.org/{topic}", "cited_by_count": 0,
    } for wid, title, abstract, topic, year, kind, doi in text])


@pytest.fixture
def tiny_index(tmp_path: Path, monkeypatch) -> Path:
    works = _works()
    source = tmp_path / "source" / "works.parquet"
    source.parent.mkdir()
    works.to_parquet(source, index=False)
    (source.parent / "manifest.json").write_text(json.dumps({
        "status": "complete", "tables": {"works": {"rows": len(works), "sha256": file_sha256(source)}}
    }))
    web = tmp_path / "web"
    web.mkdir()
    (web / "manifest.json").write_text("{}")
    monkeypatch.setattr("ai_research_trends.web.paper_discovery.verify_web_data", lambda path: None)
    index = tmp_path / "index"
    build_index(source, web, index, min_df=1)
    return index


def test_preparation_preserves_missingness_and_deduplicates_exact_text():
    papers, stats = prepare_papers(_works())
    assert stats["source_works"] == 6
    assert stats["excluded_insufficient_title"] == 1
    assert stats["excluded_exact_text_duplicates"] == 1
    assert stats["indexed_works"] == 4
    assert papers.loc[papers.work_id.eq("https://openalex.org/W4"), "text_status"].item() == "title_only"
    assert papers.loc[papers.work_id.eq("https://openalex.org/W4"), "abstract"].item() == ""


def test_preparation_rejects_bad_ids_and_duplicate_ids():
    frame = _works()
    frame.loc[0, "work_id"] = "W1"
    with pytest.raises(ValueError, match="Noncanonical"):
        prepare_papers(frame)
    frame = _works()
    frame.loc[1, "work_id"] = frame.loc[0, "work_id"]
    with pytest.raises(ValueError, match="Duplicate"):
        prepare_papers(frame)


def test_identical_query_first_and_self_exclusion(tiny_index):
    index = PaperDiscovery(tiny_index)
    row = _works().iloc[0]
    result = index.search(row.title, row.abstract, top_k=5)
    assert result["items"][0]["work_id"] == row.work_id
    assert result["items"][0]["similarity"] > 0.99
    removed = index.search(row.title, row.abstract, top_k=5, exclude_work_id=row.work_id)
    assert all(x["work_id"] != row.work_id for x in removed["items"])
    assert removed["items"][0]["work_id"] == "https://openalex.org/W2"


def test_filters_ranking_and_empty_matches(tiny_index):
    index = PaperDiscovery(tiny_index)
    query = "Neural machine translation with attention models"
    first = index.search(query, top_k=2)
    assert first["items"] == index.search(query, top_k=2)["items"]
    assert [x["similarity"] for x in first["items"]] == sorted(
        [x["similarity"] for x in first["items"]], reverse=True)
    filtered = index.search(query, top_k=10, year_min=2021, year_max=2021,
                            topic_id="T10028", work_type="article")
    assert [x["work_id"] for x in filtered["items"]] == ["https://openalex.org/W2"]
    assert index.search(query, year_min=2023, work_type="review")["items"] == []
    assert index.search("Quasar supernova astronomy observation galaxy")["items"] == []


@pytest.mark.parametrize("kwargs", [{"top_k": 0}, {"top_k": 21}, {"top_k": True},
                                    {"year_min": 2025, "year_max": 2020},
                                    {"topic_id": "../bad"}, {"work_type": "book"},
                                    {"exclude_work_id": "bad"}])
def test_bad_search_parameters(tiny_index, kwargs):
    with pytest.raises(ValueError):
        PaperDiscovery(tiny_index).search("Neural machine translation with attention models", **kwargs)


@pytest.mark.parametrize("title,abstract", [("", ""), ("short", ""),
    ("Neural machine translation with attention models", "too short"),
    ("Neural machine translation with attention models\x00", "")])
def test_invalid_query_text(tiny_index, title, abstract):
    with pytest.raises(ValueError):
        PaperDiscovery(tiny_index).search(title, abstract)


def test_manifest_tampering_and_missing_files_fail(tiny_index):
    manifest = json.loads((tiny_index / "manifest.json").read_text())
    (tiny_index / "matrix.npz").write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="checksum"):
        verify_index(tiny_index)
    manifest["files"].pop("vectorizer.json")
    (tiny_index / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="Missing"):
        verify_index(tiny_index)


def test_missing_manifest_fails(tiny_index):
    (tiny_index / "manifest.json").unlink()
    with pytest.raises(FileNotFoundError):
        PaperDiscovery(tiny_index)


def test_source_hash_mismatch_fails_read_only_verification(tmp_path, tiny_index):
    works = tmp_path / "source" / "works.parquet"
    assert verify_index(tiny_index, works_path=works)["status"] == "complete"
    works.write_bytes(b"changed source")
    with pytest.raises(ValueError, match="Source works changed"):
        verify_index(tiny_index, works_path=works)


def test_build_is_immutable_and_deterministic(tmp_path, tiny_index, monkeypatch):
    source = tmp_path / "source" / "works.parquet"
    web = tmp_path / "web"
    with pytest.raises(FileExistsError):
        build_index(source, web, tiny_index, min_df=1)
    monkeypatch.setattr("ai_research_trends.web.paper_discovery.verify_web_data", lambda path: None)
    second = tmp_path / "second"
    build_index(source, web, second, min_df=1)
    a, b = verify_index(tiny_index), verify_index(second)
    assert a["files"] == b["files"]
    assert a["matrix_shape"] == b["matrix_shape"]


@pytest.mark.parametrize("status", ["confident_suggestion", "needs_user_confirmation", "no_confident_match"])
def test_user_facing_abstention_states(status):
    text = suggestion_message(status).lower()
    assert "automatic" not in text
    assert "probability" not in text
    if status == "no_confident_match":
        assert "fourteen supported topics" in text
    with pytest.raises(ValueError):
        suggestion_message("invalid")
