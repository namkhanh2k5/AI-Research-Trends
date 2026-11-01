"""Leakage-checked, train-only-tuned Phase 3 topic-classification experiments."""

from __future__ import annotations

import argparse
import json
import platform
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
import yaml
from scipy.stats import wilcoxon
from sklearn.metrics import (accuracy_score, classification_report, confusion_matrix,
                             f1_score, precision_recall_fscore_support, top_k_accuracy_score)
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.model_selection import GridSearchCV, StratifiedGroupKFold
from sklearn.feature_extraction.text import TfidfVectorizer

from ai_research_trends.ml.topic_final_validation import make_pipeline
from ai_research_trends.ml.topic_pilot import clean_text
from ai_research_trends.ml.validate_integrated_data import verify_run
from ai_research_trends.preprocessing.validate_tables import file_sha256

SEED=20251019
OPTIONS={"complement_nb":[.5,1.,2.],"logistic_regression":[.3,1.,3.],
         "linear_svm":[.3,1.,3.]}
INTEGRATED=Path("data/processed/ml_topic_classification/finalization_p2_20261101_v3")
CATALOGUE=Path("config/phase6b_catalogue.yaml")


def text_features(frame: pd.DataFrame) -> pd.DataFrame:
    required={"work_id","version_group","title","abstract","publication_year","primary_topic_id"}
    if not required.issubset(frame.columns): raise ValueError("Model input missing required columns")
    out=frame.copy()
    out["title_clean"]=out.title.map(clean_text)
    out["abstract_clean"]=out.abstract.map(clean_text)
    if out.title_clean.eq("").any() or out.abstract_clean.eq("").any():
        raise ValueError("Model-ready split contains unusable title or abstract")
    out["text"]=out.title_clean+"\n"+out.abstract_clean
    if out.work_id.duplicated().any() or out.version_group.duplicated().any():
        raise ValueError("Duplicate work or version group within model split")
    return out


def load_data(integrated: Path, catalogue_path: Path) -> tuple[pd.DataFrame,pd.DataFrame,list[str],pd.DataFrame,dict]:
    verified=verify_run(integrated)
    config=yaml.safe_load(catalogue_path.read_text())
    metadata_path=Path(config["source_metadata_csv"])
    if file_sha256(metadata_path)!=config["source_metadata_sha256"]:
        raise ValueError("Official topic metadata changed")
    selected=[f"https://openalex.org/{short}" for short in config["catalogue_b"]]
    if len(selected)!=14 or len(set(selected))!=14: raise ValueError("Catalogue must remain frozen at 14 topics")
    train=text_features(pd.read_parquet(integrated/"train.parquet"))
    valid=text_features(pd.read_parquet(integrated/"validation_2024.parquet"))
    if not train.publication_year.isin((2020,2021,2022,2023)).all(): raise ValueError("Train-year leakage")
    if not valid.publication_year.eq(2024).all(): raise ValueError("Validation-year leakage")
    if set(train.work_id)&set(valid.work_id) or set(train.version_group)&set(valid.version_group):
        raise ValueError("Cross-split identity leakage")
    if valid.dataset_origin.ne("original_analytical_sample").any():
        raise ValueError("Targeted expansion entered 2024 validation")
    metadata=pd.read_csv(metadata_path)
    if not set(selected).issubset(set(metadata.topic_id)):
        raise ValueError("Selected official-topic descriptions missing")
    return train,valid,sorted(selected),metadata,verified


def tune_model(name: str, training: pd.DataFrame) -> tuple[object,dict]:
    if name not in OPTIONS: raise ValueError(name)
    if training.version_group.duplicated().any():
        raise ValueError("Group-aware tuning requires one row per version group")
    options=OPTIONS[name]
    parameter="model__alpha" if name=="complement_nb" else "model__C"
    grid=GridSearchCV(make_pipeline(name,options[0]),{parameter:options},
        cv=StratifiedGroupKFold(n_splits=3,shuffle=True,random_state=SEED),
        scoring="f1_macro",n_jobs=1,refit=True,error_score="raise")
    start=time.perf_counter()
    grid.fit(training.text.tolist(),training.primary_topic_id.tolist(),groups=training.version_group.tolist())
    return grid.best_estimator_,{"grid":options,"selected":grid.best_params_,
        "cv_macro_f1":float(grid.best_score_),
        "cv_scores":[float(x) for x in grid.cv_results_["mean_test_score"]],
        "training_search_seconds":time.perf_counter()-start,"folds":3,"seed":SEED,
        "fold_policy":"StratifiedGroupKFold on version_group; vectorizer inside pipeline"}


