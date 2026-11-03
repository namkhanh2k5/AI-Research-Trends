"""Bounded, leakage-audited Phase 6A OpenAlex silver-label classification pilot."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
from sklearn.naive_bayes import ComplementNB
from sklearn.svm import LinearSVC
from sklearn.metrics.pairwise import cosine_similarity

from ai_research_trends.analysis.load_data import load_verified_tables
from ai_research_trends.preprocessing.validate_tables import file_sha256


VERSION = "phase6a-v2"
SEED = 20261028
PROCESSED = Path("data/processed/openalex_stratified/stratified_20261019T155909Z")
PLAN = Path("data/metadata/phase2_sampling_plan.json")
POPULATION = Path("data/metadata/population_counts_pre_phase2.json")
CONFIG = Path("config/topics.yaml")
CATALOGUE = Path("config/phase6_topic_catalogue.yaml")

# Provisional semantic review of actual observed names. Other topics remain pending
# human review, not algorithmically deemed out of scope.
SCOPE = {
    "T10036": ("in", "neural-network methods within the CV primary subfield"),
    "T10028": ("in", "topic modelling is a core NLP method; broad label"),
    "T10664": ("in", "sentiment/opinion analysis is an NLP task"),
    "T10052": ("in", "image segmentation is a CV method, albeit medical-specific"),
    "T10462": ("in", "reinforcement learning is a core AI method; robotics-specific"),
    "T10020": ("out", "quantum information/cryptography is not primarily AI/CV"),
    "T10682": ("out", "quantum-computing architecture is not primarily AI/CV"),
    "T10764": ("manual_review", "privacy technologies are broad, not necessarily AI methodology"),
    "T10862": ("manual_review", "cancer-detection application overlaps CV/medical imaging"),
}


def topic_short(topic_id: str) -> str:
    match = re.fullmatch(r"https://openalex\.org/(T\d+)", str(topic_id))
    if not match:
        raise ValueError(f"Invalid canonical OpenAlex topic ID: {topic_id!r}")
    return match.group(1)


def clean_text(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    return " ".join(unicodedata.normalize("NFC", str(value)).split())


def title_key(title: str) -> str:
    return re.sub(r"[^\w]+", " ", clean_text(title).casefold(), flags=re.UNICODE).strip()


def version_groups(frame: pd.DataFrame) -> pd.DataFrame:
    """Union DOI and normalized-title matches without consulting any topic label."""
    if frame.work_id.isna().any() or not frame.work_id.is_unique:
        raise ValueError("Work IDs must be unique and non-null")
    out = frame[["work_id", "doi", "title", "publication_year"]].copy().sort_values("work_id")
    ids = out.work_id.tolist()
    parent = {wid: wid for wid in ids}

    def root(wid: str) -> str:
        while parent[wid] != wid:
            parent[wid] = parent[parent[wid]]
            wid = parent[wid]
        return wid

    def union(a: str, b: str) -> None:
        a, b = root(a), root(b)
        parent[max(a, b)] = min(a, b)

    seen: dict[str, str] = {}
    for row in out.itertuples(index=False):
        keys = []
        if pd.notna(row.doi) and clean_text(row.doi):
            keys.append("doi:" + clean_text(row.doi).casefold().removeprefix("https://doi.org/"))
        key = title_key(row.title)
        if len(key) >= 20:
            keys.append("title:" + key)
        for k in keys:
            if k in seen:
                union(row.work_id, seen[k])
            else:
                seen[k] = row.work_id
    out["version_group"] = [root(wid) for wid in ids]
    return out[["work_id", "version_group"]]


def prepare_rows(works: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Keep earliest version per group, then require both original text fields."""
    required = {"work_id", "doi", "title", "abstract", "publication_year", "primary_topic_id"}
    if not required.issubset(works.columns):
        raise ValueError(f"Missing required columns: {sorted(required - set(works.columns))}")
    w = works.copy()
    if w.primary_topic_id.isna().any():
        raise ValueError("Missing primary topic labels must be audited before training")
    w["title_clean"] = w.title.map(clean_text)
    w["abstract_clean"] = w.abstract.map(clean_text)
    w = w.merge(version_groups(w), on="work_id", validate="one_to_one")
    w["has_text"] = w.title_clean.ne("") & w.abstract_clean.ne("")
    w = w.sort_values(["publication_year", "work_id"]).reset_index(drop=True)
    w["is_first_version"] = ~w.version_group.duplicated()
    w["eligible"] = w.has_text & w.is_first_version
    w["exclusion_reason"] = np.select(
        [~w.has_text, ~w.is_first_version], ["missing_title_or_abstract", "later_version"], default="eligible"
    )
    conflicts = w.groupby("version_group").primary_topic_id.nunique()
    w["group_has_label_conflict"] = w.version_group.map(conflicts).gt(1)
    # Text is never copied into audit output; it remains only in local ML splits.
    audit = w[["work_id", "publication_year", "primary_topic_id", "version_group",
               "has_text", "is_first_version", "eligible", "exclusion_reason",
               "group_has_label_conflict"]].copy()
    eligible = w.loc[w.eligible].copy()
    eligible["text"] = eligible.title_clean + "\n" + eligible.abstract_clean
    if eligible.version_group.duplicated().any():
        raise ValueError("Version groups are not isolated")
    return eligible, audit


