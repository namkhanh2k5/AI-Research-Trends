"""Disjoint 2024 calibration/evaluation of catalogue rejection strategies."""

from __future__ import annotations

import argparse
import json
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import roc_curve
from sklearn.model_selection import StratifiedKFold

from ai_research_trends.ml.final_experiments import CATALOGUE, INTEGRATED, SEED, load_data
from ai_research_trends.ml.topic_final_validation import (make_pipeline, open_set_metrics,
                                                         select_rejection_threshold, stable_group_split)
from ai_research_trends.preprocessing.validate_tables import file_sha256


def score_predictions(model: object, texts: list[str], method: str,
                      selected: set[str]) -> tuple[np.ndarray,np.ndarray]:
    if method=="svm_margin":
        values=np.asarray(model.decision_function(texts))
        score=values.max(axis=1)
        pred=model.predict(texts)
    elif method in ("calibrated_lr","lr_raw_probability","nb_probability"):
        values=np.asarray(model.predict_proba(texts))
        score=values.max(axis=1)
        pred=model.predict(texts)
    elif method=="explicit_other_lr":
        values=np.asarray(model.predict_proba(texts))
        classes=np.asarray(model.named_steps["model"].classes_)
        supported=np.isin(classes,list(selected))
        score=1-values[:,classes.tolist().index("OTHER")]
        pred=classes[supported][values[:,supported].argmax(axis=1)]
    else: raise ValueError(method)
    if len(score)!=len(pred):raise ValueError("Open-set score/prediction mismatch")
    return np.asarray(score,dtype=float),np.asarray(pred,dtype=object)


def bootstrap_open_set(scores: np.ndarray,pred: np.ndarray,truth: np.ndarray,
                       selected: set[str],threshold: float,draws: int=500) -> dict:
    rng=np.random.default_rng(SEED)
    keys=("in_acceptance_rate","out_false_acceptance_rate","auroc_in_vs_out",
          "end_to_end_correct_placement","accepted_precision_in_catalogue")
    samples={key:[] for key in keys}
    for _ in range(draws):
        ix=rng.integers(0,len(truth),len(truth))
        if np.isin(truth[ix],list(selected)).all() or not np.isin(truth[ix],list(selected)).any():continue
        result=open_set_metrics(scores[ix],pred[ix],truth[ix],selected,threshold)
        for key in keys:samples[key].append(result[key])
    return {key:[float(x) for x in np.quantile(values,[.025,.975])] for key,values in samples.items()}


