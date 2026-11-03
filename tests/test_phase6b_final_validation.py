"""Offline synthetic checks for the Phase 6B decision-critical invariants."""

import hashlib
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pytest

from ai_research_trends.ml.topic_annotation import analyze_ratings
from ai_research_trends.ml.topic_brief import load_verified_brief_run, place_research_draft
from ai_research_trends.ml.topic_catalogue import parse_verified_topic
from ai_research_trends.ml.validate_topic_run import verify_run
from ai_research_trends.ml.topic_final_validation import (
    exact_and_near_duplicates, load_catalogue, make_pipeline, open_set_metrics,
    paired_bootstrap, scope_table, select_rejection_threshold, stable_group_split,
)


def test_official_topic_response_identity_and_description():
    payload={"id":"https://openalex.org/T42","display_name":"Vision methods",
             "description":"Verified description","subfield":{"id":"https://openalex.org/subfields/1707"}}
    result=parse_verified_topic(payload,"T42")
    assert result["subfield_id"]=="1707"
    with pytest.raises(ValueError,match="mismatch"): parse_verified_topic(payload,"T43")
    payload["description"]=None
    with pytest.raises(ValueError,match="no official description"): parse_verified_topic(payload,"T42")


def test_frozen_catalogue_metadata_hash_and_scope():
    spec,metadata=load_catalogue(Path("config/phase6b_catalogue.yaml"))
    assert len(spec["catalogue_a"])==5 and len(spec["catalogue_b"])==14
    assert len(metadata)==20
    assert all(spec["scope_review"][tid]["status"]=="in" for tid in spec["catalogue_b"])


def test_scope_support_ignores_2025():
    meta=pd.DataFrame([{"topic_id":"https://openalex.org/T1","short_id":"T1","name":"AI method",
                        "description":"official","subfield_id":"1702","source_url":"api","updated_date":None}])
    spec={"minimum_train":2,"minimum_validation":1,"scope_review":{"T1":{"status":"in","reason":"AI","overlap":"none"}},
          "catalogue_a":["T1"],"catalogue_b":["T1"]}
    rows=pd.DataFrame([{"primary_topic_id":"https://openalex.org/T1","publication_year":y}
                       for y in (2020,2021,2024,2025,2025,2025)])
    result=scope_table(rows,meta,spec)
    assert result.train_2020_2023.iat[0]==2 and result.validation_2024.iat[0]==1
    assert scope_table(rows.loc[rows.publication_year.ne(2025)],meta,spec).equals(result)


def test_blocked_near_duplicate_detection_and_exact_keys():
    text="robust tracking algorithm for human visual motion"
    abstract="We propose a robust tracking algorithm for human visual motion in video data."
    rows=pd.DataFrame([
        {"work_id":"A","doi":"https://doi.org/10.1/x","title_clean":text,
         "abstract_clean":abstract,"text":text+"\n"+abstract,"publication_year":2023},
        {"work_id":"B","doi":"https://doi.org/10.1/x","title_clean":text+" systems",
         "abstract_clean":abstract,"text":text+" systems\n"+abstract,"publication_year":2024},
    ])
    pairs,audit=exact_and_near_duplicates(rows)
    assert audit["canonical_doi_cross_period_groups"]==1
    assert audit["near_duplicate_pairs"]>=1
    assert pairs.validation_work_id.iat[0]=="B"


def test_threshold_is_calibration_only_and_open_set_denominators():
    scores=np.array([.9,.8,.7,.6,.5,.4,.3])
    inside=np.array([1,1,1,0,0,0,0],dtype=bool)
    threshold=select_rejection_threshold(scores,inside,.25)
    assert np.mean(scores[~inside]>=threshold)<=.25
    true=np.array(["T1","T1","OUT","OUT"])
    pred=np.array(["T1","T2","T1","T1"])
    result=open_set_metrics(np.array([.9,.2,.8,.1]),pred,true,{"T1","T2"},.5)
    assert result["in_acceptance_rate"]==.5
    assert result["out_false_acceptance_rate"]==.5
    assert result["end_to_end_correct_placement"]==.25
    assert result["accepted_precision_in_catalogue"]==.5
    with pytest.raises(ValueError): select_rejection_threshold(np.array([1,2]),np.array([1,1]))


def test_stable_hash_split_preserves_version_groups_and_is_reproducible():
    rows=pd.DataFrame({"work_id":[f"W{i}" for i in range(12)],
                       "version_group":[f"G{i}" for i in range(12)],
                       "primary_topic_id":["T1"]*6+["OUT"]*6})
    first=stable_group_split(rows,{"T1"})
    second=stable_group_split(rows.sample(frac=1,random_state=3),{"T1"})
    assert set(first[0].work_id)==set(second[0].work_id)
    assert not set(first[0].version_group)&set(first[1].version_group)
    assert set(first[0].work_id)|set(first[1].work_id)==set(rows.work_id)
    with pytest.raises(ValueError,match="duplicate version"):
        stable_group_split(pd.concat([rows,rows.iloc[[0]]],ignore_index=True),{"T1"})


