# Phase 3 Data Quality Report

## A. Processing overview

- Status: **complete**; processed at 2026-10-23T07:45:51Z.
- Source collection run: `stratified_20261019T155909Z`; observation time: 2026-10-19T16:03:40Z.
- Processing Git HEAD: `7b6dbb8c603f0a5f23277cf4774d70c2b418b406`; source-code SHA-256: `9395b3943f65bc0b224872e8ecebe5e595f480f503c34dab307ff5667efdb0b3`.
- Output directory: `data/processed/openalex_stratified/stratified_20261019T155909Z`; processing manifest: `data/processed/openalex_stratified/stratified_20261019T155909Z/manifest.json`.
- Original raw and interim JSONL files were read only; no OpenAlex API request was made.
- Transformations: strict corpus and ID validation; Unicode-preserving whitespace normalization; DOI normalization; abstract reconstruction; relationship deduplication; nullable bibliometric, text and collaboration features; sorted typed Parquet export.

### Verified inputs

| Artifact | Path | SHA-256 |
|---|---|---|
| source_jsonl | `/home/khanh/Projects/AI-Research-Trends/data/interim/openalex_stratified/stratified_20261019T155909Z/works.jsonl` | `b8734cd3da2cba8c2c9ff8a9742d46d62585e55604f18630274f6bb8fbc178af` |
| source_manifest | `/home/khanh/Projects/AI-Research-Trends/data/raw/openalex_stratified/stratified_20261019T155909Z/manifest.json` | `c6fc71e6eee2fc3131df3cdfe2f300dc719ed3b6196be1be852a45519a08aa6e` |
| plan | `/home/khanh/Projects/AI-Research-Trends/data/metadata/phase2_sampling_plan.json` | `f18ecdc621e5e697ae0c3cbe277d5729f40592299f6c2af95cabeab96e9a7593` |
| population | `/home/khanh/Projects/AI-Research-Trends/data/metadata/population_counts_pre_phase2.json` | `e84015be2e14756301130dc982b437097449986ae45c9ece4ed8007bb87e36d3` |
| phase2_profile | `/home/khanh/Projects/AI-Research-Trends/data/metadata/phase2_profile.json` | `64c67f570000953b3486653ed18cb4c02a035dc94914b690871d69dd8b23f1be` |
| config | `/home/khanh/Projects/AI-Research-Trends/config/topics.yaml` | `5a97ea16ced3746db9bfd4bf2316af8482be4f7c0efefe78cd6705e5ee32969a` |

### Sampling allocation (detailed sample, not population estimates)

| Year | Population N | Planned n | Actual n | Nominal N/n |
|---:|---:|---:|---:|---:|
| 2020 | 125,506 | 1,607 | 1,607 | 78.099564 |
| 2021 | 128,893 | 1,650 | 1,650 | 78.116970 |
| 2022 | 126,189 | 1,615 | 1,615 | 78.135604 |
| 2023 | 145,735 | 1,865 | 1,865 | 78.142091 |
| 2024 | 178,694 | 2,287 | 2,287 | 78.134674 |
| 2025 | 232,476 | 2,976 | 2,976 | 78.116935 |

## B. Table inventory

