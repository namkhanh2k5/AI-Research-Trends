# Finalization Phase 1 — targeted training-data expansion

## Executive decision

**The bounded acquisition and integrity gate passed.** The original 12,000-work analytical sample was preserved; a separate 2020–2023 training-only OpenAlex run acquired **2,515 raw records / 2,515 unique Work IDs**. After text and identity screening, **1,947 new records** (77.4%) are provisionally ML-training-eligible: **1,638** with a selected primary topic and **309** outside the fourteen-topic catalogue. Selected-topic usable support rose from **1,746 to 3,384**; 11 of 14 topics now reach the pragmatic 225-example target. The remaining gaps are **12** in total, not a reason for another large crawl. This is readiness for a **controlled integration and human-review phase**, not approval to fit or publish a classifier yet.

## Source integrity and scientific scope

The original Phase 2 acquisition is still valid: read-only verification returned 123/123 pages and 12,000 unique IDs with identical original raw/interim JSONL SHA-256 `b8734cd3da2cba8c2c9ff8a9742d46d62585e55604f18630274f6bb8fbc178af`. The Phase 3 `works.parquet` and `work_topics.parquet` source hashes remain `9318c456d916b8c9a35b0a3c86a829a92347083357693593e743abb0253264d4` and `e65356b899f3c9dec4d9d47ec9dae54557b23dc1709a1b3ea1d4c5f746acf6d5`. No Phase 1–4 dataset or analysis output was overwritten. The full population aggregates and 12,000-work probability-design sample remain separate from this **targeted, nonrepresentative ML expansion**. The latter cannot estimate topic popularity, publication growth, OA effects or impact for the defined AI/CV population.

All acquired works were checked against exact 2020–2023 publication dates, `article|review|preprint`, primary subfield `1702|1707`, `is_retracted:false`, canonical Work ID, assigned year, and requested primary topic when specified. The 2024 validation and 2025 locked-test work labels were not used to plan or query the expansion. Held-out **identities** (ID, DOI, normalized title) were checked solely to prevent cross-split duplicates; their labels were not read. The seed is reproducible, but OpenAlex server-side sampling is not asserted to provide known inclusion probabilities or a stable multi-page snapshot.

## Planning and actual API execution

The [gap audit](FINALIZATION_P1_DATA_GAP_AUDIT.md) found 1,746 original usable training records across 14 topics, 1,548 below a 225/topic target. Verified source-capacity checks consumed **21 list credits**; the planned 2,015 selected-topic raw plus 500 outside-source raw records fit a **3,000-record** and **180-request/credit** cap. The 36-record separate smoke run passed 12/12 raw pages and 36 unique IDs before production execution.

The production run `ml_expansion_20261101T052506Z` ran from **2026-11-01 05:25:06 UTC to 05:26:56 UTC** (110 seconds). It completed **80/80 pages**, **80 successful list requests**, **80 observed API credits**, and **no recorded request failures**; the last observed daily credit balance was **9,885**. The existing API client may retry internally; retry counts are not exposed, so do not interpret “80 requests” as a measured count of HTTP attempts. The collected pages occupied approximately **83 MiB** in the raw run directory; raw JSONL was **41,300,576 bytes**, interim JSONL **42,970,282 bytes**. The primary run manifest is local at `data/raw/openalex_ml_expansion/ml_expansion_20261101T052506Z/manifest.json`, with raw JSONL beside it and enriched, provenance-wrapped interim JSONL at `data/interim/openalex_ml_expansion/ml_expansion_20261101T052506Z/records.jsonl`.

Read-only verification checked all page hashes, page counts, exact corpus membership, ordered Work IDs, raw JSONL SHA-256 `cc946d6970cbfbafcfe58b236699f2f27772545865f68b5b693872f87ef87126`, and interim JSONL SHA-256 `cd60da68c9d53ffe181e2f4ca847bbad21baf1952e840aa8537e0b1ae67533a3`. Result: **PASS**, 2,515 unique IDs and zero duplicate IDs across all production pages. The private quality manifest and record-level exclusion audit are under `data/analysis/finalization_p1_quality_20261101_v2/`; [public aggregate checksums](finalization_p1/reproducibility_manifest.json) cover only small summaries.

| Publication year | Raw new records | Eligible new | Eligible selected-topic | Eligible outside-topic |
|---|---:|---:|---:|---:|
| 2020 | 558 | 410 | 346 | 64 |
| 2021 | 608 | 465 | 401 | 64 |
| 2022 | 620 | 488 | 407 | 81 |
| 2023 | 729 | 584 | 484 | 100 |
| **Total** | **2,515** | **1,947** | **1,638** | **309** |

The broad 275-work AI/CV source contained **97** records whose actual primary topic was in the selected catalogue; 72 of those were eligible. Conversely, all 2,015 selected-source records had the intended primary topic. The 500 outside-source *queries* therefore yielded **403 outside-labelled raw** records, not 500 guaranteed negatives. Exact source-group yields are [published separately](finalization_p1/source_group_yield.csv).

