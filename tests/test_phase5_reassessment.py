"""Synthetic checks for the bounded historical-pool and enrichment experiment."""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import pytest

from ai_research_trends.ml import metadata_enrichment as enrichment
from ai_research_trends.ml.candidate_pool import historical_citers, pool_audit
from ai_research_trends.ml.metadata_enrichment import (
    parse_candidate_metadata, select_training_candidates,
)
from ai_research_trends.ml.feasibility import candidate_frequency, nested_query_subset
from ai_research_trends.ml.retrieval_baselines import temporal_coverage, temporal_relation
from ai_research_trends.preprocessing.validate_tables import file_sha256


ROOT = Path(__file__).resolve().parents[1]


def _works() -> pd.DataFrame:
    return pd.DataFrame([
        {"work_id": "H1", "publication_year": 2020, "publication_date": "2020-01-15"},
        {"work_id": "H2", "publication_year": 2021, "publication_date": "2021-02-01"},
        {"work_id": "H3", "publication_year": 2022, "publication_date": "2022-05-01"},
        {"work_id": "Q", "publication_year": 2023, "publication_date": "2023-06-01",
         "work_type": "article", "primary_subfield_id": "1702"},
        {"work_id": "L", "publication_year": 2024, "publication_date": "2024-01-01"},
    ])


def _edges() -> pd.DataFrame:
    return pd.DataFrame([("H1", "A"), ("H2", "B"), ("H3", "B"),
                         ("Q", "A"), ("Q", "B"), ("Q", "C"), ("L", "C")],
                        columns=["citing_work_id", "referenced_work_id"])


def test_historical_cutoff_and_all_citers() -> None:
    works, edges = _works(), _edges()
    assert historical_citers(works, edges, evaluation_year=2023) == {"H1", "H2", "H3"}
    assert historical_citers(works, edges, evaluation_year=2023,
                             eligible_ids={"H1", "Q"}) == {"H1"}
    assert historical_citers(works, edges, evaluation_year=2024) == {"H1", "H2", "H3", "Q"}
    with pytest.raises(ValueError):
        historical_citers(works, edges, evaluation_year=2022)
    bad = works.copy()
    bad.loc[0, "publication_date"] = "2023-01-15"
    assert "H1" not in historical_citers(bad, edges, evaluation_year=2023)


def test_pool_uses_distinct_historical_citers_and_never_evaluation_edges() -> None:
    works, edges = _works(), _edges()
    eligibility = works[["work_id", "publication_year", "publication_date",
                         "work_type", "primary_subfield_id"]].copy()
    eligibility["eligible"] = eligibility.work_id.isin({"H1", "Q"})
    original, _, original_frequency = pool_audit(works, edges, eligibility,
                                                   evaluation_year=2023,
                                                   strategy="eligible_historical", threshold=2)
    expanded, _, expanded_frequency = pool_audit(works, edges, eligibility,
                                                   evaluation_year=2023,
                                                   strategy="all_historical", threshold=2)
    assert original["pool_size"] == 0
    assert expanded["pool_size"] == 1
    assert expanded_frequency.loc["B"] == 2
    assert "C" not in expanded_frequency.index  # Q and L are post-cutoff
    assert expanded["id_overlap_edges"] == 1
    assert original_frequency.loc["A"] == 1


def test_frequency_deduplicates_citers_and_subsamples_are_nested() -> None:
    duplicated = pd.DataFrame([("H1", "A"), ("H1", "A"), ("H2", "A"),
                               ("Q", "A")], columns=["citing_work_id", "referenced_work_id"])
    assert candidate_frequency(duplicated, {"H1", "H2"}).loc["A"] == 2
    assert candidate_frequency(duplicated, {"H1"}).loc["A"] == 1
    history = ["H3", "H1", "H2", "H4"]
    assert nested_query_subset(history, .25, 42).issubset(
        nested_query_subset(reversed(history), .5, 42))


def test_candidate_selection_is_training_only_and_deterministic() -> None:
    ids = [f"https://openalex.org/W{i}" for i in range(1, 9)]
    frequency = pd.Series([3, 2, 2, 1, 1, 1, 1, 1], index=ids)
    first = select_training_candidates(frequency, maximum=5, tail_fraction=.2, seed=7)
    second = select_training_candidates(frequency.sample(frac=1, random_state=9),
                                        maximum=5, tail_fraction=.2, seed=7)
    pd.testing.assert_frame_equal(first, second)
    assert len(first) == 5 and first.work_id.is_unique
    assert first.selection_group.eq("frequency_one_audit").sum() == 1
    with pytest.raises(ValueError):
        select_training_candidates(frequency, maximum=3001)
    with pytest.raises(ValueError):
        select_training_candidates(pd.concat([frequency, frequency.iloc[[0]]]))


def test_metadata_identity_nulls_and_temporal_boundary() -> None:
    parsed = parse_candidate_metadata({"id": "https://openalex.org/W42", "title": None,
                                       "abstract_inverted_index": None,
                                       "publication_date": None, "open_access": None},
                                      "https://openalex.org/W42")
    assert parsed["title"] is None and parsed["publication_date"] is None
    with pytest.raises(ValueError, match="different"):
        parse_candidate_metadata({"id": "W43"}, "https://openalex.org/W42")
    with pytest.raises(ValueError, match="Malformed"):
        parse_candidate_metadata({"id": "W42", "publication_date": "invalid"},
                                 "https://openalex.org/W42")
    assert temporal_relation(None, "2023-06-01") == "unknown"
    assert temporal_relation("2023-05-31", "2023-06-01") == "same_year_nonfuture"
    assert temporal_relation("2023-06-02", "2023-06-01") == "future"
    assert temporal_relation("2022-12-31", "2023-06-01") == "earlier_year"