def audit_topics(works: pd.DataFrame, topics: pd.DataFrame, audit: pd.DataFrame,
                 descriptions: dict[str,str] | None = None) -> dict[str, pd.DataFrame]:
    if topics.duplicated(["work_id", "topic_id"]).any():
        raise ValueError("Duplicate topic relationships")
    ranked = topics.loc[topics.topic_rank.eq(1)].copy()
    if ranked.work_id.duplicated().any() or len(ranked) != len(works):
        raise ValueError("Missing or duplicate rank-1 topic")
    check = works[["work_id", "primary_topic_id"]].merge(
        ranked[["work_id", "topic_id"]], on="work_id", validate="one_to_one"
    )
    if not check.primary_topic_id.eq(check.topic_id).all():
        raise ValueError("Primary topic disagrees with rank-1 relationship")
    merged = works.merge(ranked[["work_id", "topic_name", "topic_score", "subfield_id"]],
                         on="work_id", validate="one_to_one")
    merged["has_title"] = merged.title.map(clean_text).ne("")
    merged["has_abstract"] = merged.abstract.map(clean_text).ne("")
    merged["has_both"] = merged.has_title & merged.has_abstract
    merged["low_score_lt_0_5"] = merged.topic_score.lt(.5)
    grouped = merged.groupby("primary_topic_id", sort=True)
    summary = grouped.agg(topic_name=("topic_name", "first"), primary_subfield=("subfield_id", "first"),
                          sample_works=("work_id", "size"), with_title=("has_title", "sum"),
                          with_abstract=("has_abstract", "sum"), with_both=("has_both", "sum"),
                          score_median=("topic_score", "median"), score_p10=("topic_score", lambda x:x.quantile(.1)),
                          score_p90=("topic_score", lambda x:x.quantile(.9)),
                          low_score_share=("low_score_lt_0_5", "mean")).reset_index()
    summary["missing_abstract_pct"] = 100 * (1 - summary.with_abstract / summary.sample_works)
    summary["topic_description"] = summary.primary_topic_id.map(descriptions or {})
    # Descriptions absent from Phase 3 are deliberately left null, not inferred.
    base = merged[["work_id", "primary_topic_id", "publication_year", "work_type", "language", "has_abstract"]]
    by_year = base.groupby(["primary_topic_id", "publication_year"]).agg(works=("work_id", "size"),
        missing_abstract=("has_abstract", lambda x: int((~x).sum()))).reset_index()
    by_type = base.groupby(["primary_topic_id", "work_type"]).size().rename("works").reset_index()
    by_language = base.assign(language=base.language.fillna("<missing>")).groupby(
        ["primary_topic_id", "language"]).size().rename("works").reset_index()
    secondary = topics.loc[topics.topic_rank.between(2,3), ["work_id", "topic_id", "topic_rank"]].merge(
        check[["work_id", "primary_topic_id"]], on="work_id", validate="many_to_one")
    cooccurrence = secondary.groupby(["primary_topic_id", "topic_id", "topic_rank"]).size().rename("works").reset_index()
    support = audit.loc[audit.eligible].groupby(["primary_topic_id", "publication_year"]).size().unstack(fill_value=0)
    summary["train_usable"] = summary.primary_topic_id.map(support.reindex(columns=[2020,2021,2022,2023],fill_value=0).sum(axis=1)).fillna(0).astype(int)
    summary["validation_usable"] = summary.primary_topic_id.map(support.get(2024,pd.Series(dtype=int))).fillna(0).astype(int)
    # No 2025 counts enter selection or selection output.
    return {"topic_summary":summary, "topic_by_year":by_year, "topic_by_type":by_type,
            "topic_by_language":by_language, "top3_cooccurrence":cooccurrence}