| Parquet table | Rows | Unique keys | Columns | Bytes | SHA-256 |
|---|---:|---:|---:|---:|---|
| `works` | 12,000 | 12,000 | 49 | 5,762,302 | `9318c456d916b8c9a35b0a3c86a829a92347083357693593e743abb0253264d4` |
| `work_topics` | 36,000 | 36,000 | 8 | 342,377 | `e65356b899f3c9dec4d9d47ec9dae54557b23dc1709a1b3ea1d4c5f746acf6d5` |
| `authorships` | 46,249 | 46,249 | 6 | 921,766 | `ba8bee6e7da8deb7a4063acc66bb78c8cab9551472a12965071874c2cb298782` |
| `work_institutions` | 18,717 | 18,717 | 6 | 264,917 | `d4fd9e1375b5d6369542a581b83aa9659497ee949bea7de146c2d74c872a1f4e` |
| `work_countries` | 11,786 | 11,786 | 3 | 74,681 | `6e4c8b1bf27bf260a98468d6e171a0ef4685057b26a43f382e2d532c4e449ed4` |
| `references` | 289,110 | 289,110 | 3 | 1,617,252 | `1c0f306225e6f7fd673b2972744c702d184b2e8f5c88e09569eea24d831d599d` |
| `category_membership` | 4,790 | 4,790 | 5 | 33,595 | `438bf85a8858f135099e198ea552e93da59008f5677cc828694f9ee48ef50ae1` |
| `population_year_counts` | 72 | 72 | 6 | 3,675 | `ae723a94efa06981097fa059a0592b70f8807555678e8bff58d8b088593534ba` |

## C. Missingness audit

All rates use the 12,000-work detailed-sample denominator; these are not population prevalence estimates.

| Field/coverage | Missing | Percent | Phase 2 missing | Difference |
|---|---:|---:|---:|---:|
| title | 2 | 0.02% | 2 | +0 |
| doi | 1,019 | 8.49% | 1,019 | +0 |
| abstract | 2,558 | 21.32% | 2,558 | +0 |
| fwci | 2,678 | 22.32% | 2,678 | +0 |
| institution | 2,902 | 24.18% | 2,902 | +0 |
| country | 2,949 | 24.57% | 2,949 | +0 |
| language | 586 | 4.88% | 586 | +0 |
| open_access | 0 | 0.00% | 0 | +0 |

### By publication year

| Group | Works | Missing title | DOI | Abstract | FWCI | Institution | Country | Language | OA |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2020 | 1,607 | 0 | 390 | 478 | 278 | 547 | 549 | 5 | 0 |
| 2021 | 1,650 | 0 | 262 | 396 | 355 | 425 | 429 | 15 | 0 |
| 2022 | 1,615 | 1 | 44 | 328 | 323 | 277 | 281 | 16 | 0 |
| 2023 | 1,865 | 1 | 61 | 344 | 403 | 294 | 299 | 23 | 0 |
| 2024 | 2,287 | 0 | 97 | 412 | 533 | 419 | 429 | 29 | 0 |
| 2025 | 2,976 | 0 | 165 | 600 | 786 | 940 | 962 | 498 | 0 |

### By work type

| Group | Works | Missing title | DOI | Abstract | FWCI | Institution | Country | Language | OA |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| article | 9,265 | 2 | 845 | 2,199 | 0 | 1,906 | 1,946 | 338 | 0 |
| preprint | 2,678 | 0 | 170 | 355 | 2,678 | 985 | 992 | 244 | 0 |
| review | 57 | 0 | 4 | 4 | 0 | 11 | 11 | 4 | 0 |

FWCI missing by type: article: 0/9,265, preprint: 2,678/2,678, review: 0/57. All sampled preprints lack FWCI; cross-type FWCI comparisons must exclude or separately treat them.
Affiliation uncertainty: international collaboration is unknown for 4,030 works and institutional collaboration for 3,573; unknown is not domestic/single-institution.
Reference-list source status: empty=4,471, present=7,529. An absent list is not a confirmed zero-reference work.

## D. Integrity and classification audit

- Validation: **29/29 PASS**. Checks cover corpus/date/type/retraction, canonical and unique IDs, six plan strata and nominal weights, composite keys, bridge-table foreign keys, OA/FWCI/citation consistency, population-series separation and file checksums.
- Processing issues: 0; by field: `{}`. See `quality.json` for row-level quarantine records.
- No unexpected source-schema inconsistencies were observed in this run; strict date, type, ID, numeric and relationship checks found no records to exclude or repair. Any future failure leaves an incomplete-run diagnostic beside the requested output directory.
- OpenAlex-native and custom text-derived memberships are independent overlapping layers. Unmatched text is not a validated negative, especially where abstracts are unavailable.

