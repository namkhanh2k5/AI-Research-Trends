"""Read-only Phase 5 G1/G2 and RQ5 audit of verified Phase 3 Parquet data."""

from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from ai_research_trends.analysis.load_data import load_verified_tables
from ai_research_trends.analysis.reference_eda import (
    reference_age_subset, reference_concentration, top_subarea_references,
)
from ai_research_trends.ml.feasibility import (
    candidate_frequency, candidate_pool, coverage_per_query, coverage_summary,
    eligibility_by, nested_query_subset, query_eligibility,
)
from ai_research_trends.preprocessing.validate_tables import file_sha256


DEFAULT_PROCESSED = Path("data/processed/openalex_stratified/stratified_20261019T155909Z")
DEFAULT_PLAN = Path("data/metadata/phase2_sampling_plan.json")
DEFAULT_POPULATION = Path("data/metadata/population_counts_pre_phase2.json")
DEFAULT_CONFIG = Path("config/topics.yaml")
REPORT_NAMES = ("PHASE5_FEASIBILITY_REPORT.md", "PHASE5_REFERENCE_EDA_REPORT.md",
                "PHASE5_ML_PILOT_REPORT.md")


def _reference_distribution(frame: pd.DataFrame, group: str) -> pd.DataFrame:
    rows = []
    for value, part in frame.groupby(group, sort=True, dropna=False):
        counts = part.matched_references
        rows.append({group: value, "sample_works": len(part), "mean_matched_references": counts.mean(),
                     "median_matched_references": counts.median(), "p90_matched_references": counts.quantile(.9),
                     "max_matched_references": int(counts.max()),
                     "present_lists": int(part.reference_list_status.eq("present").sum()),
                     "empty_lists": int(part.reference_list_status.eq("empty").sum()),
                     "missing_lists": int(part.reference_list_status.eq("missing").sum())})
    return pd.DataFrame(rows)


