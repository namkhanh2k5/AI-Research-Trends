# Research Questions and Operational Definitions

## RQ1 — topic evolution

**Question:** How have AI research topics evolved during 2020–2025?

Population evidence will use complete year counts from declared OpenAlex filters.
The fixed frame uses `primary_topic.subfield.id:1702|1707`. OpenAlex-native lenses
use overlapping `topics.id` memberships. Custom LLM, Multimodal AI, and RAG labels
use separately reported title/abstract rules and are not directly equivalent to
native counts. Counts overlap and cannot be summed. Detailed-sample estimates will
report design weights and uncertainty. Primary-topic composition is a separate,
mutually exclusive view.

Measures include annual count, year-over-year change, share of the defined frame,
and topic transition/composition. A database/classifier change may cause an
apparent trend and must be discussed.

## RQ2 — citation impact

**Question:** Which AI research areas show stronger scientific citation impact
when publication year and field are considered?

Primary outcomes are OpenAlex `fwci` and, when available and suitable, citation
percentile indicators. Raw `cited_by_count` and citations-per-year are descriptive
sensitivity measures. Comparisons will stratify or adjust for publication year,
primary subfield, and work type; uncertainty and missing FWCI are reported.

“Impact” means observed citation impact in OpenAlex. It does not mean validity,
novelty, societal benefit, or scientific quality.

## RQ3 — Open Access and impact

**Question:** How is OA status associated with scientific impact?

Exposure views are binary `open_access.is_oa` and status categories (diamond,
gold, green, hybrid, bronze, closed). Compare distributions and fit an adjusted
model with year, work type, primary subfield/category, and available venue/country
covariates. Report effect sizes and confidence intervals, not only p-values.

This is observational. Author resources, venue selection, discipline, funder
mandates, and self-archiving can confound the association; no causal OA advantage
will be claimed.

## RQ4 — collaboration

**Question:** How do institutions and countries collaborate in AI research?

Build one row per `(work_id, institution_id)` and `(work_id, country_code)` after
deduplication within a work. Create unordered pairs once per work. Full counting
gives each observed edge one contribution per paper; fractional sensitivity gives
each of `k(k-1)/2` pairs weight `1 / choose(k, 2)`. Self-loops are excluded.

Report works lacking affiliations/country codes. Country values reflect author
affiliations, not nationality. Network prominence is not research quality.

## Confirmatory versus exploratory

The four questions and main operational definitions above are pre-specified.
Fine-grained topic discovery, clustering, alternate text rules, and 2026 YTD are
exploratory and must be labeled as such.
