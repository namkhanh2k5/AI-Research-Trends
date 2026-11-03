"""Phase 6B development-only classification, leakage and open-set audit."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import yaml
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score, classification_report, confusion_matrix, f1_score, roc_auc_score,
    top_k_accuracy_score,
)
from sklearn.model_selection import GridSearchCV, StratifiedKFold
from sklearn.naive_bayes import ComplementNB
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC

from ai_research_trends.analysis.load_data import load_verified_tables
from ai_research_trends.ml.topic_pilot import (
    CONFIG, PLAN, POPULATION, PROCESSED, SEED, clean_text, prepare_rows, title_key,
)
from ai_research_trends.preprocessing.validate_tables import file_sha256


CATALOGUE = Path("config/phase6b_catalogue.yaml")
RUN_DEFAULT = Path("data/analysis/phase6b_topic_validation_20261028_v1")


def load_catalogue(path: Path) -> tuple[dict, pd.DataFrame]:
    spec = yaml.safe_load(path.read_text())
    source = Path(spec["source_metadata_csv"])
    if file_sha256(source) != spec["source_metadata_sha256"]:
        raise ValueError("Official topic metadata hash mismatch")
    metadata = pd.read_csv(source)
    if metadata.short_id.duplicated().any() or set(spec["scope_review"]) != set(metadata.short_id):
        raise ValueError("Scope review does not cover exactly the official metadata candidates")
    for catalogue in ("catalogue_a", "catalogue_b"):
        ids = spec[catalogue]
        if len(ids) != len(set(ids)) or not set(ids).issubset(set(metadata.short_id)):
            raise ValueError(f"Invalid {catalogue} IDs")
    if not set(spec["catalogue_a"]).issubset(set(spec["catalogue_b"])):
        raise ValueError("Expanded catalogue must retain the reference five topics")
    if any(spec["scope_review"][i]["status"] != "in" for i in spec["catalogue_b"]):
        raise ValueError("Selected topic has no in-scope review")
    return spec, metadata


def scope_table(eligible_dev: pd.DataFrame, metadata: pd.DataFrame, spec: dict) -> pd.DataFrame:
    counts = eligible_dev.groupby(["primary_topic_id", "publication_year"]).size().unstack(fill_value=0)
    rows = []
    for topic in metadata.itertuples(index=False):
        tid = topic.topic_id
        years = counts.loc[tid] if tid in counts.index else pd.Series(dtype=int)
        train = sum(int(years.get(y, 0)) for y in (2020, 2021, 2022, 2023))
        valid = int(years.get(2024, 0))
        review = spec["scope_review"][topic.short_id]
        if train < spec["minimum_train"] or valid < spec["minimum_validation"]:
            raise ValueError(f"Frozen candidate {topic.short_id} does not meet pre-2025 support")
        rows.append({"topic_id":tid,"short_id":topic.short_id,"topic_name":topic.name,
                     "official_description":topic.description,"primary_subfield":topic.subfield_id,
                     "train_2020_2023":train,"validation_2024":valid,
                     "scope_status":review["status"],"reason":review["reason"],
                     "overlap_concern":review["overlap"],"manual_review_required":True,
                     "catalogue_a":topic.short_id in spec["catalogue_a"],
                     "catalogue_b":topic.short_id in spec["catalogue_b"],
                     "source_url":topic.source_url})
    return pd.DataFrame(rows).sort_values("short_id").reset_index(drop=True)


def exact_and_near_duplicates(eligible_dev: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Cross-period audit with rare-title-token blocking; labels never form blocks."""
    w = eligible_dev.loc[eligible_dev.publication_year.le(2024)].copy()
    w["period"] = np.where(w.publication_year.eq(2024), "validation", "train")
    w["title_key"] = w.title_clean.map(title_key)
    w["text_key"] = w.text.map(lambda value: hashlib.sha256(value.casefold().encode()).hexdigest())
    exact = {"exact_text_cross_period_groups":0,"exact_title_cross_period_groups":0,
             "exact_abstract_cross_period_groups":0,"canonical_doi_cross_period_groups":0}
    for field, key in (("text_key","exact_text_cross_period_groups"),
                       ("title_key","exact_title_cross_period_groups")):
        exact[key] = int((w.groupby(field).period.nunique() > 1).sum())
    exact["exact_abstract_cross_period_groups"] = int((w.loc[w.abstract_clean.ne("")]
        .assign(abstract_key=lambda f:f.abstract_clean.str.casefold())
        .groupby("abstract_key").period.nunique() > 1).sum())
    doi = w.doi.fillna("").str.lower().str.removeprefix("https://doi.org/")
    exact["canonical_doi_cross_period_groups"] = int((w.assign(doi_key=doi).loc[doi.ne("")]
                                                     .groupby("doi_key").period.nunique() > 1).sum())
    train = w.loc[w.period.eq("train"), ["work_id", "title_key", "abstract_clean"]].reset_index(drop=True)
    valid = w.loc[w.period.eq("validation"), ["work_id", "title_key", "abstract_clean"]].reset_index(drop=True)
    stop = {"neural", "network", "learning", "based", "using", "research", "analysis", "method",
            "methods", "model", "models", "deep", "data", "image", "study", "artificial"}
    tokens = lambda x: {t for t in x.split() if len(t) >= 5 and t not in stop}
    train_tokens = [tokens(x) for x in train.title_key]
    valid_tokens = [tokens(x) for x in valid.title_key]
    frequency = Counter(t for ts in train_tokens + valid_tokens for t in ts)
    blocks: dict[str, set[int]] = defaultdict(set)
    for i, ts in enumerate(train_tokens):
        for token in sorted(ts, key=lambda t:(frequency[t],t))[:4]:
            if frequency[token] <= 100:
                blocks[token].add(i)
    candidate_pairs = set()
    for j, ts in enumerate(valid_tokens):
        for token in sorted(ts, key=lambda t:(frequency[t],t))[:4]:
            if frequency[token] <= 100:
                candidate_pairs.update((i,j) for i in blocks.get(token,()))
    pairs = []
    for i,j in sorted(candidate_pairs):
        a,b = train.iloc[i],valid.iloc[j]
        if abs(len(a.title_key)-len(b.title_key)) > .35 * max(len(a.title_key),len(b.title_key),1):
            continue
        tr = SequenceMatcher(None,a.title_key,b.title_key,autojunk=False).ratio()
        if tr < .72:
            continue
        ar = SequenceMatcher(None,a.abstract_clean.casefold(),b.abstract_clean.casefold(),autojunk=False).ratio()
        if tr >= .92 or (tr >= .78 and ar >= .95):
            pairs.append({"train_work_id":a.work_id,"validation_work_id":b.work_id,
                          "title_similarity":tr,"abstract_similarity":ar})
    return pd.DataFrame(pairs,columns=["train_work_id","validation_work_id",
                                       "title_similarity","abstract_similarity"]), {
        **exact,"blocked_candidate_pairs":len(candidate_pairs),"near_duplicate_pairs":len(pairs),
        "near_duplicate_validation_works":len({r["validation_work_id"] for r in pairs}),
        "blocking_limit":"four rare non-stop title tokens, frequency <=100; may miss reworded titles",
    }


