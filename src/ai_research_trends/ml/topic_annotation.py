"""Import real independent Phase 6B human ratings; never generate ratings."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
from sklearn.metrics import cohen_kappa_score

from ai_research_trends.ml.topic_brief import load_verified_brief_run


SPECIAL={"NONE","UNCLEAR"}


def analyze_ratings(ratings: pd.DataFrame, blind: pd.DataFrame, answer_key: pd.DataFrame,
                    allowed_topics: set[str], model: object) -> dict:
    required={"example_id","rater_id","best_topic"}
    if not required.issubset(ratings.columns): raise ValueError("Ratings need example_id, rater_id, best_topic")
    if ratings.duplicated(["example_id","rater_id"]).any(): raise ValueError("Duplicate rater/example pair")
    if not ratings.example_id.isin(blind.example_id).all(): raise ValueError("Unknown example ID")
    ratings=ratings.copy()
    short_to_full={topic.rsplit("/",1)[-1]:topic for topic in allowed_topics}
    ratings["best_topic"]=ratings.best_topic.map(lambda value:short_to_full.get(value,value))
    if not ratings.best_topic.isin(allowed_topics|SPECIAL).all(): raise ValueError("Invalid human topic choice")
    if set(ratings.example_id)!=set(blind.example_id): raise ValueError("Some example IDs lack ratings")
    raters=sorted(ratings.rater_id.unique())
    if len(raters)!=2: raise ValueError("Exactly two independent raters are required")
    pivot=ratings.pivot(index="example_id",columns="rater_id",values="best_topic").reindex(blind.example_id)
    if pivot.isna().any().any(): raise ValueError("Every example needs both ratings")
    a,b=pivot[raters[0]].to_numpy(),pivot[raters[1]].to_numpy()
    joined=blind[["example_id","title","abstract"]].merge(answer_key,on="example_id",validate="one_to_one")
    predictions=model.predict((joined.title.fillna("")+"\n"+joined.abstract.fillna("")).tolist())
    return {"examples":len(joined),"raters":raters,"raw_agreement":float((a==b).mean()),
        "cohen_kappa_including_none_unclear":float(cohen_kappa_score(a,b)),
        "openalex_label_accepted_by_both":int(((a==joined.openalex_primary_topic.to_numpy()) &
                                                 (b==joined.openalex_primary_topic.to_numpy())).sum()),
        "model_prediction_accepted_by_both":int(((a==predictions)&(b==predictions)).sum()),
        "none_or_unclear_by_rater":{raters[0]:int(pd.Series(a).isin(SPECIAL).sum()),
                                   raters[1]:int(pd.Series(b).isin(SPECIAL).sum())},
        "disagreement_examples":int((a!=b).sum()),
        "interpretation":"Observed human ratings only; small calibration samples do not prove population accuracy"}


def main(argv: list[str]|None=None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir",type=Path,required=True)
    parser.add_argument("--ratings",type=Path,required=True)
    parser.add_argument("--sheet",choices=["calibration","evaluation"],required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args(argv)
    if args.output.exists(): parser.error("Refusing to overwrite an annotation analysis")
    model,briefs,_,_=load_verified_brief_run(args.run_dir)
    blind=pd.read_csv(args.run_dir/f"blind_{args.sheet}.csv")
    key=pd.read_csv(args.run_dir/f"restricted_key_{args.sheet}.csv")
    result=analyze_ratings(pd.read_csv(args.ratings),blind,key,set(briefs),model)
    args.output.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result,indent=2))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