def run(integrated: Path, catalogue: Path, closed_run: Path, output_dir: Path) -> dict:
    if output_dir.exists():raise FileExistsError(output_dir)
    closed=json.loads((closed_run/"results.json").read_text())
    if closed["source_manifest_sha256"]!=file_sha256(integrated/"split_manifest.json"):
        raise ValueError("Closed-set run used another integrated dataset")
    train,valid,classes,_,_=load_data(integrated,catalogue);selected=set(classes)
    calibration,evaluation=stable_group_split(valid,selected,fraction=.4)
    if set(calibration.work_id)&set(evaluation.work_id) or set(calibration.version_group)&set(evaluation.version_group):
        raise ValueError("2024 calibration/evaluation leakage")
    lr=joblib.load(closed_run/"models/expanded_logistic_regression.joblib")
    svm=joblib.load(closed_run/"models/expanded_linear_svm.joblib")
    nb=joblib.load(closed_run/"models/expanded_complement_nb.joblib")
    selected_train=train.loc[train.primary_topic_id.isin(selected)]
    lr_c=float(closed["fit_info"]["expanded_logistic_regression"]["selected"]["model__C"])
    calibrated=CalibratedClassifierCV(estimator=make_pipeline("logistic_regression",lr_c),
        method="sigmoid",cv=StratifiedKFold(3,shuffle=True,random_state=SEED),n_jobs=1)
    start=time.perf_counter();calibrated.fit(selected_train.text.tolist(),selected_train.primary_topic_id.tolist())
    calibration_seconds=time.perf_counter()-start
    other=train.copy()
    other["target"]=other.primary_topic_id.where(other.primary_topic_id.isin(selected),"OTHER")
    explicit=make_pipeline("logistic_regression",lr_c)
    start=time.perf_counter();explicit.fit(other.text.tolist(),other.target.tolist())
    other_seconds=time.perf_counter()-start
    methods={"calibrated_lr":calibrated,"lr_raw_probability":lr,
             "svm_margin":svm,"nb_probability":nb,
             "explicit_other_lr":explicit}
    results={};tables={};thresholds={}
    for name,model in methods.items():
        cal_score,cal_pred=score_predictions(model,calibration.text.tolist(),name,selected)
        start=time.perf_counter()
        eval_score,eval_pred=score_predictions(model,evaluation.text.tolist(),name,selected)
        latency_ms=1000*(time.perf_counter()-start)/len(evaluation)
        threshold=select_rejection_threshold(cal_score,calibration.primary_topic_id.isin(selected).to_numpy(),.2)
        thresholds[name]=float(threshold)
        confirmation_floor=float(min(threshold,np.quantile(cal_score,.25)))
        cal=open_set_metrics(cal_score,cal_pred,calibration.primary_topic_id.to_numpy(),selected,threshold)
        ev=open_set_metrics(eval_score,eval_pred,evaluation.primary_topic_id.to_numpy(),selected,threshold)
        accepted=eval_score>=threshold
        ev["accepted_correct_precision_all"]=float(ev["correct_accepted_in"]/max(1,int(accepted.sum())))
        ev["overall_acceptance_rate"]=float(accepted.mean())
        results[name]={"threshold":float(threshold),"confirmation_floor":confirmation_floor,
            "calibration":cal,"evaluation":ev,
            "evaluation_bootstrap_95":bootstrap_open_set(eval_score,eval_pred,
                evaluation.primary_topic_id.to_numpy(),selected,threshold),
            "inference_ms_per_work":latency_ms,
            "score_interpretation":("train-CV sigmoid-calibrated multiclass maximum probability; "
                "not calibrated catalogue-membership probability" if name=="calibrated_lr" else
                "raw LinearSVC maximum decision margin; not a probability" if name=="svm_margin" else
                "LogisticRegression raw maximum class probability estimate" if name=="lr_raw_probability" else
                "ComplementNB maximum class probability estimate; not independently calibrated" if name=="nb_probability" else
                "one minus 15-class OTHER probability; model-dependent score")}
        tables[f"{name}_predictions"]=pd.DataFrame({"work_id":evaluation.work_id.to_numpy(),
            "true_topic":evaluation.primary_topic_id.to_numpy(),"predicted_topic":eval_pred,
            "score":eval_score,"accepted":accepted})
        fpr,tpr,roc_threshold=roc_curve(evaluation.primary_topic_id.isin(selected),eval_score)
        tables[f"{name}_roc"]=pd.DataFrame({"fpr":fpr,"tpr":tpr,"threshold":roc_threshold})
        sensitivity=[]
        for candidate in np.quantile(cal_score,np.linspace(0,1,21)):
            row=open_set_metrics(eval_score,eval_pred,evaluation.primary_topic_id.to_numpy(),selected,float(candidate))
            sensitivity.append({"threshold":float(candidate),"coverage":row["selective_coverage_in"],
                "risk":row["selective_risk"],"false_acceptance":row["out_false_acceptance_rate"]})
        tables[f"{name}_risk_coverage"]=pd.DataFrame(sensitivity)
        by_topic=[]
        for topic in classes:
            mask=evaluation.primary_topic_id.eq(topic).to_numpy()
            by_topic.append({"topic_id":topic,"n":int(mask.sum()),"accepted":int((accepted&mask).sum()),
                             "acceptance_rate":float((accepted&mask).sum()/max(1,mask.sum()))})
        tables[f"{name}_per_topic"]=pd.DataFrame(by_topic)
    output_dir.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".final_p3_open_stage_",dir=output_dir.parent) as temp:
        stage=Path(temp);(stage/"models").mkdir()
        joblib.dump(calibrated,stage/"models/calibrated_lr.joblib",compress=3)
        joblib.dump(explicit,stage/"models/explicit_other_lr.joblib",compress=3)
        for name,frame in tables.items():
            if name.endswith("_predictions"):frame.to_parquet(stage/f"{name}.parquet",index=False)
            else:frame.to_csv(stage/f"{name}.csv",index=False)
        output={"status":"complete","run_id":output_dir.name,
            "created_at_utc":datetime.now(timezone.utc).isoformat(),
            "closed_run_manifest_sha256":file_sha256(closed_run/"manifest.json"),
            "source_manifest_sha256":file_sha256(integrated/"split_manifest.json"),
            "catalogue_sha256":file_sha256(catalogue),"code_sha256":file_sha256(Path(__file__)),
            "seed":SEED,"calibration_rows":len(calibration),"evaluation_rows":len(evaluation),
            "calibration_in":int(calibration.primary_topic_id.isin(selected).sum()),
            "evaluation_in":int(evaluation.primary_topic_id.isin(selected).sum()),
            "threshold_selection":"2024 calibration only; lowest score with <=20% outside false acceptance",
            "calibrated_lr_train_only_seconds":calibration_seconds,
            "explicit_other_training_seconds":other_seconds,"methods":results,"thresholds":thresholds,
            "human_semantic_validation":"pending","final_2025_test":"SEALED"}
        (stage/"results.json").write_text(json.dumps(output,indent=2)+"\n")
        output["files"]={str(path.relative_to(stage)):{"sha256":file_sha256(path),"bytes":path.stat().st_size}
                         for path in sorted(stage.rglob("*")) if path.is_file()}
        (stage/"manifest.json").write_text(json.dumps({key:output[key] for key in
            ("status","run_id","created_at_utc","source_manifest_sha256","closed_run_manifest_sha256",
             "catalogue_sha256","code_sha256","seed","files","final_2025_test")},indent=2)+"\n")
        stage.replace(output_dir)
    return output


def main(argv: list[str]|None=None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--integrated",type=Path,default=INTEGRATED)
    parser.add_argument("--catalogue",type=Path,default=CATALOGUE)
    parser.add_argument("--closed-run",type=Path,required=True)
    parser.add_argument("--output-dir",type=Path,required=True)
    args=parser.parse_args(argv);result=run(args.integrated,args.catalogue,args.closed_run,args.output_dir)
    print(json.dumps({"status":result["status"],"calibration_rows":result["calibration_rows"],
        "evaluation_rows":result["evaluation_rows"],"thresholds":result["thresholds"]},indent=2));return 0


if __name__=="__main__":raise SystemExit(main())