def make_pipeline(name: str, parameter: float) -> Pipeline:
    vectorizer = TfidfVectorizer(ngram_range=(1,2), min_df=2, max_features=50000, sublinear_tf=True)
    if name == "complement_nb": model = ComplementNB(alpha=parameter)
    elif name == "logistic_regression": model = LogisticRegression(C=parameter,max_iter=1000,random_state=SEED)
    elif name == "linear_svm": model = LinearSVC(C=parameter,random_state=SEED)
    else: raise ValueError(f"Unknown model: {name}")
    return Pipeline([("tfidf",vectorizer),("model",model)])


def tune_on_training(name: str, train: pd.DataFrame) -> tuple[Pipeline, dict]:
    options = {"complement_nb":[.5,1.,2.],"logistic_regression":[.3,1.,3.],
               "linear_svm":[.3,1.,3.]}[name]
    grid = GridSearchCV(make_pipeline(name,options[0]), {"model__" +
        ("alpha" if name == "complement_nb" else "C"):options},
        cv=StratifiedKFold(3,shuffle=True,random_state=SEED),scoring="f1_macro",n_jobs=1,
        refit=True,error_score="raise")
    start = time.perf_counter()
    grid.fit(train.text.tolist(),train.primary_topic_id.tolist())
    duration = time.perf_counter()-start
    best_fold_scores=[float(grid.cv_results_[f"split{i}_test_score"][grid.best_index_])
                      for i in range(grid.n_splits_)]
    return grid.best_estimator_,{"options":options,"best_params":grid.best_params_,
        "best_training_cv_macro_f1":float(grid.best_score_),
        "candidate_mean_cv_scores":[float(x) for x in grid.cv_results_["mean_test_score"]],
        "best_parameter_fold_scores":best_fold_scores,"fit_search_seconds":duration}