def _plot_bar(years: pd.DataFrame, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.bar(years.publication_year.astype(str), years.sample_works, color="#d7e5ef", label="sampled")
    ax.bar(years.publication_year.astype(str), years.eligible_10, color="#21618c", label="eligible")
    ax.set(xlabel="Publication year", ylabel="Sampled works", title="RQ5 query eligibility: title, usable abstract, ≥10 matched references")
    ax.legend(); fig.tight_layout(); fig.savefig(path, dpi=180); plt.close(fig)


def _plot_coverage(queries: pd.DataFrame, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(8, 4.5))
    for threshold in (1, 2, 3):
        values = queries.loc[(queries.minimum_citers.eq(threshold)) &
                             (queries.publication_year.eq(2023)), "id_overlap_coverage"]
        ax.hist(values, bins=20, alpha=.42, label=f"≥{threshold} historical citers")
    ax.set(xlabel="Observed reference fraction in historical candidate pool (ID overlap)",
           ylabel="Eligible 2023 queries", title="G2 pool coverage; candidate dates mostly unknown")
    ax.legend(); fig.tight_layout(); fig.savefig(path, dpi=180); plt.close(fig)


def _plot_lorenz(lorenz: pd.DataFrame, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(6, 5))
    ax.plot(lorenz.reference_fraction, lorenz.edge_fraction, color="#21618c", label="observed references")
    ax.plot([0, 1], [0, 1], "--", color="#777777", label="equal share")
    ax.set(xlabel="Fraction of distinct referenced IDs", ylabel="Fraction of sampled citation edges",
           title="RQ5 concentration within sampled citation edges")
    ax.legend(); fig.tight_layout(); fig.savefig(path, dpi=180); plt.close(fig)


def _plot_reference_counts(frame: pd.DataFrame, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.hist(frame.matched_references.clip(upper=150), bins=35, color="#148f77")
    ax.set(xlabel="Matched references per sampled work (150+ clipped for display)",
           ylabel="Sampled works", title="RQ5 observed reference-list distribution")
    fig.tight_layout(); fig.savefig(path, dpi=180); plt.close(fig)


def _fmt(value: float, digits: int = 1) -> str:
    return f"{value:.{digits}f}" if math.isfinite(value) else "not estimable"


def _reports(*, source: Path, eligibility: pd.DataFrame,
             eligibility_year: pd.DataFrame, eligibility_type: pd.DataFrame,
             eligibility_subfield: pd.DataFrame, coverage: pd.DataFrame,
             sensitivity: pd.DataFrame, concentration: dict, age: dict,
             overlap: pd.DataFrame, top: pd.DataFrame, age_by_subfield: pd.DataFrame,
             rows: dict[str, int],
             decision: str, source_hashes: dict[str, str], report_dir: Path,
             published_figure_dir: Path) -> dict[str, str]:
    g = coverage.loc[(coverage.minimum_citers.eq(2)) & (coverage.period.eq("2023")) &
                     (coverage.group_by.eq("all"))].iloc[0]
    p1 = coverage.loc[(coverage.minimum_citers.eq(1)) & (coverage.period.eq("2023")) &
                      (coverage.group_by.eq("all"))].iloc[0]
    p3 = coverage.loc[(coverage.minimum_citers.eq(3)) & (coverage.period.eq("2023")) &
                      (coverage.group_by.eq("all"))].iloc[0]
    images = lambda name: os.path.relpath(published_figure_dir / name, report_dir)
    by_year = "\n".join(
        f"| {int(r.publication_year)} | {int(r.sample_works):,} | {int(r.valid_title):,} | "
        f"{int(r.usable_abstract):,} | {int(r.reference_list_present):,} | "
        f"{int(r.refs_ge_5):,} | {int(r.refs_ge_10):,} | {int(r.refs_ge_15):,} | "
        f"{int(r.eligible_10):,} | {r.eligible_percent:.1f}% |"
        for r in eligibility_year.itertuples(index=False))
    by_type = "\n".join(
        f"| {r.work_type} | {int(r.sample_works):,} | {int(r.usable_abstract):,} | "
        f"{int(r.reference_list_present):,} | {int(r.eligible_10):,} | {r.eligible_percent:.1f}% |"
        for r in eligibility_type.itertuples(index=False))
    by_subfield = "\n".join(
        f"| {str(r.primary_subfield_id).rsplit('/', 1)[-1]} | {int(r.sample_works):,} | "
        f"{int(r.eligible_10):,} | {r.eligible_percent:.1f}% |"
        for r in eligibility_subfield.itertuples(index=False))
    pool_rows = "\n".join(
        f"| ≥{int(r.minimum_citers)} | {int(r.pool_size):,} | {int(r.queries):,} | "
        f"{r.mean_coverage:.1%} | {r.median_coverage:.1%} | "
        f"{r.p10_coverage:.1%} | {r.p25_coverage:.1%} | {r.p75_coverage:.1%} | "
        f"{r.p90_coverage:.1%} | {r.zero_coverage_percent:.1f}% |"
        for r in (p1, g, p3))
    coverage_year_rows = "\n".join(
        f"| {r.period} | {int(r.queries):,} | {r.mean_coverage:.1%} | "
        f"{r.median_coverage:.1%} | {r.zero_coverage_percent:.1f}% |"
        for r in coverage.loc[(coverage.minimum_citers.eq(2)) &
                              (coverage.group_by.eq("all"))].itertuples(index=False))
    coverage_subfield_rows = "\n".join(
        f"| {r.group.rsplit('/', 1)[-1]} | {int(r.queries):,} | {r.mean_coverage:.1%} | "
        f"{r.median_coverage:.1%} | {r.zero_coverage_percent:.1f}% |"
        for r in coverage.loc[(coverage.minimum_citers.eq(2)) &
                              (coverage.period.eq("2023")) &
                              (coverage.group_by.eq("primary_subfield_id"))].itertuples(index=False))
    coverage_type_rows = "\n".join(
        f"| {r.group} | {int(r.queries):,} | {r.mean_coverage:.1%} | "
        f"{r.median_coverage:.1%} | {r.zero_coverage_percent:.1f}% |"
        for r in coverage.loc[(coverage.minimum_citers.eq(2)) &
                              (coverage.period.eq("2023")) &
                              (coverage.group_by.eq("work_type"))].itertuples(index=False))
    coverage_native_rows = "\n".join(
        f"| {r.group.replace('_', ' ')} | {int(r.queries):,} | {r.mean_coverage:.1%} | "
        f"{r.median_coverage:.1%} | {r.zero_coverage_percent:.1f}% |"
        for r in coverage.loc[(coverage.minimum_citers.eq(2)) &
                              (coverage.period.eq("2023")) &
                              (coverage.group_by.eq("openalex_native_category"))].itertuples(index=False))
    sensitivity_rows = "\n".join(
        f"| {r.historical_fraction:.0%} | {int(r.historical_queries):,} | "
        f"{int(r.pool_size):,} | {r.median_coverage:.1%} |"
        for r in sensitivity.loc[sensitivity.minimum_citers.eq(2)].sort_values(
            "historical_fraction").itertuples(index=False))
    source_lines = "\n".join(f"- `{source / (name + '.parquet')}` — SHA-256 `{digest}`"
                             for name, digest in source_hashes.items())
    feasibility = f"""# Phase 5 G1/G2 literature-discovery feasibility audit

Decision: **{decision}** for a supervised citation-aware recommender using only the current local candidate pool.

## Inputs and definitions

Read-only verified Phase 3 input: `{source}`. Exact table sizes: {rows['works']:,} sampled works,
{rows['references']:,} unique directed reference edges, {rows['categories']:,} category memberships.
Source checksums:\n{source_lines}

The approved OpenAlex population aggregates are **not** this downloaded candidate pool.
A query requires a nonblank title, an abstract of at least 50 characters and eight words,
at least ten matched canonical references, and a valid 2020–2025 publication date consistent
with its year. This operational text threshold is exploratory, not a semantic quality judgment.
`reference_list_status=empty` is distinct from `missing`; an empty OpenAlex list does not prove
the paper cites nothing. Reference edges are unique by citing/referenced Work ID.

## G1 — query eligibility

| Year | Sample n | Valid title | Usable abstract | Recorded list | ≥5 refs | ≥10 refs | ≥15 refs | Eligible | Eligible % |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
{by_year}

| Work type | Sample n | Usable abstract | Recorded list | Eligible | Eligible % |
|---|---:|---:|---:|---:|---:|
{by_type}

| Primary subfield | Sample n | Eligible | Eligible % |
|---|---:|---:|---:|
{by_subfield}

Overall eligible: {int(eligibility.eligible.sum()):,}/{len(eligibility):,}
({_fmt(100 * eligibility.eligible.mean())}%). Threshold sensitivity:
≥5 references {int(eligibility.eligible_5.sum()):,}, ≥10 {int(eligibility.eligible_10.sum()):,},
≥15 {int(eligibility.eligible_15.sum()):,} works. Present lists:
{int(eligibility.reference_list_status.eq('present').sum()):,}; empty lists:
{int(eligibility.reference_list_status.eq('empty').sum()):,}; missing lists:
{int(eligibility.reference_list_status.eq('missing').sum()):,}.
Missing/short abstracts: {int((~eligibility.usable_abstract).sum()):,}; missing titles:
{int((~eligibility.valid_title).sum()):,}; date inconsistencies:
{int((~eligibility.valid_date).sum()):,}. Denominators are sampled works, not population works.

![G1 query eligibility by year]({images('query_eligibility_by_year.png')})

## G2 — 2023 historical pool coverage

Historical eligible citing queries: 2020–2022 only. Candidate IDs come from their observed
reference lists; frequency is the number of **distinct** historical citing queries.
Evaluation queries are eligible 2023 works; they never contribute to pool frequencies.
The table is **ID-level pool overlap**, not candidate-generation recall. No text retriever
or reranker was evaluated. Most candidate publication dates are unavailable locally;
therefore these figures are not fully time-valid coverage estimates. Known future-dated
candidates are flagged separately, not assumed valid. Unknown dates cannot be certified.

| Min historical citers | Pool IDs | 2023 queries | Mean | Median | P10 | P25 | P75 | P90 | Zero coverage |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
{pool_rows}

At the preselected ≥2 setting, {int(g.id_overlap_edges):,} of
{int(g.observed_reference_edges):,} observed 2023 reference edges overlap the pool;
{int(g.known_future_hits):,} overlapping edges have known post-query dates and
{int(g.unknown_date_hits):,} have **unknown** candidate dates. The 2023 median
overlap of {g.median_coverage:.1%} is below the provisional 40% gate. Even relaxing to
≥1 historical citer yields median {p1.median_coverage:.1%}. The frequency ≥3 pool
falls to median {p3.median_coverage:.1%}. See `coverage_summary.csv` for year,
work-type and primary-subfield breakdowns and `historical_fraction_sensitivity.csv`
for nested 25/50/75/100% historical-query subsamples. Increasing the historical
fraction changes measured overlap, but extrapolation beyond these data is not guaranteed.

Coverage by evaluation year for the same fixed 2020–2022 ≥2-citer pool:

| Year | Eligible queries | Mean ID overlap | Median ID overlap | Zero coverage |
|---:|---:|---:|---:|---:|
{coverage_year_rows}

2023 subgroup checks (primary subfield and work type are separate groupings):

| Primary subfield | Queries | Mean ID overlap | Median ID overlap | Zero coverage |
|---|---:|---:|---:|---:|
{coverage_subfield_rows}

| Work type | Queries | Mean ID overlap | Median ID overlap | Zero coverage |
|---|---:|---:|---:|---:|
{coverage_type_rows}

Selected overlapping OpenAlex-native research-category memberships among 2023
eligible queries (these rows cannot be summed):

| Native category | Member queries | Mean ID overlap | Median ID overlap | Zero coverage |
|---|---:|---:|---:|---:|
{coverage_native_rows}

Nested historical-query fraction sensitivity at ≥2 citers (seeded Work-ID order):

| Historical fraction | Citing queries | Pool IDs | 2023 median ID overlap |
|---:|---:|---:|---:|
{sensitivity_rows}

Known post-query candidates are excluded from the separate
`screened_overlap_coverage` measure, but unknown dates remain uncertified. Even
screened overlap is **not** a fully time-valid coverage estimate.

![G2 2023 pool coverage]({images('pool_coverage_2023.png')})

## Decision and next smallest experiment

**{decision}.** G1 has usable queries, but G2 is the bottleneck. Do not train or claim
a supervised literature recommender yet: low pool overlap caps end-to-end recall,
and candidate publication metadata is missing for most reference IDs. First run a
small, separate expansion experiment with additional **historical citing works**
(not a blind 20,000–30,000-paper crawl), measuring incremental 2023 coverage at
frequency thresholds 1/2/3. Independently enrich publication dates for a targeted
candidate subset to establish temporal validity. Reassess feasibility before modeling.
Neither the observed fixed-seed sample nor nominal year weights establish known
probability sampling. Missing references are not evidence of no citations.
"""
    overlap_line = "; ".join(f"{r.subfield_a.rsplit('/', 1)[-1]} vs {r.subfield_b.rsplit('/', 1)[-1]}: "
                             f"{int(r.intersection)}/{int(r.union)} (Jaccard {r.jaccard:.3f})"
                             for r in overlap.itertuples(index=False)) or "not estimable"
    age_rows = "\n".join(
        f"| {r.primary_subfield_id.rsplit('/', 1)[-1]} | {int(r.known_date_edges):,} | "
        f"{int(r.nonfuture_edges):,} | {_fmt(r.median_age_years, 2)} | "
        f"{_fmt(r.within_five_years_percent)}% |"
        for r in age_by_subfield.itertuples(index=False))
    top_rows = "\n".join(
        f"| {r.primary_subfield_id.rsplit('/', 1)[-1]} | {int(r.rank)} | "
        f"{r.referenced_work_id} | {int(r.sample_citing_works):,} |"
        for r in top.loc[top["rank"].le(5)].itertuples(index=False))
    rq5 = f"""# RQ5 — What prior literature does sampled AI/CV research build on?

This is an **exploratory Phase 5 extension** to RQ1–RQ4. It describes reference
frequencies within {rows['works']:,} sampled citing works, not all OpenAlex works,
global citation counts, scientific quality or mandatory citations. The fixed-seed
sample is not a verified probability sample.

## Reference availability

{rows['references']:,} unique edges point to {concentration.get('distinct_referenced_works', 0):,}
distinct referenced Work IDs. The sample has
{int(eligibility.reference_list_status.eq('present').sum()):,} recorded nonempty lists,
{int(eligibility.reference_list_status.eq('empty').sum()):,} recorded empty lists, and
{int(eligibility.reference_list_status.eq('missing').sum()):,} missing lists.
`reference_distribution_by_year.csv`, `reference_distribution_by_type.csv`,
`reference_distribution_by_subfield.csv` and `reference_availability_native_categories.csv`
give denominators and missingness. Native category memberships overlap; they are not
exclusive subareas. List absence is not proof that a work cites nothing.

![Observed reference counts per sampled work]({images('references_per_work.png')})

## Observed citation concentration

Gini coefficient of distinct sampled citing-work frequencies:
{_fmt(concentration.get('gini', float('nan')), 3)}. The top 1% and 5% of
referenced IDs account for {_fmt(100 * concentration.get('top_1_percent_share', float('nan')))}%
and {_fmt(100 * concentration.get('top_5_percent_share', float('nan')))}% of observed
edges, respectively. This is within-sample concentration, not global influence.

![Lorenz curve for sampled reference edges]({images('reference_lorenz.png')})

## Reference age and metadata coverage

Only {age['matched_age_edges']:,}/{rows['references']:,} observed edges have a
referenced work also present in the 12,000-work sample and thus a locally verified
publication date. {age['missing_candidate_date_edges']:,} edges lack local candidate
date metadata; {age['future_dated_edges']:,} matched edges are future-dated relative
to their citing paper and are excluded from age summaries. For the
{age['valid_age_edges']:,} non-future matched edges only, median age is
{_fmt(age['median_age_years'], 2)} years and {_fmt(age['within_five_years_percent'])}%
are at most five years old. These are a highly selected matched-in-sample subset,
**not** an estimate of reference age in the full citation graph. `reference_age_known.csv`
and `reference_age_by_subfield.csv` preserve the restricted denominator. No dates
were invented for external referenced IDs.

| Citing primary subfield | Known-date edges | Non-future edges | Median age (years) | Within five years |
|---|---:|---:|---:|---:|
{age_rows}

These subfield differences are **not** generalizable because date coverage is
tiny and selected by whether the cited work also appears in the sample.

## Primary-subfield core lists

`top_references_by_subfield.csv` ranks each primary subfield's top 20 referenced IDs
by distinct supporting sampled citing works. Titles appear only when a referenced
work is itself in the local sample. Top-list overlap: {overlap_line}. This is a
descriptive signal of shared versus specialized observed reference lists, not a
research-quality ranking. Most cited IDs lack local title/age metadata; no external
metadata were fetched in this pilot.

| Citing primary subfield | Rank | Referenced Work ID | Distinct sampled citing works |
|---|---:|---|---:|
{top_rows}

## Coverage and inference limits

The ≥2-citer historical candidate pool has {int(g.pool_size):,} IDs, and its
eligible 2023 query median **ID-level** reference overlap is {g.median_coverage:.1%}.
Pool overlap is the ceiling for a retriever that can only rank those IDs;
candidate-generation recall has **not** been measured. A fixed-seed sample of
citing works, incomplete references, unknown candidate dates and possible OpenAlex
metadata updates limit inference. See the [G1/G2 feasibility report](PHASE5_FEASIBILITY_REPORT.md).
"""
    not_run = "\n".join(f"| {name} | Not run | Not run | Not run | Not run | G2/temporal-metadata gate failed |"
                        for name in ("Global Popularity", "Subarea Popularity", "BM25", "Co-citation",
                                     "Rank Fusion", "Logistic Regression", "Random Forest",
                                     "LightGBM Classifier", "LambdaMART"))
    ml = f"""# Phase 5 ML pilot decision — {decision}

No supervised ranking experiment or inference recommender was run. The decision
was made **before model comparison** from the verified G1/G2 audit: the 2023
median ID-level pool overlap is {g.median_coverage:.1%} at ≥2 historical citers,
and only {age['matched_age_edges']:,}/{rows['references']:,} edges have candidate
publication dates available in the local sample. Candidate-generation recall,
Recall@10/20, nDCG@20, MRR, warm/cold-start and latency are **not measured**.
Reporting model scores now would hide the candidate-pool and temporal-validity
bottlenecks.

| Method | Recall@20 | nDCG@20 | MRR | Latency | Reason |
|---|---|---|---|---|---|
{not_run}

The code provides tested, deterministic eligibility, historical pool construction,
leave-one-query-out popularity, visible/hidden reference splitting and implicit
negative sampling primitives for a later controlled experiment. An uncited candidate
is unobserved, not human-confirmed irrelevant. Historical citation recovery is at
most a proxy for relevance; no human evaluation or citation-necessity claim exists.
No saved model, vectorizer, candidate index or website was created.

Next: a small separate historical-citing-work expansion and targeted candidate-date
enrichment, followed by a new gate audit. Only if coverage and temporal validity
improve should the team fit BM25 and leakage-safe ranking baselines, then compare
Logistic Regression/other models on query-disjoint temporal folds.
"""
    return dict(zip(REPORT_NAMES, (feasibility, rq5, ml), strict=True))


def run_audit(*, processed_dir: Path, plan: Path, population: Path, config: Path,
              output_dir: Path, report_dir: Path, published_figure_dir: Path,
              replace_reports: bool = False, seed: int = 20261028) -> dict:
    """Verify sources, audit once, and atomically publish a new versioned run."""
    for target in (output_dir, report_dir, published_figure_dir):
        if target.resolve().is_relative_to(processed_dir.resolve()):
            raise ValueError("Phase 5 output must not be written inside the immutable Phase 3 source")
    if output_dir.exists():
        raise FileExistsError(f"Refusing to overwrite Phase 5 audit: {output_dir}")
    targets = [report_dir / name for name in REPORT_NAMES]
    if not replace_reports and any(path.exists() for path in targets):
        raise FileExistsError("Phase 5 report already exists; select a new report directory")
    if replace_reports and any(path.exists() and not path.read_text(encoding="utf-8").startswith(
        ("# Phase 5", "# RQ5")) for path in targets):
        raise ValueError("Refusing to replace a report that is not a Phase 5 output")
    tables, _, _ = load_verified_tables(processed_dir, plan, population, config)
    works, refs, membership = (tables[name] for name in ("works", "references", "category_membership"))
    eligibility = query_eligibility(works, refs)
    g1_year = eligibility_by(eligibility, "publication_year")
    g1_type = eligibility_by(eligibility, "work_type")
    g1_subfield = eligibility_by(eligibility, "primary_subfield_id")
    native = membership.loc[membership.analytical_layer.eq("openalex_native"), ["work_id", "category"]]
    category_availability = eligibility[["work_id", "reference_list_status", "matched_references",
                                         "usable_abstract", "eligible"]].merge(
        native, on="work_id", how="inner", validate="one_to_many")
    availability_rows = []
    for name, part in category_availability.groupby("category"):
        availability_rows.append({"category": name, "member_works": part.work_id.nunique(),
                                  "present_lists": int(part.reference_list_status.eq("present").sum()),
                                  "empty_lists": int(part.reference_list_status.eq("empty").sum()),
                                  "usable_abstract": int(part.usable_abstract.sum()),
                                  "eligible_queries": int(part.eligible.sum())})
    eligible = eligibility.loc[eligibility.eligible]
    historical_ids = set(eligible.loc[eligible.publication_year.le(2022), "work_id"])
    evaluation = eligible.loc[eligible.publication_year.ge(2023)]
    candidate_dates = works.set_index("work_id").publication_date
    frequencies = candidate_frequency(refs, historical_ids)
    coverage_parts = []
    summaries = []
    for threshold in (1, 2, 3):
        pool = candidate_pool(frequencies, threshold)
        detail = coverage_per_query(evaluation, refs, pool, candidate_dates)
        detail["minimum_citers"] = threshold
        coverage_parts.append(detail)
        for year, group in detail.groupby("publication_year"):
            summaries.append(coverage_summary(group, threshold=threshold, period=str(year),
                                               group_by="all", group="all", pool_size=len(pool)))
        focus = detail.loc[detail.publication_year.eq(2023)]
        for field in ("work_type", "primary_subfield_id"):
            for value, group in focus.groupby(field):
                summaries.append(coverage_summary(group, threshold=threshold, period="2023",
                                                   group_by=field, group=str(value), pool_size=len(pool)))
        native_focus = focus.merge(native, on="work_id", how="inner", validate="one_to_many")
        for value, group in native_focus.groupby("category"):
            summaries.append(coverage_summary(group, threshold=threshold, period="2023",
                                               group_by="openalex_native_category", group=value,
                                               pool_size=len(pool)))
    coverage_queries = pd.concat(coverage_parts, ignore_index=True)
    coverage = pd.DataFrame(summaries)
    sensitivity = []
    eval_2023 = evaluation.loc[evaluation.publication_year.eq(2023)]
    for fraction in (.25, .5, .75, 1.0):
        subset = nested_query_subset(historical_ids, fraction, seed)
        frequency = candidate_frequency(refs, subset)
        for threshold in (1, 2, 3):
            pool = candidate_pool(frequency, threshold)
            detail = coverage_per_query(eval_2023, refs, pool, candidate_dates)
            row = coverage_summary(detail, threshold=threshold, period="2023",
                                   group_by="all", group="all", pool_size=len(pool))
            row.update({"historical_fraction": fraction, "historical_queries": len(subset)})
            sensitivity.append(row)
    citation_frequency, lorenz, concentration = reference_concentration(refs)
    ages, age_stats = reference_age_subset(works, refs)
    age_by_subfield = pd.DataFrame([
        {"primary_subfield_id": field, "known_date_edges": len(part),
         "nonfuture_edges": int((~part.future_dated).sum()),
         "median_age_years": part.loc[~part.future_dated, "age_years"].median(),
         "within_five_years_percent": 100 * part.loc[~part.future_dated, "age_years"].le(5).mean()}
        for field, part in ages.groupby("citing_subfield")])
    top, overlap = top_subarea_references(works, refs)
    g2 = coverage.loc[(coverage.minimum_citers.eq(2)) & (coverage.period.eq("2023")) &
                      (coverage.group_by.eq("all"))].iloc[0]
    decision = "GO" if g2.median_coverage >= .4 and g2.zero_coverage_percent <= 10 and (
        g2.unknown_date_hits / max(1, g2.id_overlap_edges)) <= .1 else "REVISE"
    outputs = {
        "query_eligibility.csv": eligibility,
        "eligibility_by_year.csv": g1_year,
        "eligibility_by_work_type.csv": g1_type,
        "eligibility_by_subfield.csv": g1_subfield,
        "reference_availability_native_categories.csv": pd.DataFrame(availability_rows),
        "reference_distribution_by_year.csv": _reference_distribution(eligibility, "publication_year"),
        "reference_distribution_by_type.csv": _reference_distribution(eligibility, "work_type"),
        "reference_distribution_by_subfield.csv": _reference_distribution(eligibility, "primary_subfield_id"),
        "coverage_queries.csv": coverage_queries,
        "coverage_summary.csv": coverage,
        "historical_fraction_sensitivity.csv": pd.DataFrame(sensitivity),
        "historical_candidate_frequencies.csv": frequencies.rename("historical_citing_queries").rename_axis(
            "referenced_work_id").reset_index(),
        "sample_reference_frequencies.csv": citation_frequency,
        "reference_lorenz.csv": lorenz,
        "reference_age_known.csv": ages,
        "reference_age_by_subfield.csv": age_by_subfield,
        "top_references_by_subfield.csv": top,
        "top_list_overlap.csv": overlap,
    }
    source_hashes = {name: file_sha256(processed_dir / f"{name}.parquet")
                     for name in ("works", "references", "category_membership")}
    report_texts = _reports(source=processed_dir,
                            eligibility=eligibility, eligibility_year=g1_year,
                            eligibility_type=g1_type, eligibility_subfield=g1_subfield,
                            coverage=coverage, sensitivity=pd.DataFrame(sensitivity),
                            concentration=concentration, age=age_stats, overlap=overlap,
                            top=top, age_by_subfield=age_by_subfield,
                            rows={"works": len(works), "references": len(refs),
                                           "categories": len(membership)}, decision=decision,
                            source_hashes=source_hashes, report_dir=report_dir,
                            published_figure_dir=published_figure_dir)
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".phase5_stage_", dir=output_dir.parent) as temporary:
        stage = Path(temporary)
        figures = stage / "figures"
        figures.mkdir()
        _plot_bar(g1_year, figures / "query_eligibility_by_year.png")
        _plot_coverage(coverage_queries, figures / "pool_coverage_2023.png")
        _plot_lorenz(lorenz, figures / "reference_lorenz.png")
        _plot_reference_counts(eligibility, figures / "references_per_work.png")
        for name, table in outputs.items():
            table.to_csv(stage / name, index=False, float_format="%.12g", lineterminator="\n")
        for name, body in report_texts.items():
            (stage / name).write_text(body, encoding="utf-8")
        files = {path.relative_to(stage).as_posix(): {"sha256": file_sha256(path),
                                                       "bytes": path.stat().st_size}
                 for path in sorted(stage.rglob("*")) if path.is_file()}
        manifest = {"schema_version": 1, "analysis_version": "phase5-feasibility-v1",
                    "created_at_utc": datetime.now(timezone.utc).isoformat(),
                    "status": "complete", "complete": True, "decision": decision,
                    "historical_years": [2020, 2021, 2022], "evaluation_year": 2023,
                    "seed": seed, "source_phase3_manifest_sha256": file_sha256(processed_dir / "manifest.json"),
                    "source_tables_sha256": source_hashes, "outputs": files,
                    "query_eligibility": int(eligibility.eligible.sum()),
                    "evaluation_queries_2023": int(eval_2023.shape[0]),
                    "coverage_threshold_2_median": float(g2.median_coverage),
                    "limitation": "ID-level overlap; unknown candidate publication dates; no model evaluated"}
        (stage / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        if output_dir.exists():
            raise FileExistsError(f"Phase 5 output appeared during staging: {output_dir}")
        stage.replace(output_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    published_figure_dir.mkdir(parents=True, exist_ok=True)
    for source in sorted((output_dir / "figures").glob("*.png")):
        target = published_figure_dir / source.name
        if target.exists():
            if file_sha256(target) != file_sha256(source):
                raise ValueError(f"Published Phase 5 figure differs: {target}")
        else:
            shutil.copyfile(source, target)
    for name in REPORT_NAMES:
        target = report_dir / name
        temporary = target.with_suffix(target.suffix + ".part")
        shutil.copyfile(output_dir / name, temporary)
        temporary.replace(target)
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit RQ5 query and historical candidate-pool feasibility")
    parser.add_argument("--processed-dir", type=Path, default=DEFAULT_PROCESSED)
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    parser.add_argument("--population", type=Path, default=DEFAULT_POPULATION)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-dir", type=Path, required=True,
                        help="New, immutable Phase 5 audit directory")
    parser.add_argument("--report-dir", type=Path, default=Path("reports"))
    parser.add_argument("--published-figure-dir", type=Path,
                        default=Path("reports/figures/phase5"))
    parser.add_argument("--replace-reports", action="store_true",
                        help="Explicitly replace only existing Phase 5 reports, never Phase 1–4 outputs")
    parser.add_argument("--seed", type=int, default=20261028)
    args = parser.parse_args(argv)
    manifest = run_audit(processed_dir=args.processed_dir, plan=args.plan,
                         population=args.population, config=args.config,
                         output_dir=args.output_dir, report_dir=args.report_dir,
                         published_figure_dir=args.published_figure_dir,
                         replace_reports=args.replace_reports, seed=args.seed)
    print(json.dumps({"decision": manifest["decision"], "eligible_queries": manifest["query_eligibility"],
                      "evaluation_queries_2023": manifest["evaluation_queries_2023"],
                      "coverage_threshold_2_median": manifest["coverage_threshold_2_median"],
                      "output_dir": str(args.output_dir)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
