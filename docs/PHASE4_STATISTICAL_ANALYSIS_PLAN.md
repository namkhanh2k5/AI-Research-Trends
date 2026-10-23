# Phase 4 statistical analysis plan (specified before executing final models)

Snapshot: the verified Phase 3 run `stratified_20261019T155909Z`, observed at
2026-10-19 16:03:40 UTC. No new OpenAlex retrieval. This is a focused AI/CV
primary-subfield corpus, not all global AI research. The detailed sample was
drawn by a server-side mechanism whose inclusion probabilities are unverified;
the published `N_h/n_h` weights are nominal only. We therefore use exact
population aggregates for publication-volume estimands and treat sample-based
inference as conditional on the observed records and model assumptions.

| RQ | Analytical set and outcome | Primary estimand/method | Restrictions and sensitivity |
|---|---|---|---|
| RQ1 | Complete, non-retracted population year and supported native-topic aggregate series; annual work count | Exact 2020–2025 counts, YoY, index and five-interval CAGR | Overlapping native topics are never summed. Custom LLM/Multimodal/RAG matching is separately described with sample-year denominators and text coverage, never extrapolated to population counts. All-work series are sensitivity context. |
| RQ2 | All sampled works: observed citations; article/review complete cases: FWCI | Robust citation distribution, Spearman association of observation age and citations; descriptive FWCI summaries by year/type/subfield | Preserve zeroes/outliers. FWCI is absent for every preprint and never imputed. Spearman p-value is exploratory conditional-sample evidence, not a population probability-sampling claim. |
| RQ3 | OA-observed sample, outcome `log1p(cited_by_count)` | Primary: OLS with six OA statuses (closed reference), publication-year fixed effects (2020 reference), work type (article reference), primary subfield (1702 reference), HC3 robust covariance and 95% normal-approximation intervals | Descriptive binary OA and unadjusted binary OLS; article/review-only adjusted sensitivity; within-year OA vs closed descriptive contrasts. Complete-case counts and design-matrix rank/condition diagnostics reported. No causal claim. No exposure offset or significance-driven model switching. |
| RQ4 | Sample works with observed institution/country affiliations; work-level collaboration flags | Tri-state rates using all 12,000 as denominator and known-status denominator separately; one co-affiliation pair contribution per work | Compare all observed country edges with edges from works whose country affiliation coverage is complete. Missing country does not mean domestic. Networks are sampled co-affiliation graphs, not global collaboration maps. |

Statistical policy: no blanket testing of every category or pair. The primary
OA coefficient family is the five non-closed status contrasts within one
predefined model; Benjamini–Hochberg adjusted q-values are reported alongside
unadjusted p-values. Confidence intervals describe conditional model uncertainty
only, not guaranteed design-based population uncertainty. Report absolute
counts, denominator and missing/excluded count at each restriction. The chosen
log-citation model is an interpretable association analysis, not a claim that
the transformed outcome is Gaussian. Diagnostics include residual magnitude,
matrix rank/condition, citation skew and count variance-to-mean ratio.

No TF-IDF fitting, train/test splitting, ML training, causal estimation or
dashboard development is in Phase 4.