def paired_bootstrap(y: np.ndarray, predictions: dict[str,np.ndarray], a: str, b: str,
                     draws: int=300) -> dict:
    rng=np.random.default_rng(SEED)
    if not len(y): raise ValueError("Empty bootstrap population")
    values={name:{"accuracy":[],"macro_f1":[]} for name in predictions}
    differences=[]
    for _ in range(draws):
        ids=rng.integers(0,len(y),len(y))
        for name,pred in predictions.items():
            values[name]["accuracy"].append(accuracy_score(y[ids],pred[ids]))
            values[name]["macro_f1"].append(f1_score(y[ids],pred[ids],average="macro",zero_division=0))
        differences.append(values[a]["macro_f1"][-1]-values[b]["macro_f1"][-1])
    return {"per_model":{name:{metric:[float(v) for v in np.quantile(samples,[.025,.975])]
            for metric,samples in scores.items()} for name,scores in values.items()},
            "paired_macro_f1_difference":{f"{a}_minus_{b}":
                [float(v) for v in np.quantile(differences,[.025,.975])]},"draws":draws}


def top_three_accuracy(model: Pipeline, texts: list[str], labels: np.ndarray) -> float:
    scores = model.predict_proba(texts) if hasattr(model,"predict_proba") else model.decision_function(texts)
    classes=model.named_steps["model"].classes_
    return float(top_k_accuracy_score(labels,scores,k=min(3,len(classes)),labels=classes))


