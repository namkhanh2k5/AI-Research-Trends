"""RQ6 descriptive audit of OpenAlex silver-topic assignments, without test-label use."""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from collections import Counter
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
import yaml
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from ai_research_trends.ml.validate_integrated_data import verify_run
from ai_research_trends.preprocessing.validate_tables import file_sha256


def wilson_interval(success: int,total: int,z: float=1.96) -> tuple[float,float]:
    if total==0: return (float("nan"),float("nan"))
    rate=success/total;denom=1+z*z/total
    centre=(rate+z*z/(2*total))/denom
    half=z*np.sqrt(rate*(1-rate)/total+z*z/(4*total*total))/denom
    return max(0.,centre-half),min(1.,centre+half)


def analyze(works: pd.DataFrame, topics: pd.DataFrame, train: pd.DataFrame,
            validation: pd.DataFrame, groups: pd.DataFrame,
            metadata: pd.DataFrame, catalogue: dict) -> dict[str,pd.DataFrame]:
    """Only 2020–2024 source labels are used; 2025 stays sealed."""
    dev=works.loc[works.publication_year.le(2024)].copy()
    if dev.work_id.duplicated().any(): raise ValueError("Original sample Work IDs duplicated")
    selected={f"https://openalex.org/{item}" for item in catalogue["catalogue_b"]}
    verified=metadata.set_index("topic_id")
    if not selected.issubset(set(verified.index)): raise ValueError("Selected official metadata incomplete")
    rank=topics.loc[topics.work_id.isin(dev.work_id)].copy()
    if rank.duplicated(["work_id","topic_id"]).any(): raise ValueError("Duplicate topic relationships")
    if rank.loc[rank.topic_rank.eq(1)].work_id.nunique()!=len(dev):
        raise ValueError("Missing rank-one topic in original sample")
    dev["selected"] = dev.primary_topic_id.isin(selected)
    support=[]
    for topic_id in sorted(selected):
        original=dev.loc[dev.primary_topic_id.eq(topic_id)]
        original_train=train.loc[train.primary_topic_id.eq(topic_id) &
                                  train.dataset_origin.eq("original_analytical_sample")]
        added=train.loc[train.primary_topic_id.eq(topic_id) &
                        train.dataset_origin.eq("targeted_ml_expansion")]
        missing=int(original.abstract.isna().sum())
        lo,hi=wilson_interval(missing,len(original))
        support.append({"topic_id":topic_id,"short_id":topic_id.rsplit("/",1)[-1],
            "official_name":verified.at[topic_id,"name"],
            "parent_subfield":int(verified.at[topic_id,"subfield_id"]),
            "original_sample_2020_2024":len(original),
            "original_train_usable":len(original_train),"new_train_usable":len(added),
            "integrated_train_usable":len(original_train)+len(added),
            "validation_2024_usable":int(validation.primary_topic_id.eq(topic_id).sum()),
            "missing_abstract_original":missing,"missing_abstract_rate":missing/len(original) if len(original) else None,
            "missing_abstract_wilson_low":lo,"missing_abstract_wilson_high":hi,
            "target_225_gap":max(0,225-len(original_train)-len(added))})
    support=pd.DataFrame(support)
    year=(train.loc[train.primary_topic_id.isin(selected)]
          .groupby(["publication_year","primary_topic_id","dataset_origin"]).size()
          .rename("usable_train_works").reset_index().sort_values(
              ["publication_year","primary_topic_id","dataset_origin"]))
    # Assignment scores are similarities from OpenAlex, not calibrated probabilities.
    score=rank.loc[rank.topic_rank.isin([1,2]),["work_id","topic_rank","topic_score"]].pivot(
        index="work_id",columns="topic_rank",values="topic_score")
    score.columns=[f"score_rank_{int(col)}" for col in score.columns]
    score=dev[["work_id","primary_topic_id","publication_year","work_type"]].merge(
        score.reset_index(),on="work_id",validate="one_to_one")
    score["top1_top2_gap"]=score.score_rank_1-score.score_rank_2
    score["low_margin_under_0_05"]=score.top1_top2_gap.lt(.05)
    scores=(score.loc[score.primary_topic_id.isin(selected)]
            .groupby("primary_topic_id",as_index=False)
            .agg(works=("work_id","size"),primary_score_median=("score_rank_1","median"),
                 secondary_score_median=("score_rank_2","median"),
                 gap_median=("top1_top2_gap","median"),gap_p10=("top1_top2_gap",lambda x:x.quantile(.1)),
                 low_margin_count=("low_margin_under_0_05","sum")))
    scores["low_margin_rate"]=scores.low_margin_count/scores.works
    selected_rank=rank.loc[rank.topic_id.isin(selected)]
    paper_sets=selected_rank.groupby("work_id").topic_id.apply(lambda series:sorted(set(series))).to_dict()
    pair_counts=Counter()
    for ids in paper_sets.values():
        for index,a in enumerate(ids):
            for b in ids[index+1:]: pair_counts[(a,b)]+=1
    membership=selected_rank.groupby("topic_id").work_id.nunique().to_dict()
    pairs=pd.DataFrame([{"topic_a":a,"topic_b":b,"coassigned_works":count,
                         "p_b_given_a":count/membership[a],"p_a_given_b":count/membership[b],
                         "a_membership":membership[a],"b_membership":membership[b]}
                        for (a,b),count in sorted(pair_counts.items())])
    descriptions=[verified.at[item,"description"] for item in sorted(selected)]
    vectors=TfidfVectorizer(ngram_range=(1,2),stop_words="english").fit_transform(descriptions)
    similarity=cosine_similarity(vectors)
    ids=sorted(selected)
    lexical=pd.DataFrame([{"topic_a":ids[i],"topic_b":ids[j],"description_tfidf_cosine":float(similarity[i,j])}
                          for i in range(len(ids)) for j in range(i+1,len(ids))])
    missing=(dev.loc[dev.primary_topic_id.isin(selected)]
             .assign(abstract_missing=lambda frame:frame.abstract.isna())
             .groupby(["primary_topic_id","work_type"],as_index=False)
             .agg(sample_works=("work_id","size"),missing_abstract=("abstract_missing","sum")))
    missing["missing_rate"]=missing.missing_abstract/missing.sample_works
    duplicate=(groups.groupby(["cross_period","topic_label_conflict_development","resolution"],
                              as_index=False).agg(groups=("version_group","size"),
                                                   source_records=("source_records","sum")))
    composition=(train.groupby(["dataset_origin","work_type","language"],dropna=False)
                 .size().rename("works").reset_index())
    return {"topic_support":support,"topic_year_train":year,"topic_scores":scores,
            "topic_cooccurrence":pairs,"description_similarity":lexical,
            "abstract_missing_by_type":missing,"duplicate_diagnostics":duplicate,
            "train_composition":composition}


