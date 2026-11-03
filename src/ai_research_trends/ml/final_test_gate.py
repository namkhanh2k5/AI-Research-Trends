"""Explicit, single-use final-test command; sealed until genuine human sign-off."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from sklearn.metrics import accuracy_score, f1_score

from ai_research_trends.ml.final_experiments import text_features
from ai_research_trends.ml.final_inference import TopicPlacementService
from ai_research_trends.ml.final_open_set import score_predictions
from ai_research_trends.ml.human_review_workflow import validate_ratings
from ai_research_trends.ml.topic_final_validation import open_set_metrics
from ai_research_trends.preprocessing.validate_tables import file_sha256


def verify_human_gate(gate_path: Path, model_dir: Path, catalogue_path: Path,
                      review_package: Path, frozen_protocol: Path) -> dict:
    """Check provenance before *any* test-table read. Human genuineness needs external audit."""
    frozen=yaml.safe_load(frozen_protocol.read_text())
    if frozen.get("allow_final_test_execution") is not True or frozen.get("human_review")!="approved_two_independent_real_raters":
        raise PermissionError("Frozen protocol does not authorize opening the 2025 final test")
    gate=json.loads(gate_path.read_text())
    if gate.get("status")!="approved" or gate.get("scope_decision")!="no_fundamental_issue":
        raise PermissionError("Independent human scope review has not approved final testing")
    if gate.get("independent_real_human_reviewers") is not True:
        raise PermissionError("Two real independent reviewers must be attested")
    if len(set(gate.get("signed_off_by",[])))!=2:
        raise PermissionError("Two distinct human sign-offs required")
    if gate.get("frozen_protocol_sha256")!=file_sha256(frozen_protocol):
        raise ValueError("Frozen protocol changed")
    if gate.get("model_manifest_sha256")!=file_sha256(model_dir/"manifest.json"):
        raise ValueError("Frozen model manifest changed")
    catalogue=yaml.safe_load(catalogue_path.read_text())
    allowed=set(catalogue["catalogue_b"])
    hashes=[]
    for reviewer in ("reviewer_a","reviewer_b"):
        path=Path(gate["rating_paths"][reviewer])
        blind=pd.read_csv(review_package/reviewer/"blind_evaluation.csv")
        validated=validate_ratings(pd.read_csv(path),blind,reviewer,allowed)
        if len(validated)!=len(blind):raise ValueError("Incomplete reviewer evaluation")
        hashes.append(file_sha256(path))
    return {"valid":True,"rating_hashes":hashes,"sign_off":gate["signed_off_by"]}


def evaluate_once(gate_path: Path,model_dir: Path,web_dir: Path,test_path: Path,
                  catalogue_path: Path,review_package: Path,frozen_protocol: Path,
                  output_dir: Path, registry_path: Path|None=None) -> dict:
    if output_dir.exists():raise FileExistsError("Final test already has this output; never overwrite")
    gate=verify_human_gate(gate_path,model_dir,catalogue_path,review_package,frozen_protocol)
    model_manifest=json.loads((model_dir/"manifest.json").read_text())
    integrated=Path(model_manifest["source_paths"]["integrated"])
    source_manifest=json.loads((integrated/"split_manifest.json").read_text())
    expected=source_manifest["outputs"]["test_2025_sealed.parquet"]["sha256"]
    # A project-level, exclusive receipt prevents a second run using another
    # output directory. Keep even a failed attempt for human investigation.
    registry_path=registry_path or Path("data/analysis/finalization_p3_final_test_registry.json")
    registry_path.parent.mkdir(parents=True,exist_ok=True)
    attempt={"status":"attempt_started","started_at_utc":datetime.now(timezone.utc).isoformat(),
             "model_manifest_sha256":file_sha256(model_dir/"manifest.json"),
             "frozen_protocol_sha256":file_sha256(frozen_protocol),
             "human_gate_sha256":file_sha256(gate_path),"test_expected_sha256":expected,
             "output_dir":str(output_dir)}
    try:
        fd=os.open(registry_path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    except FileExistsError as exc:
        raise FileExistsError("Project-level final-test registry already exists; manual audit required") from exc
    with os.fdopen(fd,"w") as stream:
        json.dump(attempt,stream,indent=2)
        stream.write("\n")
        stream.flush();os.fsync(stream.fileno())
    if file_sha256(test_path)!=expected:raise ValueError("Sealed test checksum changed")
    service=TopicPlacementService(model_dir,web_dir)
    test=text_features(pd.read_parquet(test_path))
    if not test.publication_year.eq(2025).all():raise ValueError("Final-test year mismatch")
    classes=service.config["classes"];selected=set(classes)
    score,pred=score_predictions(service.model,test.text.tolist(),service.config["score_method"],selected)
    truth=test.primary_topic_id.to_numpy();threshold=float(service.config["threshold"])
    opened=open_set_metrics(score,pred,truth,selected,threshold)
    within=np.isin(truth,classes)
    closed={"n":int(within.sum()),"accuracy":float(accuracy_score(truth[within],pred[within])),
            "macro_f1":float(f1_score(truth[within],pred[within],labels=classes,average="macro",zero_division=0)),
            "weighted_f1":float(f1_score(truth[within],pred[within],labels=classes,average="weighted",zero_division=0))}
    output_dir.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".final_test_stage_",dir=output_dir.parent) as temp:
        stage=Path(temp)
        pd.DataFrame({"work_id":test.work_id,"true_topic":truth,"predicted_topic":pred,
                      "score":score,"accepted":score>=threshold}).to_parquet(stage/"predictions.parquet",index=False)
        result={"status":"complete","evaluated_once_at_utc":datetime.now(timezone.utc).isoformat(),
                "model_version":service.config["model_version"],"test_sha256":expected,
                "human_gate_sha256":file_sha256(gate_path),"human_rating_hashes":gate["rating_hashes"],
                "closed_set":closed,"open_set":opened,"predictions_sha256":file_sha256(stage/"predictions.parquet")}
        (stage/"result.json").write_text(json.dumps(result,indent=2)+"\n")
        stage.replace(output_dir)
    receipt={**attempt,"status":"complete","test_sha256":expected,
             "completed_at_utc":result["evaluated_once_at_utc"],
             "result_sha256":file_sha256(output_dir/"result.json")}
    with tempfile.NamedTemporaryFile(mode="w",dir=registry_path.parent,prefix=".final_test_receipt_",
                                     delete=False) as stream:
        json.dump(receipt,stream,indent=2);stream.write("\n")
        stream.flush();os.fsync(stream.fileno());temporary=Path(stream.name)
    temporary.replace(registry_path)
    return result


def main(argv: list[str]|None=None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute-once",action="store_true",required=True)
    parser.add_argument("--human-gate",type=Path,required=True)
    parser.add_argument("--model-dir",type=Path,required=True)
    parser.add_argument("--web-dir",type=Path,required=True)
    parser.add_argument("--test-path",type=Path,required=True)
    parser.add_argument("--catalogue",type=Path,default=Path("config/phase6b_catalogue.yaml"))
    parser.add_argument("--review-package",type=Path,default=Path("data/analysis/finalization_p2_human_review_20261101_v1"))
    parser.add_argument("--frozen-protocol",type=Path,required=True)
    parser.add_argument("--output-dir",type=Path,required=True)
    parser.add_argument("--registry",type=Path,default=Path("data/analysis/finalization_p3_final_test_registry.json"))
    args=parser.parse_args(argv)
    result=evaluate_once(args.human_gate,args.model_dir,args.web_dir,args.test_path,args.catalogue,
                         args.review_package,args.frozen_protocol,args.output_dir,args.registry)
    print(json.dumps({"status":result["status"],"closed_set":result["closed_set"],
                      "open_set":result["open_set"]},indent=2));return 0


if __name__=="__main__":raise SystemExit(main())
