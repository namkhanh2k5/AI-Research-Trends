"""Checksum-verified local topic placement and Phase 2 Topic Brief integration."""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import yaml

from ai_research_trends.analysis.web_queries import ResearchData
from ai_research_trends.ml.final_experiments import CATALOGUE, INTEGRATED
from ai_research_trends.ml.topic_pilot import clean_text
from ai_research_trends.ml.verify_final_ml import verify_experiment
from ai_research_trends.preprocessing.validate_tables import file_sha256


def select_champion(closed: dict,opened: dict) -> tuple[str,str]:
    candidates=("complement_nb","logistic_regression","linear_svm")
    score={name:closed["metrics"][f"expanded_{name}"]["macro_f1"] for name in candidates}
    best=max(score.values());near=[name for name in candidates if best-score[name]<=.01]
    method={"complement_nb":"nb_probability","logistic_regression":"lr_raw_probability",
            "linear_svm":"svm_margin"}
    # The tie rule was declared in the pre-experiment protocol.
    winner=min(near,key=lambda name:(opened["methods"][method[name]]["evaluation"]["out_false_acceptance_rate"],
                                  opened["methods"][method[name]]["inference_ms_per_work"],name))
    return winner,method[winner]


def package_model(closed_dir: Path,open_dir: Path,integrated: Path,catalogue_path: Path,
                  web_dir: Path,output_dir: Path) -> dict:
    if output_dir.exists():raise FileExistsError(output_dir)
    verify_experiment(closed_dir,integrated)
    verify_experiment(open_dir,integrated)
    ResearchData(web_dir)
    closed=json.loads((closed_dir/"results.json").read_text())
    opened=json.loads((open_dir/"results.json").read_text())
    name,method=select_champion(closed,opened)
    model_source=closed_dir/"models"/f"expanded_{name}.joblib"
    source_sha=file_sha256(model_source)
    config=yaml.safe_load(catalogue_path.read_text())
    metadata_path=Path(config["source_metadata_csv"])
    if file_sha256(metadata_path)!=config["source_metadata_sha256"]:raise ValueError("Topic metadata changed")
    metadata={row.short_id:{"topic_name":row.name,"description":row.description,
                            "parent_subfield":str(row.subfield_id)} for row in
              pd.read_csv(metadata_path).itertuples() if row.short_id in config["catalogue_b"]}
    classes=closed["classes"]
    if set(metadata)!={item.rsplit("/",1)[-1] for item in classes}:
        raise ValueError("Catalogue metadata/class order mismatch")
    output_dir.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".final_model_stage_",dir=output_dir.parent) as temp:
        stage=Path(temp)
        shutil.copyfile(model_source,stage/"model.joblib")
        if file_sha256(stage/"model.joblib")!=source_sha:raise ValueError("Model copy changed")
        (stage/"topic_catalogue.json").write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+"\n")
        frozen={"model_version":output_dir.name,"catalogue_version":"phase6b-14-topic",
            "model_family":name,"score_method":method,
            "score_interpretation":opened["methods"][method]["score_interpretation"],
            "threshold":opened["methods"][method]["threshold"],
            "confirmation_floor":opened["methods"][method]["confirmation_floor"],
            "classes":classes,"training_source":"expanded 2020-2023 only",
            "validation_source":"original-sample 2024 development",
            "decision_policy":"assisted_suggestion_only; user confirmation required for every placement",
            "human_validation":"PENDING","final_2025_test":"SEALED",
            "feature_rule":"clean_text(title) + newline + clean_text(abstract)",
            "selected_parameter":closed["fit_info"][f"expanded_{name}"]["selected"],
            "random_seed":closed["seed"]}
        (stage/"frozen_config.json").write_text(json.dumps(frozen,indent=2)+"\n")
        files={p.name:{"sha256":file_sha256(p),"bytes":p.stat().st_size} for p in stage.iterdir() if p.is_file()}
        manifest={"status":"complete","created_at_utc":datetime.now(timezone.utc).isoformat(),
            "model_version":output_dir.name,"model_family":name,"open_set_method":method,
            "source_model_sha256":source_sha,
            "closed_run_manifest_sha256":file_sha256(closed_dir/"manifest.json"),
            "open_run_manifest_sha256":file_sha256(open_dir/"manifest.json"),
            "integrated_manifest_sha256":file_sha256(integrated/"split_manifest.json"),
            "web_manifest_sha256":file_sha256(web_dir/"manifest.json"),
            "catalogue_sha256":file_sha256(catalogue_path),
            "metadata_sha256":file_sha256(metadata_path),"files":files,
            "inference_code_sha256":file_sha256(Path(__file__)),
            "human_validation":"PENDING","final_2025_test":"SEALED",
            "source_paths":{"closed":str(closed_dir),"open":str(open_dir),"integrated":str(integrated),
                            "web":str(web_dir),"catalogue":str(catalogue_path),"metadata":str(metadata_path)}}
        (stage/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
        stage.replace(output_dir)
    return manifest


class TopicPlacementService:
    """Loads only a trusted, checksum-matched local model bundle."""

    def __init__(self,model_dir: Path,web_dir: Path):
        manifest=json.loads((model_dir/"manifest.json").read_text())
        if manifest.get("status")!="complete" or manifest.get("final_2025_test")!="SEALED":
            raise ValueError("Invalid or incomplete model package")
        for name,entry in manifest["files"].items():
            path=model_dir/name
            if not path.is_file() or file_sha256(path)!=entry["sha256"]:
                raise ValueError(f"Model artifact checksum mismatch: {name}")
        if manifest.get("inference_code_sha256")!=file_sha256(Path(__file__)):
            raise ValueError("Inference code differs from frozen package")
        if file_sha256(web_dir/"manifest.json")!=manifest["web_manifest_sha256"]:
            raise ValueError("Web data package differs from the model build")
        self.config=json.loads((model_dir/"frozen_config.json").read_text())
        self.catalogue=json.loads((model_dir/"topic_catalogue.json").read_text())
        self.model=joblib.load(model_dir/"model.joblib")
        actual=list(self.model.named_steps["model"].classes_)
        if actual!=self.config["classes"]:raise ValueError("Serialized model class order changed")
        self.research=ResearchData(web_dir)

    def place_research_draft(self,title: str,abstract: str,top_k: int=3) -> dict:
        if not isinstance(title,str) or not isinstance(abstract,str):raise ValueError("Title and abstract must be text")
        title=clean_text(title);abstract=clean_text(abstract)
        if not title:raise ValueError("Nonblank title required")
        if len(abstract)<50 or len(abstract.split())<8:
            raise ValueError("Abstract requires at least 50 characters and 8 words")
        if not isinstance(top_k,int) or not 1<=top_k<=len(self.config["classes"]):
            raise ValueError("Invalid top_k")
        text=title+"\n"+abstract
        if self.config["model_family"]=="linear_svm":
            score=np.asarray(self.model.decision_function([text]))[0]
        else:
            score=np.asarray(self.model.predict_proba([text]))[0]
        order=np.argsort(-score)[:top_k]
        ranked=[]
        for rank,index in enumerate(order,1):
            full=self.config["classes"][int(index)];short=full.rsplit("/",1)[-1]
            ranked.append({"topic_id":short,"topic_name":self.catalogue[short]["topic_name"],
                           "rank":rank,"score":float(score[index])})
        maximum=float(score[order[0]])
        threshold=self.config["threshold"];floor=self.config["confirmation_floor"]
        status="confident_suggestion" if maximum>=threshold else (
            "needs_user_confirmation" if maximum>=floor else "no_confident_match")
        warnings=["Suggestions are limited to fourteen OpenAlex silver-label topics; no human semantic validation yet.",
                  "The highest-ranked topic is not proof of paper quality or correct subject placement."]
        if len(abstract.split())<30:warnings.append("Abstract shorter than the training text-quality floor.")
        return {"status":status,"requires_user_confirmation":True,"automatic_placement":False,
            "model_version":self.config["model_version"],"catalogue_version":self.config["catalogue_version"],
            "label_source":"OpenAlex primary-topic silver labels","predictions":ranked,
            "score_interpretation":self.config["score_interpretation"],
            "decision_threshold":threshold,"warnings":warnings}

    def explore_research_draft(self,title: str,abstract: str,
                               selected_topic_id: str|None=None,top_k: int=3) -> dict:
        suggestion=self.place_research_draft(title,abstract,top_k)
        suggested=(suggestion["predictions"][0]["topic_id"] if
            suggestion["status"]=="confident_suggestion" else None)
        chosen=selected_topic_id or suggested
        brief=None
        if chosen is not None:
            brief=self.research.get_topic_brief(chosen)
        return {"suggestion":suggestion,"selection_source":"manual" if selected_topic_id else
                "model_suggestion_unconfirmed" if chosen else "none",
            "selected_topic_id":selected_topic_id,"suggested_topic_id":suggested,"topic_brief":brief,
            "population_trends":self.research.get_publication_trends(),
            "citation_context":self.research.get_citation_summary()[0],
            "oa_context":self.research.get_oa_summary(),
            "data_scope":{"population":"approved AI/CV primary-subfield non-retracted aggregate",
                          "topic_brief_papers":"original 12,000-work detailed sample only",
                          "training_expansion":"not included in research landscape statistics"}}


def main(argv: list[str]|None=None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest="command",required=True)
    make=sub.add_parser("package")
    make.add_argument("--closed-run",type=Path,required=True)
    make.add_argument("--open-run",type=Path,required=True)
    make.add_argument("--integrated",type=Path,default=INTEGRATED)
    make.add_argument("--catalogue",type=Path,default=CATALOGUE)
    make.add_argument("--web-dir",type=Path,default=Path("data/analysis/finalization_p2_web_data_20261101_v3"))
    make.add_argument("--output-dir",type=Path,required=True)
    infer=sub.add_parser("infer")
    infer.add_argument("--model-dir",type=Path,required=True)
    infer.add_argument("--web-dir",type=Path,default=Path("data/analysis/finalization_p2_web_data_20261101_v3"))
    infer.add_argument("--title",required=True);infer.add_argument("--abstract",required=True)
    infer.add_argument("--selected-topic-id");infer.add_argument("--top-k",type=int,default=3)
    args=parser.parse_args(argv)
    if args.command=="package":result=package_model(args.closed_run,args.open_run,args.integrated,
                                                        args.catalogue,args.web_dir,args.output_dir)
    else:result=TopicPlacementService(args.model_dir,args.web_dir).explore_research_draft(
        args.title,args.abstract,args.selected_topic_id,args.top_k)
    print(json.dumps(result,indent=2,ensure_ascii=False));return 0


if __name__=="__main__":raise SystemExit(main())