def select_catalogue(summary: pd.DataFrame, descriptions: dict[str,str]) -> tuple[pd.DataFrame, list[str]]:
    rows = []
    for row in summary.itertuples(index=False):
        short = topic_short(row.primary_topic_id)
        scope, reason = SCOPE.get(short, ("manual_review", "scope needs independent semantic review"))
        support = row.train_usable >= 120 and row.validation_usable >= 30
        rows.append({"topic_id":row.primary_topic_id, "topic_name":row.topic_name,
                     "description":descriptions.get(row.primary_topic_id), "subfield_id":row.primary_subfield,
                     "scope_status":scope,"reason":reason,"manual_review_required":scope=="manual_review",
                     "train_usable":int(row.train_usable),"validation_usable":int(row.validation_usable),
                     "passes_support":bool(support),"provisional_selected":bool(scope=="in" and support)})
    review = pd.DataFrame(rows).sort_values("topic_id").reset_index(drop=True)
    selected = review.loc[review.provisional_selected].sort_values(
        ["train_usable", "topic_id"], ascending=[False,True]).head(15).topic_id.tolist()
    return review, selected


def split_catalogue(eligible: pd.DataFrame, selected: list[str]) -> tuple[pd.DataFrame,pd.DataFrame,pd.DataFrame,pd.DataFrame]:
    if len(selected) != len(set(selected)) or not selected:
        raise ValueError("Empty or repeated selected labels")
    train = eligible.loc[eligible.publication_year.between(2020,2023) & eligible.primary_topic_id.isin(selected)].copy()
    valid = eligible.loc[eligible.publication_year.eq(2024) & eligible.primary_topic_id.isin(selected)].copy()
    outside = eligible.loc[eligible.publication_year.eq(2024) & ~eligible.primary_topic_id.isin(selected)].copy()
    locked = eligible.loc[eligible.publication_year.eq(2025), ["work_id","version_group"]].copy()
    sets = [set(x.version_group) for x in (train,valid,outside,locked)]
    if any(sets[i] & sets[j] for i in range(4) for j in range(i+1,4)):
        raise ValueError("Version group crosses temporal splits")
    return train,valid,outside,locked


def bootstrap_metrics(y: np.ndarray, predictions: dict[str,np.ndarray], seed: int=SEED, draws: int=200) -> dict:
    rng = np.random.default_rng(seed)
    result = {}
    for name,pred in predictions.items():
        if len(pred) != len(y): raise ValueError("Prediction length mismatch")
        acc=[]; macro=[]
        for _ in range(draws):
            ids=rng.integers(0,len(y),len(y))
            acc.append(accuracy_score(y[ids],pred[ids]))
            macro.append(f1_score(y[ids],pred[ids],average="macro",zero_division=0))
        result[name]={"accuracy_ci95":np.quantile(acc,[.025,.975]).tolist(),
                      "macro_f1_ci95":np.quantile(macro,[.025,.975]).tolist()}
    return result


