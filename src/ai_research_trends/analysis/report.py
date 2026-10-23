"""Render an academic Phase 4 report strictly from verified analytical results."""

from __future__ import annotations

import math

import pandas as pd


def _number(value: float, digits: int = 2) -> str:
    return f"{value:,.{digits}f}" if math.isfinite(float(value)) else "not estimable"


def render_report(t: dict[str, pd.DataFrame], *, run_id: str, observed_at: str,
                  population_total: int, processed_hash: str, seed: int) -> str:
    growth = t["publication_trends"].sort_values("year")
    native = t["native_topic_trends"]
    emerging = t["emerging_topic_sample_trends"]
    citations = t["citation_descriptives"]
    fwci = t["fwci_descriptives"]
    oa = t["oa_descriptives"]
    binary_oa = t["oa_binary_descriptives"].sort_values("is_oa")
    models = t["oa_regression_results"]
    diagnostics = t["oa_model_diagnostics"]
    collab = t["collaboration_descriptives"].query("group_by == 'all'").iloc[0]
    network = t["network_metrics"]
    country = t["country_collaboration_edges"].nlargest(5, "weight_works")
    institution = t["institution_collaboration_edges"].nlargest(5, "weight_works")
    age_test = t["statistical_test_results"].iloc[0]
    whole_cite = citations.query("group_by == 'all' and metric == 'cited_by_count'").iloc[0]
    whole_fwci = fwci.query("group_by == 'all_eligible'").iloc[0]
    first, last = growth.iloc[0], growth.iloc[-1]
    cagr = ((last.work_count / first.work_count) ** (1 / 5) - 1) * 100
    primary = models.loc[(models.model == "adjusted_status_year") & models.term.str.startswith("oa_")]
    age_model = diagnostics.loc[diagnostics.model == "adjusted_status_age"].iloc[0]
    lines = [
        "# Phase 4: Exploratory and Statistical Analysis Report", "",
        "## 1. Executive summary", "",
        f"The approved OpenAlex AI/CV primary-subfield population contains **{population_total:,} non-retracted works** across 2020–2025. Annual volume rose from **{int(first.work_count):,}** to **{int(last.work_count):,}** ({_number(cagr)}% five-interval CAGR). These are complete-query aggregate counts, not sample estimates.",
        f"The detailed 12,000-work sample has a median of **{_number(whole_cite['median'], 0)}** observed citations versus a mean of **{_number(whole_cite['mean'])}**, highlighting skew. FWCI is observed for **{int(whole_fwci['n']):,}** articles/reviews and no sampled preprints.",
        f"OA-status associations are conditional, observational results; the primary model retains **{int(diagnostics.loc[diagnostics.model == 'adjusted_status_year', 'complete_cases'].iloc[0]):,}** works. International collaboration is explicitly unknown for **{int(collab.international_unknown):,}** works. None of these findings establishes causal impact or a global AI network.",
        "", "## 2. Research scope and methodology", "",
        "The corpus consists of OpenAlex articles, reviews and preprints dated 2020-01-01 through 2025-12-31 whose **primary** topic belongs to subfield 1702 or 1707. Retracted works are excluded from the primary series. It is not all worldwide AI research. The complete population aggregates are analyzed separately from a fixed-seed, year-stratified 12,000-work detailed sample. OpenAlex server-side sampling is not verified as a known-probability design; nominal `N_h/n_h` weights are not used to claim population-unbiased estimates or design-based intervals.",
        f"Source run: `{run_id}`; common citation observation time: `{observed_at}`; Phase 3 manifest SHA-256: `{processed_hash}`; analysis seed: `{seed}`. All work-level joins preserve the unique Work ID grain. Missing values remain null and are excluded only from analyses requiring that field. The predeclared [statistical analysis plan](../docs/PHASE4_STATISTICAL_ANALYSIS_PLAN.md) defines methods and model families before result interpretation.",
        "", "## 3. RQ1 — Publication and topic trends", "",
        "| Year | Population works | Absolute YoY | YoY % | 2020 index |", "|---:|---:|---:|---:|---:|",
    ]
    for row in growth.itertuples(index=False):
        change = "—" if pd.isna(row.absolute_yoy_change) else f"{int(row.absolute_yoy_change):+,}"
        yoy = "—" if pd.isna(row.yoy_growth_percent) else f"{row.yoy_growth_percent:+.2f}%"
        lines.append(f"| {row.year} | {int(row.work_count):,} | {change} | {yoy} | {row.index_2020_100:.1f} |")
    lines += [
        "",
        f"Across the five intervals, total change is **{int(last.work_count - first.work_count):+,} works** ({_number((last.work_count / first.work_count - 1) * 100)}%). No 2020 YoY rate is reported because there is no 2019 baseline.",
        "", "Selected OpenAlex-native topic series (membership overlaps):", "",
        "| Native series | 2020 count | 2025 count | 2025 share of primary corpus |", "|---|---:|---:|---:|",
    ]
    for name, group in native.groupby("series"):
        g = group.sort_values("year")
        lines.append(f"| {name.replace('_primary_non_retracted', '')} | {int(g.iloc[0].work_count):,} | {int(g.iloc[-1].work_count):,} | {g.iloc[-1].share_of_primary_percent:.2f}% |")
    lines += [
        "", "The native series share the approved primary-corpus and non-retraction filters. Their memberships overlap, so their counts cannot be summed into an AI total. Classification or database changes can affect apparent growth.",
        "", "Custom title/abstract matches in the detailed sample (exploratory, not population counts):", "",
        "| Text-rule category | Matched sampled works | 2025 matches | 2025 sample denominator |", "|---|---:|---:|---:|",
    ]
    for name, group in emerging.groupby("category"):
        end = group.loc[group.year == 2025].iloc[0]
        lines.append(f"| {name} | {int(group.matched_sample_works.sum()):,} | {int(end.matched_sample_works):,} | {int(end.sample_year_denominator):,} |")
    lines += [
        "", "The RAG rule identifies few works and has unmeasured recall; no RAG population trajectory is inferred. Abstract availability by year is included in the machine-readable table. Figures: [annual counts](figures/phase4/rq1_population_counts.png), [YoY](figures/phase4/rq1_yoy_growth.png), [index](figures/phase4/rq1_population_index.png), [native topics](figures/phase4/rq1_native_topic_trends.png), [sample text matches](figures/phase4/rq1_emerging_sample_trends.png).",
        "", "## 4. RQ2 — Citation impact", "",
        f"Observed citation counts: n={int(whole_cite['n']):,}; mean {_number(whole_cite['mean'])}; median {_number(whole_cite['median'])}; IQR {_number(whole_cite['iqr'])}; P90 {_number(whole_cite['p90'])}; P95 {_number(whole_cite['p95'])}; maximum {int(whole_cite['max']):,}; zero-citation share {_number(whole_cite['zero_percent'])}%. All zeroes and highly cited observations remain in the data. The mean–median gap is why robust summaries and log1p displays accompany raw counts.",
        "", "| Primary subfield | Sample n | Mean citations | Median citations | FWCI-eligible n | Median FWCI |", "|---|---:|---:|---:|---:|---:|",
    ]
    for label in ("1702", "1707"):
        c = citations.loc[(citations.group_by == "primary_subfield_id") & (citations.group == label) & (citations.metric == "cited_by_count")].iloc[0]
        f = fwci.loc[(fwci.group_by == "primary_subfield_id") & (fwci.group == label)].iloc[0]
        lines.append(f"| {label} | {int(c['n']):,} | {_number(c['mean'])} | {_number(c['median'])} | {int(f['n']):,} | {_number(f['median'])} |")
    lines += [
        "", "These are descriptive sample comparisons; publication year and work-type composition can differ across subfields. Category-level summaries, including complete-case denominators, are in the machine-readable citation and FWCI tables.",
        "", "FWCI by selected, **overlapping** research-category memberships (eligible articles/reviews only):", "",
        "| Classification layer | Category | FWCI-observed n | Median FWCI | Mean FWCI |", "|---|---|---:|---:|---:|",
    ]
    category_fwci = fwci.loc[fwci.group_by.astype(str).str.startswith("category:")]
    for row in category_fwci.itertuples(index=False):
        lines.append(f"| {row.group_by.removeprefix('category:')} | {row.group} | {int(row.n):,} | {_number(row.median)} | {_number(row.mean)} |")
    lines += [
        "", "FWCI already incorporates OpenAlex field/time normalization, but these are still overlapping, selected and sometimes small complete-case samples—not independently sampled categories. In particular, a small RAG group does not justify a strong comparative-impact claim. Publication-year and work-type citation/FWCI breakdowns are retained in the machine-readable tables.",
        f"At the common observation snapshot, publication age and observed citations have Spearman ρ={_number(age_test.statistic, 3)}, n={int(age_test.n):,}, p={age_test.p_value:.3g}. This is an exploratory conditional-sample association; greater exposure time is one plausible contributor, not a full explanation or causal estimate.",
        f"FWCI complete cases: {int(whole_fwci['n']):,}/{len(t['works']):,} works; median {_number(whole_fwci['median'])}, mean {_number(whole_fwci['mean'])}. Every sampled preprint lacks FWCI; article/review-only results cannot represent preprint impact. FWCI is normalized citation impact, not scientific quality. Figures: [citations](figures/phase4/rq2_citation_distribution.png), [cohorts](figures/phase4/rq2_citations_by_year.png), [FWCI](figures/phase4/rq2_fwci_distribution.png), [FWCI by subfield](figures/phase4/rq2_fwci_by_subfield.png), [age](figures/phase4/rq2_citation_age.png), [work type](figures/phase4/rq2_citations_by_type.png).",
        "", "## 5. RQ3 — Open Access and citation association", "",
        "| OA status | Sample n | Median citations | Mean citations | FWCI-available n |", "|---|---:|---:|---:|---:|",
    ]
    for row in oa.sort_values("oa_status").itertuples(index=False):
        lines.append(f"| {row.oa_status} | {row.n:,} | {_number(row.median_citations)} | {_number(row.mean_citations)} | {row.fwci_n:,} |")
    lines += [
        "", "Additional binary OA view (descriptive; statuses are retained separately above):", "",
        "| OA binary | Sample n | Median citations | Mean citations | Zero-citation % |", "|---|---:|---:|---:|---:|",
    ]
    for row in binary_oa.itertuples(index=False):
        lines.append(f"| {'open' if row.is_oa else 'closed'} | {row.n:,} | {_number(row.median_citations)} | {_number(row.mean_citations)} | {_number(row.zero_citation_percent)}% |")
    lines += [
        "", "The primary prespecified model is OLS for `ln(1 + citations)` with six OA statuses (closed reference), publication-year fixed effects (2020 reference), work type (article reference), primary subfield (1702 reference), and HC3 robust standard errors. Coefficients compare conditional mean log outcomes; `exp(β)−1` describes a relative change in **1 + citations**, not raw citation counts or a causal treatment effect.",
        "", "| OA contrast vs closed | β log1p | HC3 95% CI | p | BH q (five contrasts) |", "|---|---:|---:|---:|---:|",
    ]
    for row in primary.itertuples(index=False):
        lines.append(f"| {row.term.removeprefix('oa_')} | {row.estimate_log1p:+.3f} | [{row.ci95_low:+.3f}, {row.ci95_high:+.3f}] | {row.p_value:.3g} | {row.q_value_oa_family:.3g} |")
    lines += [
        "", "Sensitivity estimates selected before modeling (all coefficients on log1p citations):", "",
        "| Model | OA contrast | Complete cases | β | HC3 95% CI |", "|---|---|---:|---:|---:|",
    ]
    for model, term in (("unadjusted_binary", "oa_open"),
                        ("articles_reviews_status_year", "oa_green"),
                        ("articles_reviews_status_year", "oa_gold"),
                        ("adjusted_status_age", "oa_green"),
                        ("adjusted_status_age", "oa_gold")):
        row = models.loc[(models.model == model) & (models.term == term)].iloc[0]
        lines.append(f"| {model} | {term} | {int(row.n_complete_cases):,} | {row.estimate_log1p:+.3f} | [{row.ci95_low:+.3f}, {row.ci95_high:+.3f}] |")
    green_preprints = t["oa_composition"].loc[
        (t["oa_composition"].oa_status == "green") &
        (t["oa_composition"].group_by == "work_type") &
        (t["oa_composition"].group == "preprint"), "works"
    ].iloc[0]
    lines += [
        "", f"The unadjusted binary estimate differs in sign from some adjusted status-specific contrasts; OA groups are not compositionally comparable. In particular, **{int(green_preprints):,} of {int(oa.loc[oa.oa_status == 'green', 'n'].iloc[0]):,}** green-OA works are preprints. The models answer different exposure contrasts, so this is not a causal reversal. Within-year summaries and all model terms are in the CSV outputs.",
        f"The primary design matrix has rank {int(diagnostics.loc[diagnostics.model == 'adjusted_status_year', 'rank'].iloc[0])}/{int(diagnostics.loc[diagnostics.model == 'adjusted_status_year', 'parameters'].iloc[0])}; condition number {_number(diagnostics.loc[diagnostics.model == 'adjusted_status_year', 'condition_number'].iloc[0])}. Age-sensitivity complete cases: {int(age_model.complete_cases):,}. Observed citation-count variance/mean is {_number(diagnostics.loc[diagnostics.model == 'adjusted_status_year', 'count_variance_to_mean'].iloc[0])}; an unadjusted Poisson model would therefore be inappropriate. No unsupported exposure offset is applied. HC3 protects standard errors against heteroskedasticity but does not solve unmeasured confounding or model misspecification.",
        "", "Figures: [OA mix](figures/phase4/rq3_oa_distribution.png), [citation distributions](figures/phase4/rq3_citations_by_oa.png), [medians](figures/phase4/rq3_median_citations_oa.png), [adjusted estimates](figures/phase4/rq3_adjusted_coefficients.png), [FWCI](figures/phase4/rq3_fwci_by_oa.png).",
        "", "## 6. RQ4 — Collaboration networks", "",
        f"Mean authorship positions per work: {_number(collab.mean_authorships)} (median {_number(collab.median_authorships)}). Observed institution and country affiliations appear on {int(collab.institution_affiliation_available):,} and {int(collab.country_affiliation_available):,} of 12,000 works, respectively. Work-level observed institution counts: {int(collab.zero_observed_institutions):,} zero, {int(collab.single_observed_institution):,} single, {int(collab.multi_observed_institution):,} multi. Observed country counts: {int(collab.zero_observed_countries):,} zero, {int(collab.single_observed_country):,} single, {int(collab.multi_observed_country):,} multi. These observed-count bins do not replace the stricter tri-state collaboration flags.",
        f"International co-affiliation: {int(collab.international_true):,} true, {int(collab.international_false):,} known false, and {int(collab.international_unknown):,} unknown (all out of 12,000). Among {int(collab.international_known_denominator):,} known statuses, {_number(collab.international_rate_known_percent)}% are international. Unknown is never recoded as domestic.",
        "", "| Network | Nodes | Edges | Components | Density |", "|---|---:|---:|---:|---:|",
    ]
    for row in network.itertuples(index=False):
        lines.append(f"| {row.network} | {row.nodes:,} | {row.edges:,} | {row.connected_components:,} | {row.density:.5f} |")
    lines += ["", "Top observed country pairs (unique supporting sampled works): " + "; ".join(
        f"{r.country_a}–{r.country_b} ({int(r.weight_works):,})" for r in country.itertuples(index=False)
    ) + ".", "Top observed institution pairs (OpenAlex IDs; unique supporting sampled works): " + "; ".join(
        f"{r.institution_a.rsplit('/', 1)[-1]}–{r.institution_b.rsplit('/', 1)[-1]} ({int(r.weight_works):,})" for r in institution.itertuples(index=False)
    ) + "."]
    lines += [
        "", "Each unordered country/institution pair contributes at most once per work. Complete-country-coverage edge weights are stored alongside all-observed weights as a sensitivity check; country affiliation means institutional geography, not nationality. Graph centrality is sample-specific co-affiliation, not global influence or direct person-to-person collaboration. Figures: [counts](figures/phase4/rq4_author_institution_counts.png), [tri-state status](figures/phase4/rq4_international_status.png), [country graph](figures/phase4/rq4_country_network.png), [top pairs](figures/phase4/rq4_top_country_pairs.png), [institution graph](figures/phase4/rq4_institution_network.png), [coverage](figures/phase4/rq4_affiliation_coverage.png).",
        "", "## 7. Cross-cutting data quality", "",
        "`missingness_analysis.csv` records overall, year and work-type denominators. `analytical_subset_audit.csv` contrasts included and excluded works by year, type and subfield for FWCI, collaboration status, text and OA coverage. FWCI completeness differs sharply by type: every preprint is excluded from FWCI analyses. Abstract gaps constrain text-rule recall, and missing affiliation data can bias observed network structure. `oa_model_diagnostics.csv` reports retained and excluded unique works for each model; no many-to-many join is used in work-level regression.",
        "", "## 8. Statistical validity and limitations", "",
        "This is a database/classifier snapshot, subject to coverage and taxonomy changes. Raw citations depend strongly on age and are not scientific quality. FWCI is unavailable for preprints and can have its own coverage bias. Affiliations and abstracts are missing nonrandomly in ways this analysis cannot rule out. The sampling mechanism does not establish known inclusion probabilities, so conventional design-based population confidence intervals are not claimed. OA, topic and collaboration associations are descriptive or conditional on recorded covariates, never causal. Five primary OA-status contrasts receive Benjamini–Hochberg q-values within their declared family; other p-values are exploratory.",
        "", "## 9. Conclusions", "",
        "RQ1: the approved OpenAlex AI/CV primary-subfield corpus grew in observed publication volume, but this does not quantify all global AI research. Selected native-topic classifications show trajectories within that corpus; emerging text-rule matches are only sample-based exploratory signals.",
        "RQ2: observed citations are highly skewed and age-associated; FWCI comparisons are limited to eligible articles/reviews. No citation metric here establishes paper quality.",
        "RQ3: OA status is associated with observed citation differences under the specified models, with estimates and uncertainty above; no causal OA advantage or penalty is inferred.",
        "RQ4: the sampled affiliation graph reveals repeated country and institution co-affiliation pairs, but missing affiliations and sample scope prohibit a global collaboration ranking.",
        "", "## 10. Phase 5 readiness", "",
        "The verified work grain, reconstructed text, category provenance, and deterministic output manifests support a later **leakage-aware** TF-IDF baseline or clustering experiment. Split by Work ID before vocabulary fitting; keep native-topic labels distinct from text-rule labels and quantify abstract missingness. No ML model or dashboard was built in Phase 4.", "",
    ]
    return "\n".join(lines)
