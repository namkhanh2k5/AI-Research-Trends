"""Time-cutoff candidate-pool reassessment on verified Phase 3 citation edges.

All pools are constructed without evaluation-period edges. Results measure ID
overlap, not time-valid recall or a retriever's ranking performance.
"""

from __future__ import annotations

import argparse
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from ai_research_trends.analysis.load_data import load_verified_tables
from ai_research_trends.ml.feasibility import (
    candidate_frequency, candidate_pool, coverage_per_query, coverage_summary,
    nested_query_subset, query_eligibility,
)
from ai_research_trends.preprocessing.validate_tables import file_sha256


def historical_citers(works: pd.DataFrame, references: pd.DataFrame, *,
                      evaluation_year: int, eligible_ids: set[str] | None = None) -> set[str]:
    """Return citing IDs strictly earlier than evaluation year and with edges."""
    if evaluation_year not in (2023, 2024, 2025):
        raise ValueError("evaluation_year must be 2023, 2024, or 2025")
    dated = works.loc[works.publication_year.lt(evaluation_year),
                      ["work_id", "publication_year", "publication_date"]].copy()
    parsed = pd.to_datetime(dated.publication_date, errors="coerce")
    dated = dated.loc[parsed.notna() & parsed.dt.year.eq(dated.publication_year)]
    ids = set(dated.work_id) & set(references.citing_work_id)
    return ids if eligible_ids is None else ids & eligible_ids


def pool_audit(works: pd.DataFrame, references: pd.DataFrame,
               eligibility: pd.DataFrame, *, evaluation_year: int,
               strategy: str, threshold: int) -> tuple[dict, pd.DataFrame, pd.Series]:
    """Audit one strategy with a hard temporal partition at evaluation year."""
    if strategy not in ("eligible_historical", "all_historical"):
        raise ValueError("Unknown pool strategy")
    eligible_ids = set(eligibility.loc[eligibility.eligible, "work_id"])
    history = historical_citers(works, references, evaluation_year=evaluation_year,
                               eligible_ids=eligible_ids if strategy == "eligible_historical" else None)
    frequency = candidate_frequency(references, history)
    pool = candidate_pool(frequency, threshold)
    queries = eligibility.loc[eligibility.eligible & eligibility.publication_year.eq(evaluation_year)]
    dates = works.set_index("work_id").publication_date
    detail = coverage_per_query(queries, references, pool, dates)
    row = coverage_summary(detail, threshold=threshold, period=str(evaluation_year),
                           group_by="all", group="all", pool_size=len(pool))
    row.update({"strategy": strategy, "evaluation_year": evaluation_year,
                "historical_cutoff_year": evaluation_year - 1,
                "historical_citing_works": len(history),
                "historical_distinct_edges": int(references.citing_work_id.isin(history).sum()),
                "candidate_ids_before_threshold": len(frequency)})
    return row, detail, frequency


def reassess(works: pd.DataFrame, references: pd.DataFrame, *,
             seeds: tuple[int, ...] = (20261028, 20261029, 20261030,
                                       20261031, 20261032)) -> dict[str, pd.DataFrame]:
    """Compare original/expanded pools and repeated nested saturation curves."""
    eligibility = query_eligibility(works, references)
    rows: list[dict] = []
    groups: list[dict] = []
    for year in (2023, 2024, 2025):
        for strategy in ("eligible_historical", "all_historical"):
            for threshold in (1, 2, 3):
                row, detail, _ = pool_audit(works, references, eligibility,
                                            evaluation_year=year,
                                            strategy=strategy, threshold=threshold)
                rows.append(row)
                if year == 2023:
                    for field in ("work_type", "primary_subfield_id"):
                        for value, part in detail.groupby(field, sort=True):
                            group = coverage_summary(part, threshold=threshold,
                                                     period=str(year), group_by=field,
                                                     group=str(value), pool_size=row["pool_size"])
                            group.update({"strategy": strategy, "evaluation_year": year})
                            groups.append(group)
    saturation: list[dict] = []
    year = 2023
    history = historical_citers(works, references, evaluation_year=year)
    queries = eligibility.loc[eligibility.eligible & eligibility.publication_year.eq(year)]
    dates = works.set_index("work_id").publication_date
    for seed in seeds:
        for fraction in (.25, .5, .75, 1.0):
            subset = nested_query_subset(history, fraction, seed)
            frequency = candidate_frequency(references, subset)
            for threshold in (1, 2, 3):
                pool = candidate_pool(frequency, threshold)
                detail = coverage_per_query(queries, references, pool, dates)
                summary = coverage_summary(detail, threshold=threshold, period="2023",
                                           group_by="all", group="all", pool_size=len(pool))
                summary.update({"seed": seed, "historical_fraction": fraction,
                                "historical_citing_works": len(subset),
                                "historical_distinct_edges": int(
                                    references.citing_work_id.isin(subset).sum())})
                saturation.append(summary)
    return {"pool_comparison": pd.DataFrame(rows),
            "coverage_subgroups_2023": pd.DataFrame(groups),
            "saturation_replicates": pd.DataFrame(saturation),
            "query_eligibility": eligibility}


