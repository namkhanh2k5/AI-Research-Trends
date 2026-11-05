"""Offline invariants for the targeted training-data finalization audit."""

import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest
import yaml

from ai_research_trends.analysis.label_drift import deterministic_audit_ids, summarize_drift
from ai_research_trends.analysis.ml_data_gap import audit_training_gaps
from ai_research_trends.crawling.collect_ml_expansion import (
    _checkpoint_pages, _finalize, validate_expansion_plan, validate_page,
)
from ai_research_trends.crawling.ml_expansion_plan import (
    build_plan, build_smoke_plan, verify_plan_inputs,
)
from ai_research_trends.crawling.verify_ml_expansion import verify
from ai_research_trends.ml.topic_pilot import title_key
from ai_research_trends.preprocessing.ml_expansion_quality import (
    audit_records, identity_keys, text_quality,
)
from ai_research_trends.preprocessing.validate_tables import file_sha256


def _fixtures():
    ids=[f"T{i}" for i in range(1,15)]
    works=[]; topics=[]; metadata=[]
    for index,short in enumerate(ids):
        metadata.append({"short_id":short,"name":f"Topic {index}","description":"official text",
                         "subfield_id":1702})
        for pos,year in enumerate((2022,2023)):
            wid=f"https://openalex.org/W{1000+index*2+pos}"
            works.append({"work_id":wid,"publication_year":year,"title":f"Distinct title for {short} {year}",
                          "abstract":"Long research abstract with adequate details and scientific terms.",
                          "doi":f"https://doi.org/10.1/{short}-{pos}","work_type":"article",
                          "language":"en","primary_topic_id":f"https://openalex.org/{short}"})
            topics.append({"work_id":wid,"topic_id":f"https://openalex.org/{short}",
                           "topic_rank":1,"topic_score":.8})
    works.append({"work_id":"https://openalex.org/W9999","publication_year":2025,
                  "title":"Sealed paper","abstract":"Do not inspect","doi":None,
                  "work_type":"article","language":"en","primary_topic_id":"https://openalex.org/T1"})
    catalogue={"catalogue_b":ids,"scope_review":{short:{"overlap":"none","reason":"method"} for short in ids}}
    return pd.DataFrame(works),pd.DataFrame(topics),catalogue,pd.DataFrame(metadata)


def test_gap_uses_training_only_and_calculates_shortfalls():
    works,topics,catalogue,metadata=_fixtures()
    result=audit_training_gaps(works,topics,catalogue,metadata,(4,))
    assert len(result)==14 and result.usable_training_works.sum()==28
    assert result.shortfall_4.sum()==28
    assert result.estimated_raw_needed_4.sum()==28
    assert "shortfall_300" not in result.columns
    assert all(result.source_2023.eq(1))
    # A sealed test record must not change a planning result.
    clean=audit_training_gaps(works.loc[works.publication_year.ne(2025)],topics,catalogue,metadata,(4,))
    pd.testing.assert_frame_equal(result,clean)


def test_gap_detects_missing_abstract_and_version_exclusion():
    works,topics,catalogue,metadata=_fixtures()
    works.loc[works.work_id.eq("https://openalex.org/W1000"),"abstract"]=None
    works.loc[works.work_id.eq("https://openalex.org/W1003"),"doi"]="https://doi.org/10.1/T2-0"
    result=audit_training_gaps(works,topics,catalogue,metadata,(4,))
    assert result.set_index("short_id").at["T1","missing_abstract_rate"]==.5
    assert result.set_index("short_id").at["T2","version_exclusions"]==1
    assert result.set_index("short_id").at["T2","usable_training_works"]==1


def test_drift_id_selection_is_deterministic_and_excludes_2025():
    works,_,_,_=_fixtures()
    selected={"https://openalex.org/T1"}
    first=deterministic_audit_ids(works,selected,42,per_topic=1,outside=3)
    second=deterministic_audit_ids(works.sample(frac=1,random_state=2),selected,42,per_topic=1,outside=3)
    assert first==second and "https://openalex.org/W9999" not in first
    with pytest.raises(ValueError,match="Insufficient"):
        deterministic_audit_ids(works,selected,42,per_topic=3,outside=3)