def open_set_diagnostic(in_prob: np.ndarray, out_prob: np.ndarray, threshold: float=.5) -> dict:
    """Illustrative threshold counts only; probabilities are not calibrated."""
    if len(in_prob)==0 or not 0<=threshold<=1:
        raise ValueError("Need in-catalogue scores and a threshold in [0,1]")
    if np.any(~np.isfinite(in_prob)) or np.any(~np.isfinite(out_prob)):
        raise ValueError("Nonfinite open-set score")
    return {"threshold":threshold,"in_catalogue":len(in_prob),"outside_catalogue":len(out_prob),
            "in_median_max_probability":float(np.median(in_prob)),
            "outside_median_max_probability":float(np.median(out_prob)) if len(out_prob) else None,
            "incorrectly_rejected_in":int((in_prob<threshold).sum()),
            "confidently_assigned_outside":int((out_prob>=threshold).sum())}


def fit_training_vectorizer(train_text: list[str], other_text: list[str]) -> tuple[TfidfVectorizer,object,object]:
    """Fit vocabulary/IDF only on training documents; transform the other split."""
    vectorizer=TfidfVectorizer(ngram_range=(1,2),min_df=2,max_features=50000,sublinear_tf=True)
    Xtr=vectorizer.fit_transform(train_text)
    return vectorizer,Xtr,vectorizer.transform(other_text)


def run_models(train: pd.DataFrame, valid: pd.DataFrame, outside: pd.DataFrame,
               selected: list[str], descriptions: dict[str,str]) -> tuple[dict,dict[str,pd.DataFrame]]:
    if len(selected)<4 or min(train.primary_topic_id.value_counts().reindex(selected,fill_value=0))<120 or min(valid.primary_topic_id.value_counts().reindex(selected,fill_value=0))<30:
        raise ValueError("Insufficient topic-class support for diagnostic model")
    xtr=train.text.tolist(); xv=valid.text.tolist(); ytr=train.primary_topic_id.to_numpy(); yv=valid.primary_topic_id.to_numpy()
    majority=Counter(ytr).most_common(1)[0][0]
    predictions={"majority":np.full(len(yv),majority,dtype=object)}
    predict_seconds={"majority":0.0}
    if all(descriptions.get(tid) for tid in selected):
        start=time.perf_counter()
        descriptor=TfidfVectorizer(ngram_range=(1,2),sublinear_tf=True)
        dmat=descriptor.fit_transform([descriptions[tid] for tid in selected])
        sim=cosine_similarity(descriptor.transform(xv),dmat)
        predictions["description_match"]=np.asarray(selected,dtype=object)[sim.argmax(axis=1)]
        predict_seconds["description_match"]=time.perf_counter()-start
    start=time.perf_counter(); vectorizer,Xtr,Xv=fit_training_vectorizer(xtr,xv)
    fit_seconds={"tfidf":time.perf_counter()-start}
    start=time.perf_counter(); Xv=vectorizer.transform(xv)
    validation_vectorize_seconds=time.perf_counter()-start
    models={"logistic_regression":LogisticRegression(C=1,max_iter=1000,random_state=SEED),
            "complement_nb":ComplementNB(),"linear_svm":LinearSVC(random_state=SEED)}
    logistic=None
    for name,model in models.items():
        start=time.perf_counter(); model.fit(Xtr,ytr); fit_seconds[name]=time.perf_counter()-start
        start=time.perf_counter(); predictions[name]=model.predict(Xv)
        predict_seconds[name]=time.perf_counter()-start
        if name=="logistic_regression": logistic=model
    metrics={name:{"accuracy":float(accuracy_score(yv,pred)),
                   "macro_f1":float(f1_score(yv,pred,average="macro",zero_division=0)),
                   "weighted_f1":float(f1_score(yv,pred,average="weighted",zero_division=0))}
             for name,pred in predictions.items()}
    report=classification_report(yv,predictions["logistic_regression"],labels=selected,output_dict=True,zero_division=0)
    per_class=pd.DataFrame([{"topic_id":tid,**report[tid]} for tid in selected])
    cm=pd.DataFrame(confusion_matrix(yv,predictions["logistic_regression"],labels=selected),index=selected,columns=selected)
    probs_in=logistic.predict_proba(Xv).max(axis=1)
    probs_out=logistic.predict_proba(vectorizer.transform(outside.text.tolist())).max(axis=1) if len(outside) else np.array([])
    threshold=.5  # diagnostic only; no calibration claim
    open_set=open_set_diagnostic(probs_in,probs_out,threshold)
    bci=bootstrap_metrics(yv,predictions)
    best_baseline=max((name for name in predictions if name in {"majority","description_match"}),
                      key=lambda name:metrics[name]["macro_f1"])
    rng=np.random.default_rng(SEED+1)
    paired_diffs=[]
    for _ in range(200):
        draw=rng.integers(0,len(yv),len(yv))
        paired_diffs.append(f1_score(yv[draw],predictions["logistic_regression"][draw],
                                    average="macro",zero_division=0)-
                            f1_score(yv[draw],predictions[best_baseline][draw],
                                     average="macro",zero_division=0))
    result={"metrics":metrics,"per_class":per_class.to_dict("records"),"open_set":open_set,
            "bootstrap_ci":bci,"strongest_baseline":best_baseline,
            "logistic_macro_f1_minus_baseline_ci95":np.quantile(paired_diffs,[.025,.975]).tolist(),
            "fit_seconds":fit_seconds,"predict_seconds_total_2024_validation":predict_seconds,
            "predict_ms_per_validation_work":{k:1000*v/len(valid) for k,v in predict_seconds.items()},
            "validation_vectorize_seconds":validation_vectorize_seconds,
            "end_to_end_ms_per_validation_work":{
                k:1000*(validation_vectorize_seconds+predict_seconds[k])/len(valid)
                for k in models},
            "vocabulary_size":len(vectorizer.vocabulary_),
            "vectorizer_fit_rows":len(train),"validation_transform_rows":len(valid),"test_transform_rows":0,
            "model_feature_columns":["title","abstract"]}
    return result,{"per_class":per_class,"confusion_matrix":cm,
                   "validation_predictions":pd.DataFrame({"work_id":valid.work_id,"true_topic":yv,
                       "predicted_topic":predictions["logistic_regression"],"max_probability":probs_in})}


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    frame.to_csv(path,index=True if frame.index.name is not None else False)


