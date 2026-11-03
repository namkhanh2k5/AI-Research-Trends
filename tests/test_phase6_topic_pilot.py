"""Synthetic invariants for the silver-label, time-split Phase 6A pilot."""

import numpy as np
import pandas as pd
import pytest
from pathlib import Path

from ai_research_trends.ml.topic_pilot import (
    audit_topics, bootstrap_metrics, clean_text, fit_training_vectorizer,
    open_set_diagnostic, prepare_rows, select_catalogue, split_catalogue, topic_short,
    version_groups,
)


def works_fixture():
    return pd.DataFrame([
        {"work_id":"W1","doi":"https://doi.org/10.1/a","title":"Neural vision method", "abstract":"A vision method", "publication_year":2022,"primary_topic_id":"https://openalex.org/T1","work_type":"article","language":"en"},
        {"work_id":"W2","doi":"10.1/a","title":"Different title here", "abstract":"Other text", "publication_year":2024,"primary_topic_id":"https://openalex.org/T2","work_type":"article","language":"en"},
        {"work_id":"W3","doi":None,"title":"Neural vision method", "abstract":"Another abstract", "publication_year":2025,"primary_topic_id":"https://openalex.org/T1","work_type":"preprint","language":None},
        {"work_id":"W4","doi":None,"title":"Other useful research", "abstract":None, "publication_year":2024,"primary_topic_id":"https://openalex.org/T2","work_type":"review","language":None},
    ])


def test_unicode_text_and_topic_identifier():
    assert clean_text("  Tiếng  Việt\n nghiên cứu  ") == "Tiếng Việt nghiên cứu"
    assert topic_short("https://openalex.org/T10036") == "T10036"
    with pytest.raises(ValueError): topic_short("T10036")


def test_version_grouping_is_label_independent_and_reports_conflict():
    w=works_fixture()
    groups=version_groups(w).set_index("work_id").version_group
    assert groups["W1"]==groups["W2"]==groups["W3"]
    eligible,audit=prepare_rows(w)
    assert eligible.work_id.tolist()==["W1"]
    assert audit.group_has_label_conflict.sum()==3
    assert audit.loc[audit.work_id.eq("W4"),"exclusion_reason"].iat[0]=="missing_title_or_abstract"


def test_missing_label_fails_instead_of_fabricating_a_class():
    w=works_fixture(); w.loc[0,"primary_topic_id"]=None
    with pytest.raises(ValueError,match="Missing primary topic"): prepare_rows(w)


def test_primary_topic_rank_one_consistency():
    w=works_fixture()
    t=pd.DataFrame({"work_id":w.work_id,"topic_id":w.primary_topic_id,"topic_rank":[1]*4,
                    "topic_name":["a"]*4,"topic_score":[.8]*4,"subfield_id":["1702"]*4})
    _,audit=prepare_rows(w)
    assert len(audit_topics(w,t,audit)["topic_summary"])==2
    t.loc[0,"topic_id"]="https://openalex.org/T99"
    with pytest.raises(ValueError,match="disagrees"): audit_topics(w,t,audit)


def test_selection_never_uses_2025_counts():
    summary=pd.DataFrame([{"primary_topic_id":"https://openalex.org/T10036","topic_name":"vision",
                           "primary_subfield":"1707","train_usable":120,"validation_usable":30,
                           "sample_works":9999}])
    review,selected=select_catalogue(summary,{"https://openalex.org/T10036":"description"})
    assert len(selected)==1
    summary.loc[0,"sample_works"]=1
    assert select_catalogue(summary,{})[1]==selected
    summary.loc[0,"validation_usable"]=29
    assert select_catalogue(summary,{})[1]==[]


def test_temporal_split_and_version_isolation():
    w=works_fixture(); eligible,_=prepare_rows(w)
    train,valid,outside,locked=split_catalogue(eligible,["https://openalex.org/T1"])
    assert train.work_id.tolist()==["W1"]
    assert valid.empty and outside.empty and locked.empty
    bad=pd.DataFrame([{"work_id":"A","version_group":"x","publication_year":2023,"primary_topic_id":"T","text":"a"},
                      {"work_id":"B","version_group":"x","publication_year":2024,"primary_topic_id":"T","text":"b"}])
    with pytest.raises(ValueError,match="crosses"): split_catalogue(bad,["T"])
    with pytest.raises(ValueError,match="Empty"): split_catalogue(bad,[])


def test_vectorizer_fit_excludes_validation_vocabulary():
    v,xtr,xv=fit_training_vectorizer(["neural vision method", "neural image method"],
                                     ["unseenvalidationterm neural image"])
    assert xtr.shape[0]==2 and xv.shape[0]==1
    assert "unseenvalidationterm" not in v.vocabulary_


def test_bootstrap_metrics_are_reproducible_and_validate_length():
    y=np.array(["a","b","a","b"])
    pred={"m":np.array(["a","b","b","b"])}
    assert bootstrap_metrics(y,pred,draws=20)==bootstrap_metrics(y,pred,draws=20)
    with pytest.raises(ValueError,match="length"): bootstrap_metrics(y,{"bad":np.array(["a"])})


def test_open_set_diagnostic_counts_unknowns_without_claiming_calibration():
    result=open_set_diagnostic(np.array([.3,.8]),np.array([.2,.6]),.5)
    assert result["incorrectly_rejected_in"]==1
    assert result["confidently_assigned_outside"]==1
    with pytest.raises(ValueError): open_set_diagnostic(np.array([]),np.array([.3]))


def test_published_phase6_figure_is_a_real_linked_png():
    root=Path(__file__).resolve().parents[1]
    figure=root/"reports/figures/phase6/topic_support.png"
    assert figure.stat().st_size>1000
    assert figure.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert "reports/figures/phase6/topic_support.png" in (root/"README.md").read_text()
    assert "figures/phase6/topic_support.png" in (root/"reports/PHASE6A_TOPIC_CLASSIFICATION_FEASIBILITY.md").read_text()


def test_published_audit_tables_are_small_aggregates_without_paper_text():
    root=Path(__file__).resolve().parents[1]
    names={"topic_summary","topic_by_year","topic_by_type","topic_by_language",
           "top3_cooccurrence","scope_review","per_class","confusion_matrix"}
    for name in names:
        table=pd.read_csv(root/f"reports/phase6a/{name}.csv")
        assert len(table)>0
        assert not {"title","abstract","text","work_id"}.intersection(table.columns)