def evaluate_catalogue(train: pd.DataFrame, valid: pd.DataFrame, metadata: pd.DataFrame,
                       selected_short: list[str], *, tune: bool) -> tuple[dict,dict[str,pd.DataFrame],dict[str,Pipeline]]:
    selected=["https://openalex.org/"+i for i in selected_short]
    tr=train.loc[train.primary_topic_id.isin(selected)].copy()
    va=valid.loc[valid.primary_topic_id.isin(selected)].copy()
    if tr.empty or va.empty: raise ValueError("Empty catalogue split")
    classes=sorted(selected)
    descriptions=dict(zip(metadata.topic_id,metadata.description))
    if any(not descriptions.get(tid) for tid in classes): raise ValueError("Missing official descriptions")
    y=va.primary_topic_id.to_numpy()
    majority=tr.primary_topic_id.value_counts().idxmax()
    predictions={"majority":np.full(len(va),majority,dtype=object)}
    desc=TfidfVectorizer(ngram_range=(1,2),sublinear_tf=True)
    desc_mat=desc.fit_transform([descriptions[tid] for tid in classes])
    from sklearn.metrics.pairwise import cosine_similarity
    scores=cosine_similarity(desc.transform(va.text.tolist()),desc_mat)
    predictions["description_match"]=np.asarray(classes,dtype=object)[scores.argmax(axis=1)]
    models={}; fit_info={}
    for name in ("complement_nb","logistic_regression","linear_svm"):
        if tune:
            model,detail=tune_on_training(name,tr)
        else:
            model=make_pipeline(name,1.)
            start=time.perf_counter(); model.fit(tr.text.tolist(),tr.primary_topic_id.tolist())
            detail={"fixed_parameter":1.,"fit_seconds":time.perf_counter()-start}
        start=time.perf_counter(); predictions[name]=model.predict(va.text.tolist())
        detail["validation_predict_seconds_including_vectorization"]=time.perf_counter()-start
        detail["validation_predict_ms_per_paper"]=1000*detail["validation_predict_seconds_including_vectorization"]/len(va)
        detail["top3_accuracy"]=top_three_accuracy(model,va.text.tolist(),y)
        fit_info[name]=detail; models[name]=model
    metrics={name:{"accuracy":float(accuracy_score(y,pred)),
        "macro_f1":float(f1_score(y,pred,average="macro",zero_division=0)),
        "weighted_f1":float(f1_score(y,pred,average="weighted",zero_division=0))}
        for name,pred in predictions.items()}
    strongest=max(("majority","description_match"),key=lambda name:metrics[name]["macro_f1"])
    uncertainty=paired_bootstrap(y,predictions,"linear_svm","logistic_regression")
    per_class={}; matrices={}
    for name in ("complement_nb","logistic_regression","linear_svm"):
        report=classification_report(y,predictions[name],labels=classes,output_dict=True,zero_division=0)
        per_class[name]=pd.DataFrame([{"topic_id":tid,**report[tid]} for tid in classes])
        matrices[name]=pd.DataFrame(confusion_matrix(y,predictions[name],labels=classes),
                                    index=pd.Index(classes,name="true_topic"),columns=classes)
    results={"selected_topics":classes,"train_rows":len(tr),"validation_rows":len(va),
             "validation_eligible_denominator":len(valid),"coverage_validation":len(va)/len(valid),
             "metrics":metrics,"fit_info":fit_info,"strongest_baseline":strongest,
             "bootstrap":uncertainty,"train_class_counts":tr.primary_topic_id.value_counts().sort_index().to_dict(),
             "validation_class_counts":va.primary_topic_id.value_counts().sort_index().to_dict(),
             "vocabulary_sizes":{name:len(model.named_steps["tfidf"].vocabulary_) for name,model in models.items()}}
    tables={f"{name}_per_class":frame for name,frame in per_class.items()}
    tables.update({f"{name}_confusion":frame for name,frame in matrices.items()})
    tables["validation_predictions"]=pd.DataFrame({"work_id":va.work_id.to_numpy(),
        "true_topic":y,**{f"pred_{name}":pred for name,pred in predictions.items()}})
    return results,tables,models


def coverage_tables(eligible_dev: pd.DataFrame, selected_short: list[str]) -> dict[str,pd.DataFrame]:
    selected={"https://openalex.org/"+i for i in selected_short}
    data=eligible_dev.copy()
    data["in_catalogue"]=data.primary_topic_id.isin(selected)
    data["language_group"]=data.language.fillna("<missing>").map(
        lambda x:x if x in ("en","<missing>") else "other_language")
    outputs={}
    for key,column in (("year","publication_year"),("subfield","primary_subfield_id"),
                       ("work_type","work_type"),("language","language_group")):
        result=data.groupby(column,dropna=False).in_catalogue.agg(["size","sum"]).reset_index()
        result.columns=[column,"eligible_works","in_catalogue_works"]
        result["coverage"]=result.in_catalogue_works/result.eligible_works
        outputs[f"coverage_{key}"]=result.sort_values(column).reset_index(drop=True)
    return outputs