def metric_row(y: np.ndarray, prediction: np.ndarray, classes: list[str]) -> dict:
    return {"n":len(y),"accuracy":float(accuracy_score(y,prediction)),
        "macro_f1":float(f1_score(y,prediction,labels=classes,average="macro",zero_division=0)),
        "weighted_f1":float(f1_score(y,prediction,labels=classes,average="weighted",zero_division=0))}


def paired_bootstrap(y: np.ndarray, left: np.ndarray, right: np.ndarray,
                     classes: list[str], draws: int=500) -> dict:
    if not(len(y)==len(left)==len(right)) or len(y)==0: raise ValueError("Bootstrap arrays differ")
    rng=np.random.default_rng(SEED);difference=[];accuracy=[];left_scores=[];right_scores=[]
    for _ in range(draws):
        ix=rng.integers(0,len(y),len(y))
        a=float(f1_score(y[ix],left[ix],labels=classes,average="macro",zero_division=0))
        b=float(f1_score(y[ix],right[ix],labels=classes,average="macro",zero_division=0))
        left_scores.append(a);right_scores.append(b);difference.append(a-b)
        accuracy.append(float(accuracy_score(y[ix],left[ix])-accuracy_score(y[ix],right[ix])))
    q=lambda values:[float(x) for x in np.quantile(values,[.025,.975])]
    return {"draws":draws,"left_macro_f1_95":q(left_scores),"right_macro_f1_95":q(right_scores),
            "macro_f1_difference_95":q(difference),"accuracy_difference_95":q(accuracy)}


def description_predictions(texts: list[str],classes: list[str],metadata: pd.DataFrame) -> np.ndarray:
    descriptions=metadata.set_index("topic_id").loc[classes,"description"].fillna("").tolist()
    if not all(descriptions):raise ValueError("Missing official topic description")
    tfidf=TfidfVectorizer(ngram_range=(1,2),sublinear_tf=True)
    matrix=tfidf.fit_transform(descriptions)
    return np.asarray(classes,dtype=object)[cosine_similarity(tfidf.transform(texts),matrix).argmax(axis=1)]


def stratified_expansion_fraction(expansion: pd.DataFrame, fraction: float) -> pd.DataFrame:
    if fraction not in (0.,1/3,2/3,1.): raise ValueError("Unsupported preregistered expansion fraction")
    if fraction==0: return expansion.iloc[:0].copy()
    if fraction==1: return expansion.copy()
    rng=np.random.default_rng(SEED)
    selected=[]
    for _,group in expansion.groupby(["primary_topic_id","publication_year"],sort=True):
        order=np.asarray(sorted(group.index),dtype=int)
        rng.shuffle(order)
        selected.extend(order[:round(len(order)*fraction)])
    return expansion.loc[sorted(selected)].copy()


