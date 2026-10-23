# Phase 4 presentation brief — AI research trends and scientific impact

Eight slide-ready sections, based on the verified Phase 4 run
`phase4_stratified_20261019T155909Z_v3`. Figures are available in the
repository; numerical source tables remain in the local, Git-ignored run.
Population and sampled-work results must stay separate.

## Slide 1 — What did we study?

**Key message:** Two analytical layers answer different questions.

- Population: 937,493 non-retracted OpenAlex works dated 2020–2025, limited to primary AI/CV subfields 1702/1707 and article/review/preprint types.
- Detailed dataset: 12,000 distinct works sampled across six publication years for citations, OA and co-affiliation analyses.
- The corpus is an AI/CV primary-subfield definition, not all global AI research.

**Figure:** [RQ1 population counts](../reports/figures/phase4/rq1_population_counts.png) — complete OpenAlex aggregates.

**Speaker notes:** The population supports publication-volume trends. The detailed sample supports exploratory comparisons, but OpenAlex server-side sampling has no verified known inclusion probabilities; nominal weights are not design-based guarantees.

## Slide 2 — RQ1: publication and topic trends

**Key message:** Observed publication volume rose substantially, within this defined corpus.

- Annual population count: 125,506 (2020) to 232,476 (2025), an 85.23% total increase.
- Five-interval compound annual growth rate: 13.12%; 2020 has no 2019 comparison in this study.
- Selected native-topic memberships overlap; custom LLM/RAG text matches are sample-only exploratory signals.

**Figure:** [RQ1 population counts](../reports/figures/phase4/rq1_population_counts.png) — complete population, not sample counts.

**Speaker notes:** Database coverage and topic assignment can change. Do not sum overlapping OpenAlex topic counts or call this the growth rate of all worldwide AI research.

## Slide 3 — RQ2: citation impact

**Key message:** Citation counts are highly skewed and exposure-time dependent.

- Across 12,000 sampled works, median observed citations = 2; mean = 11.24.
- Zero-citation share = 37.75%; the observed maximum of 4,199 remains in the analysis.
- FWCI is observed for 9,322 articles/reviews, but for none of the 2,678 sampled preprints.

**Figure:** [RQ2 citation distribution](../reports/figures/phase4/rq2_citation_distribution.png) — detailed sample.

**Speaker notes:** The display uses `ln(1 + citations)` for readability and does not discard outliers. Citations and FWCI are indicators of recorded citation impact, not measures of scientific quality. FWCI comparisons exclude preprints.

## Slide 4 — RQ3: descriptive Open Access comparison

**Key message:** A binary OA comparison conceals very different status groups.

- Closed: 3,268 sampled works, median 3 citations; all OA statuses combined: 8,732 works, median 1.
- The unadjusted binary OLS model (`unadjusted_binary`) gives open versus closed β = −0.330 for `ln(1 + citations)`.
- Green OA contains 3,559 works, including 2,506 preprints; OA status groups differ in year/type composition.

**Figure:** [RQ3 OA-status composition](../reports/figures/phase4/rq3_oa_distribution.png) — descriptive sample counts.

**Speaker notes:** The raw binary comparison suggests a lower observed transformed citation outcome for the combined OA group. It groups unlike OA statuses and does not establish a causal OA penalty. The contrast is different from the adjusted six-status model on the next slide.

## Slide 5 — RQ3: adjusted OA associations

**Key message:** Some status-specific conditional associations are positive; none is a causal effect.

- Primary six-status OLS model (`adjusted_status_year`): outcome `ln(1 + citations)`; closed is the reference.
- Gold versus closed: β = +0.463, HC3 95% CI [+0.396, +0.531].
- Green versus closed: β = +0.178, HC3 95% CI [+0.087, +0.269].
- Adjusted for publication-year fixed effects, work type and primary AI/CV subfield; 12,000 model complete cases.

**Figure:** [RQ3 adjusted coefficients](../reports/figures/phase4/rq3_adjusted_coefficients.png) — conditional sample-model estimates, not raw citation means.

**Speaker notes:** Gold is associated with higher conditional mean log(1 + citations) than closed access in this model. Exponentiating β = 0.463 yields roughly 58.9% higher conditional geometric mean of **1 + citations**, not 58.9% more raw citations per paper. Green follows the same scale interpretation. The unadjusted binary and adjusted status-specific coefficients are different contrasts, not a causal sign reversal. All 2,678 preprints lack FWCI; unmeasured confounding, selection and model misspecification remain possible.

## Slide 6 — RQ4: collaboration patterns

**Key message:** Co-affiliation patterns can be described, but missing affiliations limit network claims.

- International co-affiliation status is true for 1,979, known false for 5,991 and unknown for 4,030 sampled works.
- Among 7,970 works with known status, 24.83% show international co-affiliation.
- The most frequent observed country pair is CN–US, supported by 208 unique sampled works.

**Figure:** [RQ4 sampled country network](../reports/figures/phase4/rq4_country_network.png) — co-affiliation among observed sample records.

**Speaker notes:** Country reflects affiliation geography, not nationality. Missing country data are unknown, never domestic. Edges count supporting works, not direct interpersonal collaborations; this is not a global AI network.

## Slide 7 — Limits that affect interpretation

**Key message:** Coverage, sampling and missingness bound all four answers.

- OpenAlex taxonomy and database coverage may change; the defined AI/CV corpus excludes research outside its primary-subfield rule.
- The detailed sample has unverified server-side inclusion probabilities; it cannot establish population prevalence or design-based intervals.
- Missing abstracts weaken custom text-rule recall; missing affiliations affect co-affiliation graphs; all preprints lack FWCI.
- Citation age, unmeasured confounding and observational design rule out causal OA claims.

**Figure:** [RQ4 affiliation coverage](../reports/figures/phase4/rq4_affiliation_coverage.png) — sample coverage diagnostic.

**Speaker notes:** State denominators before comparing groups. A statistically precise conditional association need not be practically important or causal.

## Slide 8 — Main findings and hand-off

**Key message:** Phase 4 established descriptive evidence and a reproducible base for later, leakage-aware ML.

- Population publication volume rose within the approved AI/CV corpus; native-topic and custom text-rule layers answer different questions.
- Sample citations are skewed; OA status associations change with group definition and adjustment, without implying causal effects.
- Sampled co-affiliation links are informative but incomplete; preserve unknowns and do not rank the global research network.
- Phase 5 could test TF-IDF baselines using Work-ID splits, with vocabulary fitting only on training data.

**Figure:** [RQ1 native-topic trajectories](../reports/figures/phase4/rq1_native_topic_trends.png) — complete but overlapping population topic series.

**Speaker notes:** The presentation closes at Phase 4. No Phase 5 model has been trained here. Direct examiners to the [academic report](../reports/PHASE4_ANALYSIS_REPORT.md) for methods, uncertainty and all 22 linked figures.