def test_label_drift_summary_counts_transitions_and_missingness():
    selected={"https://openalex.org/T1"}
    frame=pd.DataFrame([
        {"status":"retrieved","old_primary_topic":"https://openalex.org/T1",
         "new_primary_topic":"https://openalex.org/T2","top3_set_agree":False,
         "old_title_missing":False,"new_title_missing":False,
         "old_abstract_missing":True,"new_abstract_missing":False},
        {"status":"retrieved","old_primary_topic":"https://openalex.org/T1",
         "new_primary_topic":"https://openalex.org/T1","top3_set_agree":True,
         "old_title_missing":False,"new_title_missing":False,
         "old_abstract_missing":False,"new_abstract_missing":False},
        {"status":"unavailable"},
    ])
    summary=summarize_drift(frame,selected)
    assert summary["checked"]==3 and summary["retrieved"]==2
    assert summary["primary_changed"]==1 and summary["top_three_set_agree"]==1
    assert summary["old_selected_moved_outside_catalogue"]==1


def _plan_fixture():
    config=yaml.safe_load(Path("config/finalization_phase1_collection.yaml").read_text())
    catalogue=yaml.safe_load(Path(config["catalogue"]).read_text())
    gap=pd.DataFrame({"short_id":catalogue["catalogue_b"],
                      "estimated_raw_needed_225":[10]*14,"shortfall_225":[5]*14})
    capacities={topic:{year:1000 for year in range(2020,2024)}
                for topic in catalogue["catalogue_b"]}
    capacities.update({source["primary_topic_id"] or "BROAD":{year:1000 for year in range(2020,2024)}
                       for source in config["outside_sources"]})
    plan=build_plan(config,catalogue,gap,capacities)
    plan["config_sha256"]="a"*64
    plan["catalogue_sha256"]="b"*64
    return config,catalogue,plan


def test_plan_validation_rejects_tampered_historical_scope_and_quota():
    config,catalogue,plan=_plan_fixture()
    validate_expansion_plan(plan,config,catalogue)
    smoke=build_smoke_plan(plan)
    validate_expansion_plan(smoke,config,catalogue)
    assert {row["year"] for row in smoke["strata"]}==set(range(2020,2024))
    for key,value in (("filter","from_publication_date:2024-01-01"),
                      ("seed",42),("planned_records",99999)):
        altered=deepcopy(plan);altered["strata"][0][key]=value
        with pytest.raises(ValueError): validate_expansion_plan(altered,config,catalogue)
    altered=deepcopy(plan);altered["selected_planned_records"]+=1
    with pytest.raises(ValueError): validate_expansion_plan(altered,config,catalogue)


def _work(wid: str, topic: str="T10028") -> dict:
    return {"id":f"https://openalex.org/{wid}","publication_year":2020,
            "publication_date":"2020-04-01","type":"article","is_retracted":False,
            "title":"A Very Specific Artificial Intelligence Research Paper",
            "doi":f"https://doi.org/10.1234/{wid}",
            "primary_topic":{"id":f"https://openalex.org/{topic}",
                             "subfield":{"id":"https://openalex.org/subfields/1702"}},
            "abstract_inverted_index":{"This":[0],"is":[1],"an":[2],
                                       "abstract":[3],"with":[4],"enough":[5],"tokens":[6]}}


def test_page_validation_enforces_exact_year_topic_and_retraction():
    stratum={"year":2020,"topic_id":"T10028"}
    assert len(validate_page([_work("W123")],stratum))==1
    for mutation in ({"publication_date":"2024-01-01"},{"is_retracted":True},
                     {"primary_topic":{"id":"https://openalex.org/T10036",
                                      "subfield":{"id":"https://openalex.org/subfields/1702"}}}):
        work={**_work("W123"),**mutation}
        with pytest.raises(ValueError): validate_page([work],stratum)