| Layer | Category | Matched works |
|---|---|---:|
| custom_emerging | large_language_models | 526 |
| custom_emerging | multimodal_ai | 165 |
| custom_emerging | retrieval_augmented_generation | 39 |
| openalex_native | computer_vision | 1,838 |
| openalex_native | explainable_ai | 246 |
| openalex_native | multimodal_machine_learning_applications | 429 |
| openalex_native | natural_language_processing | 1,165 |
| openalex_native | reinforcement_learning | 382 |

- Independent rerun: `data/processed/openalex_stratified/stratified_20261019T155909Z_rerun`; all 8 Parquet SHA-256 checksums and the quality JSON checksum match exactly. Processing timestamps and code hashes in manifests are separate metadata and need not match.

## E. Engineered features and null policy

- `publication_age_years = (collection completion timestamp - publication_date).days / 365.2425`; the same observation timestamp is used for every work, and future-dated records fail validation.
- `log1p_citations = ln(1 + cited_by_count)`; `zero_citation_flag` is true only for an observed zero. Outliers are retained. `has_fwci` reflects presence; missing FWCI remains null, never zero-imputed.
- `has_oa_metadata` requires both OA fields. Binary OA and status must agree; missing OA is never assumed closed.
- Authorship count counts positions. Identified author, institution and country counts use unique identifiers/codes. Collaboration flags are true only with at least two observed entities; false requires complete relevant affiliation coverage; otherwise null.
- Text lengths use normalized but case-preserving source text. Native/custom category counts and LLM/Multimodal/RAG flags describe matching rules, not ground-truth labels.
- Future ML must split by unique Work ID before fitting any vocabulary or statistical transform; duplicate relationships must not leak across train/test partitions.

## F. Research limitations

- The `N_h/n_h` year-stratum weights are **nominal**: OpenAlex server-side sample uniformity and snapshot stability are unverified. Do not treat weighted category estimates as design-unbiased population totals.
- Population publication trends must come from `population_year_counts`, not the detailed sample. Native topic series may overlap; custom LLM/RAG/Multimodal matches have no population aggregate here.
- Missing abstracts limit lexical recall; OpenAlex taxonomy may misclassify or miss topics. Missing affiliations constrain collaboration analysis and may be nonrandom.
- Citations accumulate with publication age and are not scientific quality. FWCI excludes every sampled preprint. Open Access–impact associations are observational, not causal.
- All findings describe the approved AI/CV primary-subfield OpenAlex corpus, not all global AI research.

## G. Phase 4 readiness

- Publication trends: **ready** using validated population series; do not infer prevalence from sample category proportions.
- Citation impact: **ready with restrictions**: age-aware and field/type-aware comparisons; FWCI only where observed and preprints handled separately.
- OA association: **ready for descriptive/adjusted observational analysis**, with no causal interpretation.
- Collaboration: **ready for affiliation-observed subset/sensitivity analyses**; retain unknown states and report coverage.
- Topic comparisons: **ready as method-specific, overlapping descriptive analyses**; do not equate native and custom category counts.

## H. Execution checks

- Offline `pytest -q -ra`: **87 passed, 1 skipped**. The skipped test is the opt-in live OpenAlex integration probe; Phase 3 made no API calls.
- `pip check`: no broken requirements.
- Installed CLI entry points for preprocessing, validation and report generation returned `--help` successfully. The environment's normal editable-install command could not fetch build dependencies because PyPI DNS/network access was unavailable; an offline `--no-build-isolation --no-deps` editable install using the system-provided setuptools succeeded.
- The inspection notebook executed successfully with `nbconvert` after allowing local Jupyter kernel sockets. No Phase 4 EDA or ML was run.
- Processed data and rerun outputs remain Git-ignored; only source, tests, notebook and this report belong in Git.