def figures(tables: dict[str,pd.DataFrame], output_dir: Path) -> list[Path]:
    output_dir.mkdir()
    sns.set_theme(style="whitegrid",font_scale=.9)
    produced=[]
    support=tables["topic_support"].sort_values("short_id")
    fig,ax=plt.subplots(figsize=(11,6))
    x=np.arange(len(support));ax.bar(x-.2,support.original_train_usable,.4,label="Original usable train")
    ax.bar(x+.2,support.new_train_usable,.4,label="Added usable train")
    ax.axhline(225,ls="--",color="black",lw=1,label="Planning target 225")
    ax.set_xticks(x,support.short_id,rotation=45,ha="right");ax.set_ylabel("Training works")
    ax.set_title("RQ6: original vs targeted-enrichment training support");ax.legend()
    fig.tight_layout();path=output_dir/"rq6_training_support.png";fig.savefig(path,dpi=180);plt.close(fig);produced.append(path)
    years=tables["topic_year_train"].groupby(["primary_topic_id","publication_year"]).usable_train_works.sum().unstack(fill_value=0)
    fig,ax=plt.subplots(figsize=(8,6));sns.heatmap(years.rename(index=lambda s:s.rsplit("/",1)[-1]),annot=True,fmt="d",cmap="Blues",ax=ax)
    ax.set_title("RQ6: usable training support by year (enriched)");ax.set_xlabel("Publication year")
    fig.tight_layout();path=output_dir/"rq6_train_year_heatmap.png";fig.savefig(path,dpi=180);plt.close(fig);produced.append(path)
    ids=support.topic_id.tolist();matrix=pd.DataFrame(0,index=ids,columns=ids,dtype=int)
    for row in tables["topic_cooccurrence"].itertuples():
        matrix.at[row.topic_a,row.topic_b]=row.coassigned_works
        matrix.at[row.topic_b,row.topic_a]=row.coassigned_works
    matrix.index=[item.rsplit("/",1)[-1] for item in matrix.index]
    matrix.columns=[item.rsplit("/",1)[-1] for item in matrix.columns]
    fig,ax=plt.subplots(figsize=(9,7));sns.heatmap(matrix,cmap="mako",ax=ax)
    ax.set_title("RQ6: co-assigned native topics, original 2020–2024 sample")
    fig.tight_layout();path=output_dir/"rq6_topic_cooccurrence.png";fig.savefig(path,dpi=180);plt.close(fig);produced.append(path)
    scores=tables["topic_scores"].sort_values("gap_median")
    fig,ax=plt.subplots(figsize=(10,5));ax.bar(scores.primary_topic_id.map(lambda s:s.rsplit("/",1)[-1]),scores.gap_median)
    ax.tick_params(axis="x",rotation=45);ax.set_ylabel("Median top-1 minus top-2 assignment score")
    ax.set_title("RQ6: score separation is not a calibrated probability")
    fig.tight_layout();path=output_dir/"rq6_score_gaps.png";fig.savefig(path,dpi=180);plt.close(fig);produced.append(path)
    fig,ax=plt.subplots(figsize=(10,5));ax.bar(support.short_id,support.missing_abstract_rate)
    ax.tick_params(axis="x",rotation=45);ax.set_ylabel("Missing abstract share")
    ax.set_title("RQ6: original sample 2020–2024 abstract missingness")
    fig.tight_layout();path=output_dir/"rq6_abstract_missingness.png";fig.savefig(path,dpi=180);plt.close(fig);produced.append(path)
    return produced


