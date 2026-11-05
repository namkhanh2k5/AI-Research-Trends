# Research methodology and interpretation

The [collection strategy](DATA_COLLECTION_STRATEGY.md) fixes the exact API
corpus, retraction policy, aggregation logic, proportional year strata and
provenance. The [data dictionary](DATA_DICTIONARY.md) fixes table grains,
keys, missing values and feature definitions. The Phase 1 feasibility numbers
are preserved in [the original feasibility report](../reports/research/phase1/data_feasibility.md)
and [pre-Phase-2 gate](../reports/research/phase1/PRE_PHASE2_REVIEW.md). They are historical
snapshots, not the final Phase 2 population counts.

## Three evidence populations

1. Full-corpus OpenAlex aggregations answer publication trends only for the
   defined primary-subfield frame and retrieval time. Native topic filters
   overlap; custom title/abstract LLM, Multimodal AI and RAG rules are separate
   text-derived classifications and not directly equivalent population series.
2. The original 12,000-work detailed sample supports work-level citation,
   OA, collaboration and reference analyses. Its year-stratified weights are
   nominal because server-side sampling probabilities were not established.
3. Targeted 2020–2023 topic-ML expansion augments historical model training.
   Its selection mechanism precludes using it for RQ1–RQ4 prevalence.

## Analysis and decision boundaries

RQ1 uses population year counts; RQ2 reports raw citation distributions with
publication-age and field context, plus FWCI where observed. All 2,678 original
sample preprints lack FWCI, so complete-case FWCI comparisons exclude them.
RQ3 models `log(1 + cited_by_count)` with publication year, work type and
primary subfield adjustments; the six OA statuses must not be collapsed when
interpreting that model. OA coefficients are conditional associations subject
to unmeasured confounding and selection. RQ4 deduplicates institution/country
memberships within each work and describes **sampled co-affiliation** networks,
not worldwide collaboration or author nationality. Source methods, model
specification and uncertainty are in the protected
[Phase 4 statistical plan](PHASE4_STATISTICAL_ANALYSIS_PLAN.md) and
[completed report](../reports/research/phase4/PHASE4_ANALYSIS_REPORT.md).

RQ5's original candidate gate used eligible 2020–2022 citing works for 2023
queries and a frequency ≥2 pool; a bounded follow-up also used all historical
edge-bearing works and thresholds 1/2/3. The former plan and measured follow-up
are documented in [the final NO-GO decision](../reports/research/phase5/PHASE5_FINAL_DECISION.md)
and [coverage reassessment](../reports/research/phase5/PHASE5_COVERAGE_REASSESSMENT.md). ID
overlap is not retrieval relevance, and unknown candidate dates prevent a
complete temporally valid coverage claim.

RQ6 uses OpenAlex automated primary-topic silver labels and a provisional
14-topic catalogue. The [Phase 6 report](../reports/phase6/PHASE6_REPORT.md)
separates the five-class pilot, fourteen-class feasibility evaluation and
final integrated ML development. Different catalogues and denominators must
not share one performance claim. Two genuine independent human reviews are
still needed for semantic validation; the historical 2025 holdout is no longer
independently sealed after publication.

Further limitations: OpenAlex metadata and taxonomy can change; missing
abstracts reduce lexical coverage; missing institutions/countries make network
edges unknown; citation age and venue selection affect impact comparisons;
topic scores are not quality or calibrated confidence; paper-discovery cosine
scores are not verified relevance or novelty. No observational result in this
project establishes a causal effect.