def select_rejection_threshold(scores: np.ndarray, in_catalogue: np.ndarray,
                               false_acceptance_cap: float=.2) -> float:
    """Lowest calibration threshold satisfying the frozen out-of-catalogue FPR cap."""
    scores=np.asarray(scores,dtype=float)
    labels=np.asarray(in_catalogue,dtype=bool)
    if len(scores)!=len(labels) or not labels.any() or labels.all() or not np.isfinite(scores).all():
        raise ValueError("Calibration requires finite scores and both in/out groups")
    if not 0<=false_acceptance_cap<=1: raise ValueError("Invalid FPR cap")
    candidates=np.r_[np.sort(np.unique(scores)), np.nextafter(scores.max(),np.inf)]
    allowed=[float(t) for t in candidates if float((scores[~labels]>=t).mean())<=false_acceptance_cap+1e-12]
    if not allowed: raise ValueError("No valid threshold")
    return min(allowed)


def open_set_metrics(scores: np.ndarray, predicted: np.ndarray, true: np.ndarray,
                     selected: set[str], threshold: float) -> dict:
    scores=np.asarray(scores,dtype=float); predicted=np.asarray(predicted); true=np.asarray(true)
    if not (len(scores)==len(predicted)==len(true)) or len(true)==0:
        raise ValueError("Open-set metric arrays must align and be nonempty")
    inside=np.isin(true,list(selected)); accepted=scores>=threshold
    if not inside.any() or inside.all(): raise ValueError("Need in/out catalogue truth")
    accepted_in=accepted & inside; accepted_out=accepted & ~inside
    correct=accepted_in & (predicted==true)
    return {"total":len(true),"in_catalogue":int(inside.sum()),
        "outside_catalogue":int((~inside).sum()),"threshold":float(threshold),
        "in_acceptance_rate":float(accepted_in.sum()/inside.sum()),
        "out_false_acceptance_rate":float(accepted_out.sum()/(~inside).sum()),
        "in_false_rejection_rate":float((inside & ~accepted).sum()/inside.sum()),
        "auroc_in_vs_out":float(roc_auc_score(inside,scores)),
        "accepted_precision_in_catalogue":float(accepted_in.sum()/max(1,accepted.sum())),
        "accuracy_among_accepted_in":float(correct.sum()/max(1,accepted_in.sum())),
        "selective_risk":float(1-correct.sum()/max(1,accepted_in.sum())),
        "selective_coverage_in":float(accepted_in.sum()/inside.sum()),
        "end_to_end_correct_placement":float(correct.sum()/len(true)),
        "accepted_in":int(accepted_in.sum()),"accepted_out":int(accepted_out.sum()),
        "correct_accepted_in":int(correct.sum())}


def stable_group_split(valid: pd.DataFrame, selected: set[str], fraction: float=.4
                       ) -> tuple[pd.DataFrame,pd.DataFrame]:
    """Stratified deterministic split by version-group hash, never by topic text."""
    if not 0 < fraction < 1 or valid.version_group.duplicated().any():
        raise ValueError("Invalid fraction or duplicate version group")
    strata=valid.primary_topic_id.where(valid.primary_topic_id.isin(selected),"OUT")
    calibration_ids=[]
    for _,group in valid.groupby(strata,sort=True):
        ordered=sorted(group.index, key=lambda index:hashlib.sha256(
            f"{SEED}:{valid.at[index,'version_group']}".encode()).hexdigest())
        count=max(1,min(len(ordered)-1,round(len(ordered)*fraction))) if len(ordered)>1 else 0
        calibration_ids.extend(ordered[:count])
    calibration=valid.loc[calibration_ids].sort_values("work_id")
    evaluation=valid.drop(index=calibration_ids).sort_values("work_id")
    if set(calibration.version_group) & set(evaluation.version_group):
        raise ValueError("Version-group leakage across calibration/evaluation")
    return calibration,evaluation