def test_temporal_coverage_separates_unknown_future_and_same_year() -> None:
    query = _works().loc[lambda frame: frame.work_id.eq("Q")]
    refs = pd.DataFrame([("Q", "A"), ("Q", "B"), ("Q", "C"), ("Q", "D")],
                        columns=["citing_work_id", "referenced_work_id"])
    meta = pd.DataFrame([("A", "2022-01-01"), ("B", "2023-05-01"),
                         ("C", "2023-07-01"), ("D", None)],
                        columns=["work_id", "publication_date"])
    _, result = temporal_coverage(query, refs, meta)
    assert result["known_earlier_year_edges"] == 1
    assert result["same_year_nonfuture_edges"] == 1
    assert result["known_future_edges"] == 1
    assert result["unknown_date_overlap_edges"] == 1
    assert result["conservative_valid_overlap_edges"] == 1
    assert result["exact_date_valid_overlap_edges"] == 2


def test_enrichment_preserves_raw_bytes_and_records_unavailable_ids(tmp_path, monkeypatch) -> None:
    processed = tmp_path / "processed"
    processed.mkdir()
    (processed / "manifest.json").write_text("{}")
    works = pd.DataFrame([{"work_id": "H", "publication_year": 2020,
                           "publication_date": "2020-01-01"}])
    refs = pd.DataFrame([("H", "https://openalex.org/W1"),
                         ("H", "https://openalex.org/W2")],
                        columns=["citing_work_id", "referenced_work_id"])
    monkeypatch.setattr(enrichment, "load_verified_tables",
                        lambda *_: ({"works": works, "references": refs}, {}, {}))

    class Response:
        def __init__(self, status: int, raw: bytes) -> None:
            self.status_code = status
            self.content = raw

        def json(self):
            return {"id": "https://openalex.org/W1", "title": "First",
                    "publication_date": "2019-01-01"}

    class Client:
        api_key = "mock-key"

        def request(self, path, *, allow_statuses):
            assert allow_statuses == frozenset({404})
            return Response(200, b'{"id":"https://openalex.org/W1","title":"First","publication_date":"2019-01-01"}') if path.endswith("W1") else Response(404, b"missing")

    out = tmp_path / "enriched"
    result = enrichment.run_enrichment(processed_dir=processed, plan=tmp_path / "p",
                                       population=tmp_path / "n", config=tmp_path / "c",
                                       output_dir=out, maximum=2, client=Client())
    assert result["complete"] and result["status"] == "complete_with_unavailable"
    assert result["retrieved"] == 1 and len(result["unavailable_ids"]) == 1
    assert (out / "raw_responses/W1.json").read_bytes().startswith(b'{"id":')
    assert (out / "raw_responses/W2.http404").read_bytes() == b"missing"
    assert (out / "manifest.json").exists()
    assert enrichment.verify_enrichment(out)["raw_responses_verified"] == 2
    (out / "raw_responses/W2.http404").write_bytes(b"tampered")
    with pytest.raises(ValueError, match="checksum"):
        enrichment.verify_enrichment(out)
    with pytest.raises(FileExistsError):
        enrichment.run_enrichment(processed_dir=processed, plan=tmp_path / "p",
                                   population=tmp_path / "n", config=tmp_path / "c",
                                   output_dir=out, maximum=2, client=Client())


def test_enrichment_failure_keeps_incomplete_manifest(tmp_path, monkeypatch) -> None:
    processed = tmp_path / "processed"
    processed.mkdir()
    (processed / "manifest.json").write_text("{}")
    works = pd.DataFrame([{"work_id": "H", "publication_year": 2020,
                           "publication_date": "2020-01-01"}])
    refs = pd.DataFrame([("H", "https://openalex.org/W1")],
                        columns=["citing_work_id", "referenced_work_id"])
    monkeypatch.setattr(enrichment, "load_verified_tables",
                        lambda *_: ({"works": works, "references": refs}, {}, {}))

    class FailedClient:
        api_key = "mock-key"

        def request(self, path, *, allow_statuses):
            raise ConnectionError("simulated API failure")

    out = tmp_path / "enriched"
    result = enrichment.run_enrichment(processed_dir=processed, plan=tmp_path / "p",
                                       population=tmp_path / "n", config=tmp_path / "c",
                                       output_dir=out, maximum=1, client=FailedClient())
    assert not result["complete"] and result["status"] == "incomplete"
    assert result["api_failures"][0]["error_type"] == "ConnectionError"
    assert (out / "manifest.json").exists()


def test_reassessment_report_figure_is_published_and_source_verified() -> None:
    report = ROOT / "reports/PHASE5_COVERAGE_REASSESSMENT.md"
    links = re.findall(r"!\[[^]]*\]\((figures/phase5/[^)]+\.png)\)", report.read_text())
    assert links == ["figures/phase5/pool_saturation_2023.png"]
    published = report.parent / links[0]
    assert published.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    local = ROOT / "data/analysis/phase5_reassessment_20261028_v1/pool_saturation_2023.png"
    if local.is_file():
        assert file_sha256(published) == file_sha256(local)


def test_phase5_final_report_links_resolve() -> None:
    for name in ("PHASE5_COVERAGE_REASSESSMENT.md",
                 "PHASE5_RETRIEVAL_DIAGNOSTIC.md",
                 "PHASE5_FINAL_DECISION.md"):
        report = ROOT / "reports" / name
        links = re.findall(r"!?(?:\[[^]]*\])\(([^)]+)\)", report.read_text())
        for target in links:
            if target.startswith(("https://", "http://", "#")):
                continue
            assert (report.parent / target).exists(), f"Broken Phase 5 link: {name} -> {target}"