def run(processed_dir: Path, integrated_dir: Path, catalogue_path: Path,
        output_dir: Path, publish_dir: Path|None=None) -> dict:
    if output_dir.exists() or (publish_dir and publish_dir.exists()):
        raise FileExistsError("Refusing to overwrite RQ6 output or published aggregates")
    verified=verify_run(integrated_dir)
    phase3=json.loads((processed_dir/"manifest.json").read_text())
    for name in ("works","work_topics"):
        if file_sha256(processed_dir/f"{name}.parquet")!=phase3["tables"][name]["sha256"]:
            raise ValueError("Original analytical table checksum changed")
    catalogue=yaml.safe_load(catalogue_path.read_text())
    metadata_path=Path(catalogue["source_metadata_csv"])
    if file_sha256(metadata_path)!=catalogue["source_metadata_sha256"]:
        raise ValueError("Official topic metadata checksum changed")
    inputs={"original_works":processed_dir/"works.parquet","original_topics":processed_dir/"work_topics.parquet",
            "integrated_train":integrated_dir/"train.parquet","integrated_validation":integrated_dir/"validation_2024.parquet",
            "integrated_groups":integrated_dir/"version_groups.parquet","catalogue":catalogue_path,
            "metadata":metadata_path}
    tables=analyze(pd.read_parquet(inputs["original_works"]),pd.read_parquet(inputs["original_topics"]),
        pd.read_parquet(inputs["integrated_train"]),pd.read_parquet(inputs["integrated_validation"]),
        pd.read_parquet(inputs["integrated_groups"]),pd.read_csv(metadata_path),catalogue)
    output_dir.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".rq6_stage_",dir=output_dir.parent) as temp:
        stage=Path(temp);files={}
        for name,table in tables.items():
            path=stage/f"{name}.csv";table.to_csv(path,index=False,float_format="%.12g")
            files[path.name]={"rows":len(table),"sha256":file_sha256(path),"bytes":path.stat().st_size}
        for path in figures(tables,stage/"figures"):
            files[f"figures/{path.name}"]={"sha256":file_sha256(path),"bytes":path.stat().st_size}
        manifest={"status":"complete","run_id":output_dir.name,
            "source_scope":"original 2020-2024 sample and enriched 2020-2023 training; no 2025 labels",
            "integration_validation":verified,"inputs":{key:{"path":str(value),"sha256":file_sha256(value)}
                                                   for key,value in inputs.items()},"outputs":files}
        (stage/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
        stage.replace(output_dir)
    if publish_dir:
        publish_dir.mkdir(parents=True,exist_ok=False)
        for name in files:
            source=output_dir/name;target=publish_dir/name
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(source,target)
        (publish_dir/"manifest.json").write_text(json.dumps({
            "status":"complete","source_manifest_sha256":file_sha256(output_dir/"manifest.json"),
            "files":files,"no_2025_label_distribution":True},indent=2)+"\n")
    return manifest


def main(argv: list[str]|None=None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--processed-dir",type=Path,default=Path("data/processed/openalex_stratified/stratified_20261019T155909Z"))
    parser.add_argument("--integrated-dir",type=Path,required=True)
    parser.add_argument("--catalogue",type=Path,default=Path("config/phase6b_catalogue.yaml"))
    parser.add_argument("--output-dir",type=Path,required=True)
    parser.add_argument("--publish-dir",type=Path)
    args=parser.parse_args(argv)
    result=run(args.processed_dir,args.integrated_dir,args.catalogue,args.output_dir,args.publish_dir)
    print(json.dumps({"status":result["status"],"files":len(result["outputs"]),
                      "source_scope":result["source_scope"]},indent=2))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