def evaluate_open_set(valid: pd.DataFrame, selected_short: list[str],
                      svm: Pipeline, logistic: Pipeline) -> tuple[dict,dict[str,pd.DataFrame],pd.DataFrame,pd.DataFrame]:
    selected={"https://openalex.org/"+i for i in selected_short}
    calibration,evaluation=stable_group_split(valid,selected)
    results={}; tables={}
    for name,model in (("svm_max_decision",svm),("logistic_max_probability",logistic)):
        if name.startswith("svm"):
            score_fn=lambda text:np.max(model.decision_function(text),axis=1)
        else:
            score_fn=lambda text:np.max(model.predict_proba(text),axis=1)
        cal_scores=score_fn(calibration.text.tolist())
        eval_scores=score_fn(evaluation.text.tolist())
        threshold=select_rejection_threshold(cal_scores,calibration.primary_topic_id.isin(selected).to_numpy())
        cal_pred=model.predict(calibration.text.tolist())
        eval_pred=model.predict(evaluation.text.tolist())
        results[name]={"calibration":open_set_metrics(cal_scores,cal_pred,
            calibration.primary_topic_id.to_numpy(),selected,threshold),
            "evaluation":open_set_metrics(eval_scores,eval_pred,
            evaluation.primary_topic_id.to_numpy(),selected,threshold),
            "threshold_source":"2024 calibration only; <=20% outside false acceptance constraint",
            "score_interpretation":"raw SVM decision score, not probability" if name.startswith("svm")
             else "uncalibrated Logistic Regression maximum probability; diagnostic"}
        tables[f"{name}_evaluation_predictions"]=pd.DataFrame({"work_id":evaluation.work_id,
            "true_topic":evaluation.primary_topic_id,"predicted_topic":eval_pred,
            "score":eval_scores,"accepted":eval_scores>=threshold})
    return results,tables,calibration,evaluation


def svm_ablation_and_terms(train: pd.DataFrame, valid: pd.DataFrame,
                           model: Pipeline) -> tuple[pd.DataFrame,pd.DataFrame]:
    results=[]
    for feature in ("title_clean","abstract_clean"):
        candidate=make_pipeline("linear_svm",1.)
        candidate.fit(train[feature].tolist(),train.primary_topic_id.tolist())
        pred=candidate.predict(valid[feature].tolist())
        results.append({"features":feature,"validation_rows":len(valid),
            "accuracy":accuracy_score(valid.primary_topic_id,pred),
            "macro_f1":f1_score(valid.primary_topic_id,pred,average="macro",zero_division=0)})
    combined=model.predict(valid.text.tolist())
    results.append({"features":"title_plus_abstract","validation_rows":len(valid),
        "accuracy":accuracy_score(valid.primary_topic_id,combined),
        "macro_f1":f1_score(valid.primary_topic_id,combined,average="macro",zero_division=0)})
    words=model.named_steps["tfidf"].get_feature_names_out()
    svm=model.named_steps["model"]
    rows=[]
    for label,coefficients in zip(svm.classes_,svm.coef_):
        for rank,idx in enumerate(np.argsort(coefficients)[-15:][::-1],1):
            rows.append({"topic_id":label,"rank":rank,"term":words[idx],"coefficient":float(coefficients[idx])})
    return pd.DataFrame(results),pd.DataFrame(rows)


def make_annotation_sheets(calibration: pd.DataFrame, evaluation: pd.DataFrame,
                           metadata: pd.DataFrame, selected_short: list[str]) -> dict[str,pd.DataFrame]:
    catalogue=metadata.loc[metadata.short_id.isin(selected_short)].sort_values("short_id")
    options={r.short_id:f"{r.short_id} — {r.name}: {r.description}" for r in catalogue.itertuples()}
    out={}
    rng=np.random.default_rng(SEED)
    for purpose,frame,number in (("calibration",calibration,40),("evaluation",evaluation,100)):
        picked=frame.sample(n=min(number,len(frame)),random_state=SEED+len(frame)).sort_values("work_id")
        rows=[]; keys=[]
        for pos,row in enumerate(picked.itertuples(),1):
            example=f"P6B-{purpose[:3].upper()}-{pos:03d}"
            choice_order=list(selected_short); rng.shuffle(choice_order)
            rows.append({"example_id":example,"title":row.title_clean,"abstract":row.abstract_clean,
                         "randomized_topic_options":" | ".join(options[tid] for tid in choice_order),
                         "best_topic":"","second_plausible_topic":"","none_of_these":"",
                         "unclear_insufficient_information":"","reviewer_note":""})
            keys.append({"example_id":example,"work_id":row.work_id,
                         "openalex_primary_topic":row.primary_topic_id})
        out[f"blind_{purpose}"]=pd.DataFrame(rows)
        out[f"restricted_key_{purpose}"]=pd.DataFrame(keys)
    return out


