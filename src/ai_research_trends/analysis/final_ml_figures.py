"""Publication-ready figures generated only from verified Phase 3 development results."""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from ai_research_trends.preprocessing.validate_tables import file_sha256


def render(closed_dir: Path,open_dir: Path,integrated: Path,output_dir: Path) -> dict:
    if output_dir.exists():raise FileExistsError(output_dir)
    closed=json.loads((closed_dir/"results.json").read_text())
    opened=json.loads((open_dir/"results.json").read_text())
    if closed["final_2025_test"]!="SEALED" or opened["final_2025_test"]!="SEALED":
        raise ValueError("Figure source includes an opened final test")
    if file_sha256(integrated/"split_manifest.json")!=closed["source_manifest_sha256"]:
        raise ValueError("Figure integration source changed")
    from ai_research_trends.ml.final_inference import select_champion
    winner,method=select_champion(closed,opened)
    plt.rcParams.update({"font.family":"DejaVu Sans","font.size":9,"axes.grid":True,
                         "grid.alpha":.2,"figure.dpi":120})
    output_dir.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".final_ml_fig_stage_",dir=output_dir.parent) as temp:
        stage=Path(temp)
        def save(fig,name):
            fig.tight_layout();fig.savefig(stage/name,dpi=180,bbox_inches="tight")
            plt.close(fig)
        # Training support is separate from population prevalence.
        selected=closed["classes"]
        source=integrated/"train.parquet"
        frame=pd.read_parquet(source,columns=["primary_topic_id","dataset_origin"])
        counts=(frame.loc[frame.primary_topic_id.isin(selected)]
                .groupby(["primary_topic_id","dataset_origin"]).size().unstack(fill_value=0).reindex(selected))
        fig,ax=plt.subplots(figsize=(11,4));x=np.arange(len(selected));short=[v.rsplit("/",1)[-1] for v in selected]
        ax.bar(x-.2,counts.get("original_analytical_sample",pd.Series(0,index=selected)),.4,label="Original training")
        ax.bar(x+.2,counts.get("targeted_ml_expansion",pd.Series(0,index=selected)),.4,label="Targeted addition")
        ax.set_xticks(x,short,rotation=55,ha="right");ax.set_ylabel("Works");ax.legend()
        ax.set_title("Training support by frozen topic (not population prevalence)")
        save(fig,"training_support.png")
        curve=pd.DataFrame(closed["learning_curve"])
        fig,ax=plt.subplots(figsize=(6,4));ax.plot(curve.train_rows,curve.macro_f1,marker="o")
        ax.set(xlabel="Historical training works",ylabel="2024 Macro-F1 vs OpenAlex labels",
               title="Observed expansion-fraction diagnostic; no extrapolation")
        save(fig,"learning_curve.png")
        rows=[]
        for name in ("complement_nb","logistic_regression","linear_svm"):
            for origin in ("original_only","expanded"):
                key=f"{origin}_{name}";rows.append({"model":name,"source":origin,
                    "macro_f1":closed["metrics"][key]["macro_f1"]})
        compare=pd.DataFrame(rows)
        fig,ax=plt.subplots(figsize=(7,4));sns.barplot(compare,x="model",y="macro_f1",hue="source",ax=ax)
        ax.set(ylabel="2024 Macro-F1 vs OpenAlex labels",xlabel="Model",ylim=(0,1),
               title="Matched 681-work development validation")
        save(fig,"model_comparison.png")
        per=pd.read_csv(closed_dir/"per_class.csv")
        fig,ax=plt.subplots(figsize=(9,4));ax.bar(per.topic_id.str.rsplit("/",n=1).str[-1],per.f1)
        ax.tick_params(axis="x",rotation=55);ax.set(ylabel="F1",ylim=(0,1),
            title=f"Per-class 2024 silver-label F1: expanded {winner}")
        save(fig,"per_class_f1.png")
        confusion=pd.read_csv(closed_dir/"confusion.csv",index_col=0)
        fig,ax=plt.subplots(figsize=(8,7));sns.heatmap(confusion,cmap="Blues",ax=ax,
            xticklabels=[x.rsplit("/",1)[-1] for x in confusion.columns],
            yticklabels=[x.rsplit("/",1)[-1] for x in confusion.index])
        ax.set(xlabel="Predicted OpenAlex topic",ylabel="Observed OpenAlex topic",
               title=f"Development confusion matrix: expanded {winner}")
        save(fig,"confusion.png")
        fig,ax=plt.subplots(figsize=(6,5))
        for name in ("calibrated_lr","svm_margin","explicit_other_lr"):
            table=pd.read_csv(open_dir/f"{name}_roc.csv")
            auc=opened["methods"][name]["evaluation"]["auroc_in_vs_out"]
            ax.plot(table.fpr,table.tpr,label=f"{name} (AUROC {auc:.3f})")
        ax.plot([0,1],[0,1],"--",color="grey")
        ax.set(xlabel="Outside false-positive rate",ylabel="In-catalogue true-positive rate",
               title="2024 held-out development open-set discrimination");ax.legend(fontsize=8)
        save(fig,"open_set_roc.png")
        risk=pd.read_csv(open_dir/f"{method}_risk_coverage.csv")
        fig,ax=plt.subplots(figsize=(6,4));ax.plot(risk.coverage,risk.risk,marker=".")
        ax.set(xlabel="Accepted in-catalogue coverage",ylabel="Error among accepted in-catalogue works",
               title=f"Development selective-risk curve: {method}")
        save(fig,"risk_coverage.png")
        fig,ax=plt.subplots(figsize=(6,4));ax.plot(risk.threshold,risk.false_acceptance,marker=".")
        ax.axvline(opened["methods"][method]["threshold"],color="red",linestyle="--",label="Frozen threshold")
        ax.set(xlabel="Decision threshold (method-specific score)",ylabel="Outside false acceptance",
               title=f"2024 evaluation sensitivity: {method}");ax.legend()
        save(fig,"threshold_sensitivity.png")
        fig,ax=plt.subplots(figsize=(6,4))
        methods=list(opened["methods"])
        ax.bar(methods,[opened["methods"][name]["inference_ms_per_work"] for name in methods])
        ax.tick_params(axis="x",rotation=35);ax.set(ylabel="Milliseconds per work",title="Local 2024 inference latency")
        save(fig,"inference_latency.png")
        files={path.name:{"sha256":file_sha256(path),"bytes":path.stat().st_size}
               for path in sorted(stage.glob("*.png"))}
        manifest={"status":"complete","source_closed_sha256":file_sha256(closed_dir/"manifest.json"),
                  "source_open_sha256":file_sha256(open_dir/"manifest.json"),
                  "source_scope":"2024 development; never population performance or 2025 final test",
                  "files":files}
        (stage/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
        stage.replace(output_dir)
    return manifest


def main(argv: list[str]|None=None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--closed-run",type=Path,required=True)
    parser.add_argument("--open-run",type=Path,required=True)
    parser.add_argument("--integrated",type=Path,default=Path("data/processed/ml_topic_classification/finalization_p2_20261101_v3"))
    parser.add_argument("--output-dir",type=Path,required=True)
    args=parser.parse_args(argv);result=render(args.closed_run,args.open_run,args.integrated,args.output_dir)
    print(json.dumps({"status":result["status"],"figures":len(result["files"])},indent=2));return 0


if __name__=="__main__":raise SystemExit(main())