The smoke set included one Work ID already in the original 12,000 and 11 records without an abstract inverted index. These checks were quantified after the production run rather than serving as a pre-production overlap stop criterion; they illustrate why raw retrieval cannot be equated with newly usable training rows.

## Quality, duplicates and effective support

Original raw pages remain unchanged even when a record is excluded from ML. The 2,515 unique acquisitions contain **507 missing abstracts**, **35 abstracts shorter than 30 words**, **one missing title**, **253 missing DOIs**, and **zero missing language values**. Among newly acquired records, 1,972 had title plus an abstract of at least 30 words before identity screening. The local screening then excluded **33** IDs already in the 12,000-work sample and **two** DOI/title-linked versions of original training papers; **zero** new-new DOI or normalized-title duplicate rows and **zero** held-out DOI/title identity collisions were observed. The final *mutually exclusive* exclusion counts were: 499 missing abstracts, 33 short abstracts, 33 original-ID overlaps, two original-version overlaps, one missing title, and 1,947 eligible. The differing raw text-quality and final-exclusion counts reflect exclusion precedence. This title/DOI rule does not detect every semantically duplicated preprint or reissued article.

Primary-topic IDs matched their requested specific-topic strata. Compared with the verified topic metadata snapshot, there were **zero name mismatches among 2,367 assessable records**; **148** broad-source records had topics outside that metadata table and were not assessed for name equality. Top-three topic IDs and snapshot provenance are retained locally. No independent human topic verification is claimed.

| Topic | Original usable | New usable | Combined | Gap to 225 |
|---|---:|---:|---:|---:|
| T10036 | 369 | 9 | 378 | 0 |
| T10664 | 190 | 35 | 225 | 0 |
| T10028 | 149 | 84 | 233 | 0 |
| T10052 | 127 | 104 | 231 | 0 |
| T10462 | 120 | 118 | 238 | 0 |
| T10775 | 104 | 123 | 227 | 0 |
| T10181 | 94 | 129 | 223 | 2 |
| T11307 | 84 | 150 | 234 | 0 |
| T11689 | 73 | 177 | 250 | 0 |
| T12026 | 70 | 170 | 240 | 0 |
| T10201 | 86 | 134 | 220 | 5 |
| T10331 | 103 | 128 | 231 | 0 |
| T10812 | 73 | 147 | 220 | 5 |
| T10100 | 104 | 130 | 234 | 0 |

The combined minimum/median/maximum support is **220 / 232 / 378**, versus **70 / 103.5 / 369** originally; max/min imbalance fell from **5.27 to 1.72**. These are counts of *provisionally eligible texts*, not measured ML performance. The full [topic support table](finalization_p1/topic_support.csv), [year table](finalization_p1/by_year.csv), [work-type table](finalization_p1/by_type.csv), [language table](finalization_p1/by_language.csv) and [text-quality table](finalization_p1/text_quality.csv) are available for external review. New records include 1,753 articles, 737 preprints and 25 reviews; text missingness and work-type mix differ from the original sample and must not be interpreted as population distributions.

## Label consistency, governance and limitations

The [120-work training-only label audit](FINALIZATION_P1_LABEL_DRIFT_AUDIT.md) observed 120/120 current primary-topic and top-three-set agreements, 24/120 missing abstracts in both snapshots, and no observed moves out of the selected catalogue. That bounded result does **not** establish complete label stability or human validity. Preserve both acquisition snapshots; do not silently relabel historical records. OpenAlex topical assignment is a generated label, and broad/overlapping topics such as T10036, T10028 and T10100 require independent scope review. The [human review queue](finalization_p1/human_topic_review_queue.csv) is marked pending, not approved.

All full text, IDs, raw API responses, pages, private duplicate audit and API authentication remain local and Git-ignored. Public artifacts are aggregate only. A larger collection is **not scientifically justified now**: only 12 examples remain below the provisional per-class target, while semantic label validity and leakage review are the higher-value next checks. Phase 2 should integrate the two data origins with explicit provenance and run independent human topic review; do not start model fitting or infer any Macro-F1 gain from these counts.

## Reproduction and status

From the repository root, with the existing local data and `.env`, run `openalex-verify-ml-expansion data/raw/openalex_ml_expansion/ml_expansion_20261101T052506Z/manifest.json` and `openalex-audit-label-drift --verify-manifest data/analysis/finalization_p1_label_drift_20261101_v1/manifest.json`. The published [reproducibility manifest](finalization_p1/reproducibility_manifest.json) records source-manifest and aggregate-output hashes. The source modules have `--help`, and the exact clean-environment setup is in README. The later [integration report](FINALIZATION_P2_DATA_INTEGRATION_REPORT.md) records what was actually merged and what remained separate. **Finalization Phase 1 acquisition: complete and verified. ML model training: not started at this historical handoff.**