def topic_brief_data(works: pd.DataFrame, metadata: pd.DataFrame,
                     selected_short: list[str]) -> dict:
    """Development-period sampled-work context only; no population extrapolation."""
    details={}
    for short in selected_short:
        tid="https://openalex.org/"+short
        rows=works.loc[works.publication_year.le(2024) & works.primary_topic_id.eq(tid)]
        meta=metadata.loc[metadata.short_id.eq(short)].iloc[0]
        examples=rows.loc[rows.publication_year.eq(2024) & rows.title.notna()].sort_values(
            ["publication_date","work_id"],ascending=[False,True]).head(3)
        details[tid]={"topic_id":tid,"name":meta["name"],"description":meta["description"],
            "source":"Phase 3 detailed sample, 2020–2024 only; not full population estimates",
            "sample_works":len(rows),"sample_year_counts":{str(k):int(v) for k,v in rows.publication_year.value_counts().sort_index().items()},
            "sample_median_citations":float(rows.cited_by_count.median()) if len(rows) else None,
            "sample_oa_status_counts":{str(k):int(v) for k,v in rows.oa_status.fillna("<missing>").value_counts().items()},
            "sample_example_papers":[{"work_id":r.work_id,"title":r.title} for r in examples.itertuples()],
            "population_primary_topic_count":None,"core_literature":"not available for this exact primary-topic catalogue"}
    return details


def _store_csv(frame: pd.DataFrame, path: Path) -> dict:
    frame.to_csv(path,index=frame.index.name is not None)
    return {"sha256":file_sha256(path),"bytes":path.stat().st_size,"rows":len(frame),"path":str(path)}


