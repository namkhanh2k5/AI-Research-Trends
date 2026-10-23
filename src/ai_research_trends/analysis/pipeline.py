"""Run RQ1–RQ4 against verified Phase 3 outputs without altering source data."""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from ai_research_trends.analysis.citation_impact import citation_tables
from ai_research_trends.analysis.collaboration_analysis import collaboration_tables
from ai_research_trends.analysis.descriptive import analytical_subset_audit, missingness_table
from ai_research_trends.analysis.load_data import load_verified_tables
from ai_research_trends.analysis.open_access_analysis import oa_binary_descriptives, oa_descriptives, oa_models
from ai_research_trends.analysis.publication_trends import emerging_sample_trends, population_and_native_trends
from ai_research_trends.analysis.report import render_report
from ai_research_trends.analysis.validation import validate_analytical_results, verify_run
from ai_research_trends.analysis.visualization import make_figures
from ai_research_trends.preprocessing.validate_tables import file_sha256


GRAINS = {
    "publication_trends": ("year", "complete primary non-retracted population by year"),
    "native_topic_trends": ("series, year", "overlapping native-topic count within primary population"),
    "emerging_topic_sample_trends": ("category, year", "sampled works in that publication-year stratum"),
    "citation_descriptives": ("group_by, group, metric", "sampled works in group"),
    "fwci_descriptives": ("group_by, group, metric", "FWCI-observed eligible works; total group shown"),
    "oa_descriptives": ("oa_status", "OA-observed sampled works"),
    "oa_binary_descriptives": ("is_oa", "OA-observed sampled works"),
    "oa_composition": ("oa_status, group_by, group", "sampled works within OA status"),
    "oa_regression_results": ("model, term", "complete-case sampled works per model"),
    "oa_model_diagnostics": ("model", "full 12,000 and model complete cases"),
    "oa_year_sensitivity": ("publication_year, is_oa", "OA-observed works in year"),
    "collaboration_descriptives": ("group_by, group", "sampled works in group; known-status subdenominator shown"),
    "country_collaboration_edges": ("country_a, country_b", "unique supporting sampled works"),
    "institution_collaboration_edges": ("institution_a, institution_b", "unique supporting sampled works"),
    "network_metrics": ("network", "observed sample affiliation graph"),
    "missingness_analysis": ("group_by, group, field", "sampled works in group"),
    "analytical_subset_audit": ("subset, group_by, group", "sampled works in group"),
    "statistical_test_results": ("test, hypothesis", "paired complete-case sampled works"),
    "figure_inventory": ("figure", "denominator recorded for each figure"),
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run verified Phase 4 bibliometric analyses")
    parser.add_argument("--processed-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True, help="New directory; existing runs are immutable")
    parser.add_argument("--plan", type=Path, default=Path("data/metadata/phase2_sampling_plan.json"))
    parser.add_argument("--population", type=Path, default=Path("data/metadata/population_counts_pre_phase2.json"))
    parser.add_argument("--config", type=Path, default=Path("config/topics.yaml"))
    parser.add_argument("--analysis-plan", type=Path, default=Path("docs/PHASE4_STATISTICAL_ANALYSIS_PLAN.md"))
    parser.add_argument("--seed", type=int, default=20261023)
    parser.add_argument("--publish", action="store_true", help="Also publish report and figures to reports/")
    parser.add_argument("--report-path", type=Path, default=Path("reports/PHASE4_ANALYSIS_REPORT.md"))
    parser.add_argument("--figure-dir", type=Path, default=Path("reports/figures/phase4"))
    return parser


def analyze(
    *, processed_dir: Path, output_dir: Path, plan_path: Path, population_path: Path,
    config_path: Path, analysis_plan_path: Path, seed: int, publish: bool = False,
    report_path: Path = Path("reports/PHASE4_ANALYSIS_REPORT.md"),
    figure_dir: Path = Path("reports/figures/phase4"),
) -> dict:
    if output_dir.exists():
        raise FileExistsError(f"Refusing to overwrite Phase 4 run: {output_dir}")
    if publish and (report_path.exists() or figure_dir.exists()):
        raise FileExistsError("Published report or figure directory already exists; use a new versioned path")
    if not analysis_plan_path.is_file():
        raise FileNotFoundError(f"Predeclared statistical plan missing: {analysis_plan_path}")
    source, phase3, plan = load_verified_tables(processed_dir, plan_path, population_path, config_path)
    works = source["works"]
    if len(works) != works.work_id.nunique():
        raise ValueError("Work-level grain inflated before analysis")
    population = source["population_year_counts"]
    growth, native, _ = population_and_native_trends(population, plan["population_query_name"])
    emerging = emerging_sample_trends(works, source["category_membership"])
    citations, fwci, statistical_tests = citation_tables(works, source["category_membership"])
    oa, oa_composition = oa_descriptives(works)
    models, model_diagnostics, oa_year = oa_models(works)
    collab, countries, institutions, network = collaboration_tables(
        works, source["work_countries"], source["work_institutions"]
    )
    results = {
        "publication_trends": growth, "native_topic_trends": native,
        "emerging_topic_sample_trends": emerging, "citation_descriptives": citations,
        "fwci_descriptives": fwci, "oa_descriptives": oa,
        "oa_binary_descriptives": oa_binary_descriptives(works),
        "oa_composition": oa_composition, "oa_regression_results": models,
        "oa_model_diagnostics": model_diagnostics, "oa_year_sensitivity": oa_year,
        "collaboration_descriptives": collab, "country_collaboration_edges": countries,
        "institution_collaboration_edges": institutions, "network_metrics": network,
        "missingness_analysis": missingness_table(works),
        "analytical_subset_audit": analytical_subset_audit(works),
        "statistical_test_results": statistical_tests,
    }
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".phase4_stage_", dir=output_dir.parent) as temporary:
        stage = Path(temporary)
        results["figure_inventory"] = make_figures({**results, "works": works}, stage / "figures")
        checks = validate_analytical_results({**results, "works": works}, plan)
        source_run = phase3["source_run_id"]
        report = render_report({**results, "works": works}, run_id=source_run,
                               observed_at=phase3["observation_time_utc"],
                               population_total=plan["population_total"],
                               processed_hash=file_sha256(processed_dir / "manifest.json"), seed=seed)
        (stage / "PHASE4_ANALYSIS_REPORT.md").write_text(report, encoding="utf-8")
        files: dict[str, dict] = {}
        for name, frame in results.items():
            path = stage / f"{name}.csv"
            frame.to_csv(path, index=False, float_format="%.12g", lineterminator="\n")
            files[path.name] = {"path": path.name, "rows": len(frame),
                                "columns": len(frame.columns), "sha256": file_sha256(path),
                                "grain": GRAINS[name][0], "denominator": GRAINS[name][1],
                                "scope": "population" if name in {"publication_trends", "native_topic_trends"} else "detailed sample"}
        for path in sorted((stage / "figures").iterdir()):
            files[f"figures/{path.name}"] = {"path": f"figures/{path.name}",
                                              "bytes": path.stat().st_size, "sha256": file_sha256(path)}
        report_file = stage / "PHASE4_ANALYSIS_REPORT.md"
        files[report_file.name] = {"path": report_file.name, "bytes": report_file.stat().st_size,
                                   "sha256": file_sha256(report_file)}
        inputs = {
            "phase3_manifest": processed_dir / "manifest.json", "sampling_plan": plan_path,
            "population_artifact": population_path, "category_config": config_path,
            "statistical_analysis_plan": analysis_plan_path,
            **{f"phase3_{name}": processed_dir / f"{name}.parquet" for name in source},
        }
        manifest = {
            "schema_version": 1, "analysis_version": "phase4-v1",
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "status": "complete", "complete": True, "seed": seed,
            "source_run_id": source_run, "population_series": plan["population_query_name"],
            "population_total": int(plan["population_total"]),
            "sample_works": len(works), "citation_observation_time_utc": phase3["observation_time_utc"],
            "sampling_note": "nominal weights only; no probability-sampling or causal claim",
            "inputs": {name: {"path": str(path.resolve()), "sha256": file_sha256(path)}
                       for name, path in inputs.items()},
            "outputs": files, "validation": checks,
        }
        (stage / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        stage.replace(output_dir)
    verify_run(output_dir)
    if publish:
        figure_dir.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(output_dir / "figures", figure_dir)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_report = report_path.with_suffix(report_path.suffix + ".part")
        shutil.copy2(output_dir / "PHASE4_ANALYSIS_REPORT.md", temporary_report)
        temporary_report.replace(report_path)
    return manifest


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    manifest = analyze(
        processed_dir=args.processed_dir, output_dir=args.output_dir,
        plan_path=args.plan, population_path=args.population, config_path=args.config,
        analysis_plan_path=args.analysis_plan, seed=args.seed, publish=args.publish,
        report_path=args.report_path, figure_dir=args.figure_dir,
    )
    print(json.dumps({"complete": manifest["complete"], "output_dir": str(args.output_dir),
                      "checks_passed": len(manifest["validation"]),
                      "tables": len([name for name in manifest["outputs"] if name.endswith(".csv")]),
                      "figures_png": len([name for name in manifest["outputs"] if name.endswith(".png")])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