def run_reassessment(*, processed_dir: Path, plan: Path, population: Path,
                     config: Path, output_dir: Path) -> dict:
    if output_dir.exists():
        raise FileExistsError(f"Refusing to overwrite existing reassessment: {output_dir}")
    if output_dir.resolve().is_relative_to(processed_dir.resolve()):
        raise ValueError("Output must not be inside the immutable Phase 3 source")
    tables, _, _ = load_verified_tables(processed_dir, plan, population, config)
    works, refs = tables["works"], tables["references"]
    results = reassess(works, refs)
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".phase5_reassess_", dir=output_dir.parent) as temp:
        stage = Path(temp)
        for name, frame in results.items():
            frame.to_csv(stage / f"{name}.csv", index=False,
                         float_format="%.12g", lineterminator="\n")
        curve = results["saturation_replicates"]
        fig, ax = plt.subplots(figsize=(8, 5))
        for threshold, part in curve.groupby("minimum_citers"):
            for _, seed_rows in part.groupby("seed"):
                ax.plot(seed_rows.pool_size, seed_rows.median_coverage,
                        alpha=.25, linewidth=1)
            middle = part.groupby("historical_fraction").agg(
                pool_size=("pool_size", "median"), median=("median_coverage", "median"))
            ax.plot(middle.pool_size, middle["median"], marker="o", linewidth=2,
                    label=f"≥{threshold} citing works")
        ax.set(xlabel="Candidate IDs in observed historical pool",
               ylabel="Median 2023 reference-ID overlap",
               title="Observed pool growth; five fixed-seed historical subsamples")
        ax.legend()
        fig.tight_layout()
        fig.savefig(stage / "pool_saturation_2023.png", dpi=180)
        plt.close(fig)
        outputs = {p.name: {"sha256": file_sha256(p), "bytes": p.stat().st_size}
                   for p in sorted(stage.iterdir()) if p.is_file()}
        manifest = {"status": "complete", "complete": True,
                    "created_at_utc": datetime.now(timezone.utc).isoformat(),
                    "source_phase3_manifest_sha256": file_sha256(processed_dir / "manifest.json"),
                    "source_works_sha256": file_sha256(processed_dir / "works.parquet"),
                    "source_references_sha256": file_sha256(processed_dir / "references.parquet"),
                    "evaluation_years": [2023, 2024, 2025],
                    "cutoff_rule": "citing publication_year < evaluation_year; no evaluation edges",
                    "saturation_seeds": list((20261028, 20261029, 20261030, 20261031, 20261032)),
                    "outputs": outputs}
        (stage / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        if output_dir.exists():
            raise FileExistsError(output_dir)
        stage.replace(output_dir)
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Reassess historical citation candidate pools")
    parser.add_argument("--processed-dir", type=Path, default=Path(
        "data/processed/openalex_stratified/stratified_20261019T155909Z"))
    parser.add_argument("--plan", type=Path, default=Path("data/metadata/phase2_sampling_plan.json"))
    parser.add_argument("--population", type=Path, default=Path(
        "data/metadata/population_counts_pre_phase2.json"))
    parser.add_argument("--config", type=Path, default=Path("config/topics.yaml"))
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    manifest = run_reassessment(processed_dir=args.processed_dir, plan=args.plan,
                                population=args.population, config=args.config,
                                output_dir=args.output_dir)
    print(json.dumps({"status": manifest["status"], "output_dir": str(args.output_dir)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