def test_resume_probe_fails_safely_when_seeded_page_changes(tmp_path):
    run=tmp_path/"run";folder=run/"stratum_000";folder.mkdir(parents=True)
    saved={"meta":{"count":1},"results":[_work("W123")],"group_by":[]}
    path=folder/"page_001.json";path.write_text(json.dumps(saved))
    stratum={"source_group":"selected","year":2020,"topic_id":"T10028",
             "planned_records":1,"filter":"test","seed":42,"pages":[{
                 "page_number":1,"sha256":file_sha256(path),
                 "work_ids":["https://openalex.org/W123"]}]}
    manifest={"strata":[stratum],"per_page":100,"api_requests_attempted":0,
              "maximum_api_requests":5,"api_credits_observed":0,"maximum_api_credits":5,
              "last_daily_credits_remaining":100,"api_requests_succeeded":0,"resume_probes":[]}
    manifest["resume_attempts"]=1
    manifest_path=run/"manifest.json";manifest_path.write_text(json.dumps(manifest))
    changed={"meta":{"count":1},"results":[_work("W456")],"group_by":[]}
    response=SimpleNamespace(content=json.dumps(changed).encode(),headers={"X-RateLimit-Credits-Used":"1",
                            "X-RateLimit-Remaining":"99"})
    response.json=lambda: changed
    client=SimpleNamespace(request=lambda path,params:response)
    with pytest.raises(ValueError,match="membership changed"):
        _checkpoint_pages(run,manifest,client,manifest_path)
    assert path.read_text()==json.dumps(saved)
    assert len(manifest["resume_probes"])==1 and not manifest["resume_probes"][0]["ordered_id_match"]


def test_text_quality_and_identity_keys_keep_malformed_evidence():
    assert text_quality(_work("W123"))[0]=="short_abstract"
    work=_work("W123");work["abstract_inverted_index"]={"bad":[-1]}
    assert text_quality(work)[0]=="malformed_abstract"
    assert identity_keys("https://doi.org/10.1234/ABC","A very long title for a paper")=={
        "doi:10.1234/abc","title:"+title_key("A very long title for a paper")}


def test_quality_excludes_original_and_heldout_identity_without_labels():
    config,catalogue,_=_plan_fixture()
    original=pd.DataFrame([
        {"work_id":"https://openalex.org/W10","publication_year":2020,
         "doi":"https://doi.org/10.1234/train","title":"Original training document long title"},
        {"work_id":"https://openalex.org/W11","publication_year":2025,
         "doi":"https://doi.org/10.1234/test","title":"Hidden test document long title"},
    ])
    gap=pd.DataFrame({"short_id":catalogue["catalogue_b"],"usable_training_works":[1]*14})
    records=[]
    for wid,doi in (("W20","https://doi.org/10.1234/test"),
                    ("W21","https://doi.org/10.1234/new")):
        work=_work(wid);work["doi"]=doi
        work["title"]=f"A unique and specific artificial intelligence study {wid}"
        work["abstract_inverted_index"]={f"word{i}":[i] for i in range(40)}
        records.append({"work":work,"provenance":{"source_query":{"filter":"primary_topic.id:T10028"},
                       "source_group":"selected","retrieved_at_utc":"2026-11-01T00:00:00Z",
                       "collection_run_id":"test"}})
    audit,tables,summary=audit_records(records,original,catalogue,gap)
    assert audit.set_index("work_id").at["https://openalex.org/W20","exclusion_reason"]=="heldout_doi_or_title_overlap"
    assert summary["eligible_new_total"]==1
    assert tables["topic_support"].set_index("topic_id").at["T10028","newly_usable_train"]==1


def test_local_finalization_and_read_only_verifier_detect_corrupt_raw_page(tmp_path):
    root=tmp_path/"raw";interim=tmp_path/"interim"
    folder=root/"stratum_000";folder.mkdir(parents=True);interim.mkdir()
    page=folder/"page_001.json"
    page.write_text(json.dumps({"meta":{"count":1},"results":[_work("W123")],"group_by":[]}))
    manifest={"status":"incomplete","complete":False,"run_id":"test",
              "started_at_utc":"2026-11-01T00:00:00Z","planned_raw_records":1,
              "per_page":100,"strata":[{"year":2020,"topic_id":"T10028",
                "source_group":"selected","planned_records":1,"expected_pages":1,
                "pages":[{"page_number":1,"sha256":file_sha256(page),
                          "bytes":page.stat().st_size,
                          "work_ids":["https://openalex.org/W123"],
                          "retrieved_at_utc":"2026-11-01T00:00:00Z","params":{"sample":1}}]}]}
    _finalize(root,interim,manifest)
    path=root/"manifest.json";path.write_text(json.dumps(manifest))
    result=verify(path)
    assert result["valid"] and result["verified_pages"]==1 and result["unique_work_ids"]==1
    page.write_text(page.read_text()+" ")
    with pytest.raises(ValueError,match="checksum"):
        verify(path)


