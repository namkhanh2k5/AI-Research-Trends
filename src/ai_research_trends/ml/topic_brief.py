"""Local topic-placement proof of concept with source-labelled sample context."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import numpy as np

from ai_research_trends.ml.topic_pilot import clean_text
from ai_research_trends.preprocessing.validate_tables import file_sha256


def load_verified_brief_run(run_dir: Path) -> tuple[object,dict,float,dict]:
    manifest=json.loads((run_dir/"manifest.json").read_text())
    if manifest.get("status")!="complete": raise ValueError("Incomplete Phase 6B run")
    for name in ("catalogue_b_linear_svm","topic_briefs"):
        record=manifest["outputs"][name]
        path=run_dir/Path(record["path"]).name
        if file_sha256(path)!=record["sha256"]: raise ValueError(f"Corrupted {name} artifact")
    model=joblib.load(run_dir/"catalogue_b_linear_svm.joblib")
    briefs=json.loads((run_dir/"topic_briefs.json").read_text())
    threshold=float(manifest["open_set"]["svm_max_decision"]["evaluation"]["threshold"])
    return model,briefs,threshold,manifest


def place_research_draft(title: str, abstract: str, model: object, briefs: dict,
                         threshold: float, top_k: int=3) -> dict:
    title=clean_text(title); abstract=clean_text(abstract)
    if not title: raise ValueError("A nonblank research title is required")
    if len(abstract)<50 or len(abstract.split())<8:
        raise ValueError("An abstract of at least 50 characters and 8 words is required")
    classes=model.named_steps["model"].classes_
    if not 1<=top_k<=len(classes): raise ValueError("Invalid top_k")
    text=title+"\n"+abstract
    decision=np.asarray(model.decision_function([text]))
    # LinearSVC returns one signed margin for a two-class model, but one
    # margin per class for a multiclass model.
    scores=np.array([-decision[0],decision[0]]) if len(classes)==2 else decision[0]
    order=np.argsort(-scores)
    ranked=[{"topic_id":classes[i],"name":briefs.get(classes[i],{}).get("name",classes[i]),
             "svm_decision_score":float(scores[i])} for i in order[:top_k]]
    accepted=bool(scores[order[0]]>=threshold)
    chosen_brief=briefs.get(classes[order[0]]) if accepted else None
    return {"status":"placed" if accepted else "no_confident_match",
            "warning":("Topic brief context unavailable" if accepted and chosen_brief is None else
                       None if accepted else "No confident match among the supported silver-label topics"),
            "top_candidate":ranked[0],"ranked_alternatives":ranked[1:],
            "score_interpretation":"raw SVM decision score; not a probability or semantic certainty",
            "rejection_threshold":threshold,"catalogue_size":len(classes),
            "topic_brief":chosen_brief,
            "provenance":{"model":"Phase 6B train-period TF-IDF + LinearSVC",
                "topic_context":"Phase 3 sampled works from 2020–2024; not population prevalence",
                "semantic_validation":"pending human review"}}


def main(argv: list[str]|None=None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir",type=Path,required=True)
    parser.add_argument("--title",required=True)
    parser.add_argument("--abstract",required=True)
    parser.add_argument("--top-k",type=int,default=3)
    args=parser.parse_args(argv)
    model,briefs,threshold,_=load_verified_brief_run(args.run_dir)
    try: result=place_research_draft(args.title,args.abstract,model,briefs,threshold,args.top_k)
    except ValueError as exc: parser.error(str(exc))
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