def main(argv: list[str]|None=None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--processed-dir",type=Path,default=PROCESSED)
    parser.add_argument("--plan",type=Path,default=PLAN)
    parser.add_argument("--population",type=Path,default=POPULATION)
    parser.add_argument("--config",type=Path,default=CONFIG)
    parser.add_argument("--catalogue",type=Path,default=CATALOGUE)
    parser.add_argument("--output-dir",type=Path,default=Path("data/analysis/phase6_topic_pilot_20261028_v2"))
    args=parser.parse_args(argv)
    if args.output_dir.exists():
        parser.error(f"Output already exists; choose a new versioned directory: {args.output_dir}")
    tables,source_manifest,_=load_verified_tables(args.processed_dir,args.plan,args.population,args.config)
    works,topics=tables["works"],tables["work_topics"]
    catalogue=yaml.safe_load(args.catalogue.read_text())
    descriptions={"https://openalex.org/"+row["id"]:row["description"] for row in catalogue["topics"]}
    if len(descriptions)!=len(catalogue["topics"]):
        raise ValueError("Repeated topic description")
    eligible,exclusions=prepare_rows(works)
    audits=audit_topics(works,topics,exclusions,descriptions)
    review,selected=select_catalogue(audits["topic_summary"],descriptions)
    if not 4<=len(selected)<=15:
        raise ValueError(f"No diagnostic: {len(selected)} supported, in-scope topics")
    train,valid,outside,locked=split_catalogue(eligible,selected)
    if set(selected)!=set(descriptions):
        raise ValueError("Catalogue descriptions do not match support-selected topic IDs")
    result,model_tables=run_models(train,valid,outside,selected,descriptions)
    ranked_scores=topics.loc[topics.topic_rank.eq(1),["work_id","topic_score"]]
    model_tables["validation_predictions"]=model_tables["validation_predictions"].merge(
        ranked_scores,on="work_id",validate="one_to_one")
    args.output_dir.mkdir(parents=True,exist_ok=False)
    outputs={}
    for name,frame in {**audits,"scope_review":review,"exclusion_audit":exclusions,
                       "train":train[["work_id","version_group","publication_year","primary_topic_id","text"]],
                       "validation":valid[["work_id","version_group","publication_year","primary_topic_id","text"]],
                       "locked_test_ids":locked,**model_tables}.items():
        path=args.output_dir/f"{name}.csv"; _write_csv(frame,path); outputs[name]={"path":str(path),"sha256":file_sha256(path),"rows":len(frame)}
    # Anonymous, blind local sheet and a separate answer key. Never commit either.
    sample=valid.sample(n=min(36,len(valid)),random_state=SEED).sort_values("work_id")
    annotation=pd.DataFrame({"example_id":[f"P6A-{i:03d}" for i in range(1,len(sample)+1)],
        "title":sample.title_clean.tolist(),"abstract":sample.abstract_clean.tolist(),
        "acceptable_topic_choices":"; ".join(review.loc[review.topic_id.isin(selected),"topic_name"]),
        "topic_descriptions":" | ".join(f"{tid}: {descriptions[tid]}" for tid in selected),
        "best_topic_choice":"",
        "none_of_these":"","unclear_insufficient_information":""})
    answers=pd.DataFrame({"example_id":annotation.example_id,"work_id":sample.work_id.tolist(),
                          "openalex_primary_topic":sample.primary_topic_id.tolist()})
    for name,frame in (("blind_annotation_template",annotation),("restricted_answer_key",answers)):
        path=args.output_dir/f"{name}.csv"; _write_csv(frame,path); outputs[name]={"path":str(path),"sha256":file_sha256(path),"rows":len(frame)}
    fig,ax=plt.subplots(figsize=(9,5)); top=audits["topic_summary"].nlargest(25,"sample_works")
    ax.barh(top.topic_name.iloc[::-1],top.sample_works.iloc[::-1]); ax.set_xlabel("Sampled works (not population counts)")
    fig.tight_layout(); fig.savefig(args.output_dir/"topic_support.png",dpi=170); plt.close(fig)
    outputs["topic_support"]={"path":str(args.output_dir/"topic_support.png"),"sha256":file_sha256(args.output_dir/"topic_support.png")}
    outcome={"run_version":VERSION,"run_at_utc":datetime.now(timezone.utc).isoformat(),
             "source_manifest_sha256":file_sha256(args.processed_dir/"manifest.json"),
             "catalogue_sha256":file_sha256(args.catalogue),
             "source_table_hashes":{k:file_sha256(args.processed_dir/f"{k}.parquet") for k in ("works","work_topics")},
             "source_manifest_status":source_manifest["status"],"sample_works":len(works),
             "text_complete_before_versions":int((works.title.map(clean_text).ne("") & works.abstract.map(clean_text).ne("")).sum()),
             "eligible_after_versions":len(eligible),"observed_primary_topics":int(works.primary_topic_id.nunique()),
             "selected_topics":selected,"target_8_to_15_passed":len(selected)>=8,
             "train_rows":len(train),"validation_rows":len(valid),"locked_test_rows":len(locked),
             "validation_outside_rows":len(outside),
             "catalogue_coverage_training":len(train)/max(1,len(eligible[eligible.publication_year.le(2023)])),
             "catalogue_coverage_validation":len(valid)/max(1,len(eligible[eligible.publication_year.eq(2024)])),
             "duplicate_groups":int((exclusions.groupby("version_group").size()>1).sum()),
             "duplicate_conflict_groups":int(exclusions.loc[exclusions.group_has_label_conflict,"version_group"].nunique()),
             "model":result,"outputs":outputs,
             "interpretation":"Non-confirmatory 4–7-topic diagnostic; silver-label agreement only. 2025 locked and unevaluated."}
    (args.output_dir/"manifest.json").write_text(json.dumps(outcome,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({k:outcome[k] for k in ("sample_works","eligible_after_versions","selected_topics","target_8_to_15_passed","train_rows","validation_rows","validation_outside_rows")},indent=2))
    print(json.dumps(result["metrics"],indent=2))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