def run(integrated: Path, catalogue_path: Path, output_dir: Path) -> dict:
    if output_dir.exists():raise FileExistsError(output_dir)
    train,valid,classes,metadata,verified=load_data(integrated,catalogue_path)
    tr=train.loc[train.primary_topic_id.isin(classes)].copy()
    va=valid.loc[valid.primary_topic_id.isin(classes)].copy()
    original=tr.loc[tr.dataset_origin.eq("original_analytical_sample")].copy()
    expansion=tr.loc[tr.dataset_origin.eq("targeted_ml_expansion")].copy()
    if tr.empty or va.empty or original.empty or expansion.empty:raise ValueError("Ablation cohort empty")
    y=va.primary_topic_id.to_numpy();texts=va.text.tolist()
    predictions={};metrics={};fit_info={};models={}
    majority=tr.primary_topic_id.value_counts().idxmax()
    predictions["majority"]=np.full(len(va),majority,dtype=object)
    predictions["description_match"]=description_predictions(texts,classes,metadata)
    for name in ("majority","description_match"):
        metrics[name]=metric_row(y,predictions[name],classes)
    for source,training in (("original_only",original),("expanded",tr)):
        for name in OPTIONS:
            model,info=tune_model(name,training)
            start=time.perf_counter();pred=model.predict(texts)
            info["validation_predict_ms_per_work"]=1000*(time.perf_counter()-start)/len(va)
            scores=model.predict_proba(texts) if hasattr(model,"predict_proba") else model.decision_function(texts)
            info["top3_agreement"]=float(top_k_accuracy_score(y,scores,k=3,labels=model.named_steps["model"].classes_))
            key=f"{source}_{name}";predictions[key]=pred;metrics[key]=metric_row(y,pred,classes)
            fit_info[key]=info;models[key]=model
    ablation={}
    for name in OPTIONS:
        expanded=f"expanded_{name}";base=f"original_only_{name}"
        ablation[name]={"original":metrics[base],"expanded":metrics[expanded],
                        "paired_bootstrap":paired_bootstrap(y,predictions[expanded],predictions[base],classes)}
    winner=max(OPTIONS,key=lambda name:metrics[f"expanded_{name}"]["macro_f1"])
    chosen_param=fit_info[f"expanded_{winner}"]["selected"]["model__alpha" if winner=="complement_nb" else "model__C"]
    fixed=[]
    for source,training in (("original_only",original),("expanded",tr)):
        model=make_pipeline(winner,chosen_param);model.fit(training.text.tolist(),training.primary_topic_id.tolist())
        fixed.append({"source":source,"n_train":len(training),**metric_row(y,model.predict(texts),classes)})
    learning=[]
    for fraction in (0.,1/3,2/3,1.):
        sampled=stratified_expansion_fraction(expansion,fraction)
        training=pd.concat([original,sampled],ignore_index=True)
        model=make_pipeline(winner,chosen_param);model.fit(training.text.tolist(),training.primary_topic_id.tolist())
        learning.append({"expansion_fraction":fraction,"new_rows":len(sampled),"train_rows":len(training),
                         **metric_row(y,model.predict(texts),classes)})
    features=[]
    for feature in ("title_clean","abstract_clean","text"):
        model=make_pipeline(winner,chosen_param)
        model.fit(tr[feature].tolist(),tr.primary_topic_id.tolist())
        features.append({"feature":feature,**metric_row(y,model.predict(va[feature].tolist()),classes)})
    winner_model=models[f"expanded_{winner}"]
    class_report=classification_report(y,predictions[f"expanded_{winner}"],labels=classes,
                                       output_dict=True,zero_division=0)
    per_class=[{"topic_id":label,"support":int(class_report[label]["support"]),
                "precision":float(class_report[label]["precision"]),
                "recall":float(class_report[label]["recall"]),
                "f1":float(class_report[label]["f1-score"])} for label in classes]
    confusion=confusion_matrix(y,predictions[f"expanded_{winner}"],labels=classes)
    words=winner_model.named_steps["tfidf"].get_feature_names_out()
    estimator=winner_model.named_steps["model"]
    coefficients=getattr(estimator,"coef_",None)
    feature_terms=[]
    if coefficients is not None:
        for label,weight in zip(estimator.classes_,coefficients):
            for rank,ix in enumerate(np.argsort(weight)[-10:][::-1],1):
                feature_terms.append({"topic_id":label,"rank":rank,"term":str(words[ix]),
                                      "coefficient":float(weight[ix])})
    composition=[]
    for origin,group in train.groupby("dataset_origin"):
        composition.append({"origin":origin,"rows":len(group),"selected_rows":int(group.primary_topic_id.isin(classes).sum()),
                            "mean_abstract_words":float(group.abstract_clean.str.split().str.len().mean()),
                            "year_counts":{str(k):int(v) for k,v in group.publication_year.value_counts().sort_index().items()},
                            "type_counts":{str(k):int(v) for k,v in group.work_type.value_counts().items()},
                            "language_counts":{str(k):int(v) for k,v in group.language.fillna("missing").value_counts().items()}})
    output_dir.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".final_p3_stage_",dir=output_dir.parent) as temp:
        stage=Path(temp); (stage/"models").mkdir()
        for key,model in models.items():joblib.dump(model,stage/"models"/f"{key}.joblib",compress=3)
        prediction_table=pd.DataFrame({"work_id":va.work_id.to_numpy(),"true_topic":y,
                "publication_year":va.publication_year.to_numpy(),
                **{f"pred_{key}":value for key,value in predictions.items()}})
        prediction_table.to_parquet(stage/"validation_predictions.parquet",index=False)
        pd.DataFrame(per_class).to_csv(stage/"per_class.csv",index=False)
        pd.DataFrame(confusion,index=classes,columns=classes).to_csv(stage/"confusion.csv")
        pd.DataFrame(learning).to_csv(stage/"learning_curve.csv",index=False)
        pd.DataFrame(features).to_csv(stage/"feature_ablation.csv",index=False)
        pd.DataFrame(fixed).to_csv(stage/"fixed_hyperparameter_ablation.csv",index=False)
        pd.DataFrame(feature_terms).to_csv(stage/"dominant_terms.csv",index=False)
        result={"status":"complete","run_id":output_dir.name,"created_at_utc":datetime.now(timezone.utc).isoformat(),
            "source_scope":"2020-2023 training; original-sample 2024 development validation; 2025 sealed",
            "source_manifest_sha256":file_sha256(integrated/"split_manifest.json"),
            "catalogue_sha256":file_sha256(catalogue_path),"metadata_sha256":file_sha256(Path(yaml.safe_load(catalogue_path.read_text())["source_metadata_csv"])),
            "code_sha256":file_sha256(Path(__file__)),"seed":SEED,"classes":classes,
            "train_original_selected":len(original),"train_expansion_selected":len(expansion),
            "train_expanded_selected":len(tr),"validation_selected":len(va),
            "validation_all_eligible":len(valid),"validation_outside":len(valid)-len(va),
            "metrics":metrics,"fit_info":fit_info,"ablation":ablation,
            "strongest_lightweight_model":winner,"selected_parameter":chosen_param,
            "strict_fixed_hyperparameter_ablation":fixed,"learning_curve":learning,
            "feature_ablation":features,"per_class":per_class,
            "train_composition":composition,"sklearn_version":sklearn.__version__,
            "python_version":platform.python_version(),"embedding_model":"not run; sentence-transformers/torch unavailable locally",
            "human_semantic_validation":"pending real independent ratings","final_2025_test":"SEALED"}
        (stage/"results.json").write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n")
        result["files"]={str(path.relative_to(stage)):{"sha256":file_sha256(path),"bytes":path.stat().st_size}
                         for path in sorted(stage.rglob("*")) if path.is_file()}
        (stage/"manifest.json").write_text(json.dumps({key:result[key] for key in
            ("status","run_id","created_at_utc","source_manifest_sha256","catalogue_sha256",
             "code_sha256","seed","files","final_2025_test")},indent=2)+"\n")
        stage.replace(output_dir)
    return result


def main(argv: list[str]|None=None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--integrated",type=Path,default=INTEGRATED)
    parser.add_argument("--catalogue",type=Path,default=CATALOGUE)
    parser.add_argument("--output-dir",type=Path,required=True)
    args=parser.parse_args(argv)
    result=run(args.integrated,args.catalogue,args.output_dir)
    print(json.dumps({key:result[key] for key in ("status","train_original_selected","train_expansion_selected",
        "validation_selected","strongest_lightweight_model","final_2025_test")},indent=2))
    return 0


if __name__=="__main__":raise SystemExit(main())