def test_paired_bootstrap_is_reproducible_and_uses_same_draws():
    y=np.array(["a","a","b","b"])
    preds={"same":y.copy(),"worse":np.array(["a","b","a","b"])}
    first=paired_bootstrap(y,preds,"same","worse",draws=30)
    assert first==paired_bootstrap(y,preds,"same","worse",draws=30)
    assert first["paired_macro_f1_difference"]["same_minus_worse"][0]>=0


def _tiny_model():
    model=make_pipeline("linear_svm",1.)
    model.fit(["vision image segmentation method","vision image neural method",
               "language text sentiment method","language text opinion method"],
              ["T1","T1","T2","T2"])
    return model


def test_model_reload_inference_and_missing_brief(tmp_path):
    model=_tiny_model()
    model_path=tmp_path/"catalogue_b_linear_svm.joblib"
    joblib.dump(model,model_path)
    briefs={"T1":{"name":"Vision","source":"sample"},"T2":{"name":"Language","source":"sample"}}
    brief_path=tmp_path/"topic_briefs.json"; brief_path.write_text(json.dumps(briefs))
    manifest={"status":"complete","outputs":{
        "catalogue_b_linear_svm":{"sha256":hashlib.sha256(model_path.read_bytes()).hexdigest(),"path":str(model_path)},
        "topic_briefs":{"sha256":hashlib.sha256(brief_path.read_bytes()).hexdigest(),"path":str(brief_path)}},
        "open_set":{"svm_max_decision":{"evaluation":{"threshold":-10.}}}}
    (tmp_path/"manifest.json").write_text(json.dumps(manifest))
    loaded,context,threshold,_=load_verified_brief_run(tmp_path)
    result=place_research_draft("Vision method","This study presents a vision image segmentation method for analysis.",loaded,context,threshold,top_k=2)
    assert result["status"]=="placed" and result["topic_brief"]["source"]=="sample"
    missing=place_research_draft("Vision method","This study presents a vision image segmentation method for analysis.",loaded,{},threshold,top_k=2)
    assert missing["status"]=="placed" and missing["warning"]=="Topic brief context unavailable"
    with pytest.raises(ValueError,match="abstract"): place_research_draft("Vision","short",loaded,context,threshold)
    with pytest.raises(ValueError,match="title"): place_research_draft("","This is a sufficiently long abstract with several words for testing.",loaded,context,threshold)
    brief_path.write_text("{}")
    with pytest.raises(ValueError,match="Corrupted"): load_verified_brief_run(tmp_path)


def test_real_rating_import_requires_two_complete_blinded_raters():
    model=_tiny_model()
    blind=pd.DataFrame([{"example_id":"E1","title":"Vision methods","abstract":"image segmentation"},
                        {"example_id":"E2","title":"Language methods","abstract":"text sentiment"}])
    key=pd.DataFrame([{"example_id":"E1","work_id":"W1","openalex_primary_topic":"T1"},
                      {"example_id":"E2","work_id":"W2","openalex_primary_topic":"T2"}])
    ratings=pd.DataFrame([("E1","r1","T1"),("E1","r2","T1"),
                          ("E2","r1","T2"),("E2","r2","NONE")],
                         columns=["example_id","rater_id","best_topic"])
    result=analyze_ratings(ratings,blind,key,{"T1","T2"},model)
    assert result["examples"]==2 and result["raw_agreement"]==.5
    with pytest.raises(ValueError,match="both ratings"):
        analyze_ratings(ratings.iloc[:-1],blind,key,{"T1","T2"},model)
    full=ratings.replace({"T1":"https://openalex.org/T1","T2":"https://openalex.org/T2"})
    full_key=key.replace({"T1":"https://openalex.org/T1","T2":"https://openalex.org/T2"})
    assert analyze_ratings(ratings,blind,full_key,{"https://openalex.org/T1","https://openalex.org/T2"},model)["examples"]==2


def test_read_only_run_verifier_rejects_changed_output_and_unsealed_test(tmp_path):
    output=tmp_path/"small.csv"; output.write_text("count\n2\n")
    manifest={"status":"complete","test_2025":"sealed_not_evaluated",
              "validation_eligible":10,"catalogues":{"B":{"validation_rows":4}},
              "open_set":{"svm_max_decision":{"evaluation":{"total":6}}},
              "outputs":{"small":{"path":str(output),"sha256":hashlib.sha256(output.read_bytes()).hexdigest(),
                                  "bytes":output.stat().st_size}}}
    (tmp_path/"manifest.json").write_text(json.dumps(manifest))
    assert verify_run(tmp_path)["outputs_verified"]==1
    output.write_text("count\n3\n")
    with pytest.raises(ValueError,match="changed output"): verify_run(tmp_path)
    output.write_text("count\n2\n")
    manifest["test_2025"]="evaluated"
    (tmp_path/"manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError,match="test status"): verify_run(tmp_path)