def test_duplicate_new_identity_keeps_only_earliest_version():
    _,catalogue,_=_plan_fixture()
    original=pd.DataFrame([{"work_id":"https://openalex.org/W10","publication_year":2025,
                            "doi":None,"title":"Unrelated heldout record"}])
    gap=pd.DataFrame({"short_id":catalogue["catalogue_b"],"usable_training_works":[1]*14})
    records=[]
    for wid,date in (("W21","2020-05-01"),("W20","2020-03-01")):
        work=_work(wid);work["doi"]="https://doi.org/10.1234/shared";work["publication_date"]=date
        work["abstract_inverted_index"]={f"word{i}":[i] for i in range(40)}
        records.append({"work":work,"provenance":{"source_query":{"filter":"primary_topic.id:T10028"},
                       "source_group":"selected","retrieved_at_utc":"2026-11-01T00:00:00Z",
                       "collection_run_id":"test"}})
    audit,_,summary=audit_records(records,original,catalogue,gap)
    assert summary["eligible_new_total"]==1
    assert audit.set_index("work_id").at["https://openalex.org/W20","exclusion_reason"]=="eligible"
    assert audit.set_index("work_id").at["https://openalex.org/W21","exclusion_reason"]=="new_version_overlap"


def test_plan_rebuild_rejects_tampered_allocation(tmp_path):
    config,catalogue,plan=_plan_fixture()
    config_path=tmp_path/"config.yaml";config_path.write_text(yaml.safe_dump(config))
    catalogue_path=Path(config["catalogue"])
    gap_path=tmp_path/"gap.csv"
    pd.DataFrame({"short_id":catalogue["catalogue_b"],
                  "estimated_raw_needed_225":[10]*14,"shortfall_225":[5]*14}).to_csv(gap_path,index=False)
    capacities_dir=tmp_path/"counts";capacities_dir.mkdir()
    rows=[]
    sources=list(dict.fromkeys(catalogue["catalogue_b"]+
              [source["primary_topic_id"] or "BROAD" for source in config["outside_sources"]]))
    for source in sources:
        payload={"meta":{"count":4000},"results":[],"group_by":[
            {"key":str(year),"count":1000} for year in range(2020,2024)]}
        path=capacities_dir/f"{source}.json";path.write_text(json.dumps(payload))
        rows.append({"source":source,"path":str(path),"sha256":file_sha256(path),
                     "counts":{str(year):1000 for year in range(2020,2024)}})
    source_manifest=capacities_dir/"manifest.json"
    source_manifest.write_text(json.dumps({"status":"complete","queries":rows}))
    plan.update({"config_sha256":file_sha256(config_path),
                 "catalogue_sha256":file_sha256(catalogue_path),
                 "gap_sha256":file_sha256(gap_path),
                 "capacity_manifest_sha256":file_sha256(source_manifest)})
    assert verify_plan_inputs(plan,config_path,catalogue_path,gap_path,capacities_dir)["valid"]
    altered=deepcopy(plan);altered["strata"][0]["planned_records"]+=1
    with pytest.raises(ValueError,match="allocation changed"):
        verify_plan_inputs(altered,config_path,catalogue_path,gap_path,capacities_dir)


def test_published_aggregate_package_has_no_record_level_work_ids():
    root=Path("reports/finalization_p1")
    manifest=json.loads((root/"reproducibility_manifest.json").read_text())
    assert manifest["status"]=="complete" and manifest["no_record_level_abstracts_or_heldout_labels"]
    assert manifest["verified_raw_records"]==2515
    for name,detail in manifest["files"].items():
        path=root/name
        assert path.is_file() and path.stat().st_size==detail["bytes"]
        assert file_sha256(path)==detail["sha256"]
        assert "https://openalex.org/W" not in path.read_text()
