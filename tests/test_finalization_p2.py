"""Focused regressions for finalization integration, review and web contracts."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd
import pytest

from ai_research_trends.analysis.topic_population import collect as collect_topic_population, query_specs, verify as verify_topic_population
from ai_research_trends.analysis.web_queries import ResearchData
from ai_research_trends.ml.human_review_workflow import (human_agreement, validate_blind_sheet,
                                                         validate_ratings)
from ai_research_trends.ml.integrate_topic_data import (build_integration, identity_groups,
                                                        split_for_year, validate_splits)


def _row(key, work_id, year, doi=None, title="A sufficiently long research title", topic="https://openalex.org/T10028"):
    return {"source_record_key":key,"work_id":work_id,"publication_year":year,
            "publication_date":f"{year}-01-01","doi":doi,"title":title,"split":split_for_year(year),
            "text_quality_status":"usable","dataset_origin":"original_analytical_sample",
            "primary_topic_id":topic,"topic_score":0.9,"abstract":"A sufficiently long abstract with many words. "*5}


def test_transitive_version_identity_and_cross_period():
    rows=pd.DataFrame([_row("a","https://openalex.org/W1",2020,"10.1/a"),
                       _row("b","https://openalex.org/W2",2024,"10.1/a"),
                       _row("c","https://openalex.org/W2",2025,None)])
    grouped=identity_groups(rows)
    assert grouped.version_group.nunique()==1


def test_exact_title_identity_and_no_false_name_merge():
    rows=pd.DataFrame([_row("a","https://openalex.org/W1",2020,title="Interesting study of model transfer"),
                       _row("b","https://openalex.org/W2",2024,title=" Interesting  study of MODEL transfer "),
                       _row("c","https://openalex.org/W3",2024,title="Different study of model transfer")])
    assert identity_groups(rows).version_group.nunique()==2


def test_invalid_split_year():
    with pytest.raises(ValueError): split_for_year(2019)


def test_split_validator_rejects_expansion_in_validation():
    audit=pd.DataFrame([{"source_record_key":"a"}])
    reps=pd.DataFrame([{"work_id":"https://openalex.org/W1","doi":None,
                        "title":"A sufficiently long title","version_group":"https://openalex.org/W1",
                        "usable_for_ml":True,"split":"validation","dataset_origin":"targeted_ml_expansion"}])
    with pytest.raises(ValueError): validate_splits(reps,audit)


def test_locked_test_labels_are_masked_outside_sealed_table():
    abstract=" ".join(["scientific"]*35)
    original=pd.DataFrame([
        {"work_id":"https://openalex.org/W1","title":"Alpha study of robust prediction",
         "abstract":abstract,"publication_date":"2020-01-02","publication_year":2020,
         "work_type":"article","language":"en","doi":None,
         "primary_topic_id":"https://openalex.org/T10028","collection_run_id":"run",
         "retrieved_at_utc":"2026-01-01T00:00:00Z"},
        {"work_id":"https://openalex.org/W2","title":"Beta study of robust prediction",
         "abstract":abstract,"publication_date":"2025-01-02","publication_year":2025,
         "work_type":"article","language":"en","doi":None,
         "primary_topic_id":"https://openalex.org/T10036","collection_run_id":"run",
         "retrieved_at_utc":"2026-01-01T00:00:00Z"}])
    topics=pd.DataFrame({"work_id":original.work_id,"topic_id":original.primary_topic_id,
                         "topic_rank":[1,1],"topic_score":[0.9,0.8]})
    tables,checks=build_integration(original,topics,[],{"https://openalex.org/T10028"})
    assert checks["sealed_test_total"]==1
    assert tables["test_2025_sealed"].iloc[0].primary_topic_id=="https://openalex.org/T10036"
    for name in ("source_record_audit","ml_papers","excluded"):
        locked=tables[name].loc[tables[name].split.eq("test")]
        assert locked.primary_topic_id.isna().all()


def test_blind_sheet_rejects_leaked_prediction():
    options=" | ".join([f"T{10000+i} — Topic {i}" for i in range(14)])
    frame=pd.DataFrame([{"example_id":"1","title":"T","abstract":"A",
                         "randomized_topic_options":options,"best_topic":None,
                         "second_plausible_topic":None,"reviewer_note":None,
                         "openalex_prediction":"T10000"}])
    with pytest.raises(ValueError,match="leaks"):validate_blind_sheet(frame,{f"T{10000+i}" for i in range(14)})


def test_blind_sheet_requires_varied_options():
    ids=[f"T{10000+i}" for i in range(14)]
    options=" | ".join(f"{value} — Name" for value in ids)
    frame=pd.DataFrame([{"example_id":str(i),"title":"T","abstract":"A",
                         "randomized_topic_options":options,"best_topic":None,
                         "second_plausible_topic":None,"reviewer_note":None} for i in (1,2)])
    with pytest.raises(ValueError,match="not varied"):validate_blind_sheet(frame,set(ids))


def test_human_ratings_require_complete_independent_responses():
    blind=pd.DataFrame({"example_id":["x","y"]})
    ratings=pd.DataFrame({"example_id":["x"],"best_topic":["T10028"]})
    with pytest.raises(ValueError,match="incomplete"):validate_ratings(ratings,blind,"reviewer_a",{"T10028"})


def test_human_agreement_only_on_supplied_ratings():
    a=pd.DataFrame({"example_id":["x","y"],"best_topic":["T10028","NONE"]})
    b=pd.DataFrame({"example_id":["x","y"],"best_topic":["T10028","UNCLEAR"]})
    result=human_agreement(a,b)
    assert result["examples"]==2 and result["raw_agreement"]==0.5


def test_human_agreement_normalizes_restricted_openalex_key():
    a=pd.DataFrame({"example_id":["x","y"],"best_topic":["T10028","NONE"]})
    b=pd.DataFrame({"example_id":["x","y"],"best_topic":["T10028","UNCLEAR"]})
    key=pd.DataFrame({"example_id":["x","y"],"openalex_primary_topic":
                      ["https://openalex.org/T10028","https://openalex.org/T10036"]})
    result=human_agreement(a,b,key)
    assert result["openalex_label_accepted_by_both"]==1
    assert result["both_disagree_with_openalex"]==1


def test_topic_aggregate_specs_are_fixed_and_primary():
    catalogue={"catalogue_b":[f"T{10000+i}" for i in range(14)]}
    specs=query_specs(catalogue)
    assert len(specs)==14
    for spec in specs:
        filt=spec["params"]["filter"]
        assert "primary_topic.id:" in filt and "is_retracted:false" in filt
        assert "2020-01-01" in filt and "2025-12-31" in filt
        assert spec["params"]["group_by"]=="publication_year"


def test_topic_aggregate_specs_reject_changed_catalogue():
    with pytest.raises(ValueError):query_specs({"catalogue_b":["T10028"]*14})


def test_topic_aggregate_preserves_incomplete_manifest_on_failure(tmp_path: Path):
    catalogue=tmp_path/"catalogue.yaml"
    catalogue.write_text("catalogue_b: ["+", ".join(f"T{10000+i}" for i in range(14))+"]\n")
    class FailingClient:
        api_key="mock-not-a-real-key"
        def request(self,*_): raise RuntimeError("simulated network interruption")
    run=tmp_path/"run"
    with pytest.raises(RuntimeError,match="interruption"):
        collect_topic_population(catalogue,run,client=FailingClient())
    manifest=json.loads((run/"manifest.json").read_text())
    assert manifest["status"]=="incomplete" and manifest["api_requests"]==0
    with pytest.raises(ValueError):verify_topic_population(run)


def test_topic_aggregate_rejects_missing_year_and_keeps_raw(tmp_path: Path):
    catalogue=tmp_path/"catalogue.yaml"
    catalogue.write_text("catalogue_b: ["+", ".join(f"T{10000+i}" for i in range(14))+"]\n")
    payload={"meta":{"count":5},"results":[],
             "group_by":[{"key":"2020","count":5}]}
    class MockResponse:
        content=json.dumps(payload).encode()
        status_code=200
        def json(self): return payload
    class Client:
        api_key="mock-not-a-real-key"
        def request(self,*_): return MockResponse()
    run=tmp_path/"run"
    with pytest.raises(Exception,match="incomplete"):
        collect_topic_population(catalogue,run,client=Client())
    assert (run/"raw/T10000.json").read_bytes()==MockResponse.content
    assert json.loads((run/"manifest.json").read_text())["complete"] is False


def test_web_search_is_literal_and_paginated(tmp_path: Path,monkeypatch):
    monkeypatch.setattr("ai_research_trends.analysis.web_data.verify",lambda _:None)
    data=pd.DataFrame([{"work_id":"https://openalex.org/W1","title":"A [literal] title",
                       "publication_year":2020,"publication_date":"2020-01-01",
                       "work_type":"article","oa_status":"gold","cited_by_count":2,
                       "topic_ids":"https://openalex.org/T10028"},
                      {"work_id":"https://openalex.org/W2","title":"Another title",
                       "publication_year":2021,"publication_date":"2021-01-01",
                       "work_type":"review","oa_status":"closed","cited_by_count":0,
                       "topic_ids":"https://openalex.org/T10036"}])
    data.to_parquet(tmp_path/"paper_index.parquet")
    api=ResearchData(tmp_path)
    found=api.search_papers(keyword="[literal]",topic_id="T10028",page=1,page_size=1)
    assert found["total"]==1 and found["items"][0]["work_id"].endswith("W1")
    assert api.search_papers(page=3,page_size=1)["items"]==[]
    with pytest.raises(ValueError):api.search_papers(page_size=1000)


def test_web_topic_brief_rejects_path_traversal(tmp_path: Path,monkeypatch):
    monkeypatch.setattr("ai_research_trends.analysis.web_data.verify",lambda _:None)
    api=ResearchData(tmp_path)
    with pytest.raises(ValueError):api.get_topic_brief("../../secret")


def test_published_rq6_report_figure_links_resolve():
    root=Path(__file__).resolve().parents[1]
    report=root/"reports/FINALIZATION_P2_RQ6_TOPIC_LABEL_ANALYSIS.md"
    targets=re.findall(r"!\[[^]]*\]\((finalization_p2/figures/[^)]+\.png)\)",report.read_text())
    assert len(targets)==5
    for target in targets:
        image=report.parent/target
        assert image.is_file() and image.stat().st_size>1000
        assert image.read_bytes()[:8]==b"\x89PNG\r\n\x1a\n"