def main(argv: list[str]|None=None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--processed-dir",type=Path,default=PROCESSED)
    parser.add_argument("--plan",type=Path,default=PLAN)
    parser.add_argument("--population",type=Path,default=POPULATION)
    parser.add_argument("--config",type=Path,default=CONFIG)
    parser.add_argument("--catalogue",type=Path,default=CATALOGUE)
    parser.add_argument("--output-dir",type=Path,default=RUN_DEFAULT)
    args=parser.parse_args(argv)
    if args.output_dir.exists(): parser.error("Output already exists; choose a new versioned run")
    tables,source_manifest,_=load_verified_tables(args.processed_dir,args.plan,args.population,args.config)
    spec,metadata=load_catalogue(args.catalogue)
    works=tables["works"]
    # Never inspect 2025 labels or model predictions during catalogue selection/development.
    development_works=works.loc[works.publication_year.le(2024)].copy()
    eligible,audit=prepare_rows(development_works)
    scope=scope_table(eligible,metadata,spec)
    train=eligible.loc[eligible.publication_year.le(2023)].copy()
    valid=eligible.loc[eligible.publication_year.eq(2024)].copy()
    if set(train.version_group) & set(valid.version_group): raise ValueError("Version leakage")
    pairs,duplicate_audit=exact_and_near_duplicates(eligible)
    results={}; output_tables={"scope_review":scope,"near_duplicate_pairs_private":pairs}
    models={}; predictions={}
    for label,key in (("A","catalogue_a"),("B","catalogue_b")):
        selected=spec[key]
        result,frames,fitted=evaluate_catalogue(train,valid,metadata,selected,tune=(label=="B"))
        result["coverage_training"]=result["train_rows"]/len(train)
        results[label]=result; models[label]=fitted; predictions[label]=frames["validation_predictions"]
        output_tables.update({f"catalogue_{label.lower()}_{name}":frame for name,frame in frames.items()})
        output_tables.update({f"catalogue_{label.lower()}_{name}":frame for name,frame in
                              coverage_tables(eligible,selected).items()})
    a_selected={"https://openalex.org/"+i for i in spec["catalogue_a"]}
    a_train=train.loc[train.primary_topic_id.isin(a_selected)]
    a_valid=valid.loc[valid.primary_topic_id.isin(a_selected)]
    ablation,terms=svm_ablation_and_terms(a_train,a_valid,models["A"]["linear_svm"])
    output_tables["catalogue_a_svm_ablation"]=ablation
    output_tables["catalogue_a_svm_top_terms"]=terms
    near_ids=set(pairs.validation_work_id)
    sensitivity={}
    for label in ("A","B"):
        frame=predictions[label]
        clean=frame.loc[~frame.work_id.isin(near_ids)]
        sensitivity[label]={"removed_validation_works":len(frame)-len(clean),
            "svm_macro_f1_after_removal":float(f1_score(clean.true_topic,clean.pred_linear_svm,
                average="macro",zero_division=0)) if len(clean) else None}
    selected_b=spec["catalogue_b"]
    open_set,open_tables,calibration,evaluation=evaluate_open_set(
        valid,selected_b,models["B"]["linear_svm"],models["B"]["logistic_regression"])
    output_tables.update(open_tables)
    output_tables.update(make_annotation_sheets(calibration,evaluation,metadata,selected_b))
    brief=topic_brief_data(development_works,metadata,selected_b)
    args.output_dir.mkdir(parents=True,exist_ok=False)
    (args.output_dir/"manifest.json").write_text(json.dumps({"status":"incomplete"})+"\n")
    outputs={name:_store_csv(frame,args.output_dir/f"{name}.csv") for name,frame in output_tables.items()}
    model_path=args.output_dir/"catalogue_b_linear_svm.joblib"
    joblib.dump(models["B"]["linear_svm"],model_path)
    outputs["catalogue_b_linear_svm"]={"path":str(model_path),"sha256":file_sha256(model_path),
        "bytes":model_path.stat().st_size}
    brief_path=args.output_dir/"topic_briefs.json"
    brief_path.write_text(json.dumps(brief,ensure_ascii=False,indent=2)+"\n")
    outputs["topic_briefs"]={"path":str(brief_path),"sha256":file_sha256(brief_path),"bytes":brief_path.stat().st_size}
    summary={"status":"complete","run_at_utc":datetime.now(timezone.utc).isoformat(),
        "protocol_commit":"dd437f837dc27ae9a622fe29cf8053f974d24c00",
        "source_manifest_sha256":file_sha256(args.processed_dir/"manifest.json"),
        "source_work_sha256":file_sha256(args.processed_dir/"works.parquet"),
        "source_topic_sha256":file_sha256(args.processed_dir/"work_topics.parquet"),
        "catalogue_sha256":file_sha256(args.catalogue),"metadata_sha256":file_sha256(Path(spec["source_metadata_csv"])),
        "source_manifest_status":source_manifest["status"],"development_works":len(development_works),
        "eligible_development":len(eligible),"train_eligible":len(train),"validation_eligible":len(valid),
        "duplicate_audit":duplicate_audit,"near_duplicate_sensitivity":sensitivity,
        "catalogues":results,"open_set":open_set,"human_semantic_validation":"pending",
        "test_2025":"sealed_not_evaluated","outputs":outputs}
    (args.output_dir/"manifest.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"catalogue_metrics":{k:v["metrics"] for k,v in results.items()},
                      "catalogue_coverage":{k:v["coverage_validation"] for k,v in results.items()},
                      "open_set":open_set,"duplicate_audit":duplicate_audit},indent=2))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
