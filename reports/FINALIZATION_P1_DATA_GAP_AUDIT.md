# Finalization Phase 1 — training-data gap audit

**Observed inputs.** The immutable Phase 3 sample has 12,000 works; this audit uses only the 2020–2023 portion of `works.parquet` and `work_topics.parquet`. Their SHA-256 values are recorded in the local `data/analysis/finalization_p1_gap_20261101_v1/manifest.json`. The 2024 validation and 2025 locked-test labels were not used to choose topics, targets, quotas, or examples. The [complete machine-readable audit](finalization_p1/data_gap.csv) contains all 14 catalogue B topics, original 2020–2023 counts, text availability, version exclusions, year distribution, scores, language, and scope concerns.

The original selected-topic training support was **1,746 usable works from 2,234 source works**. Eligibility uses the existing Phase 6A rule: nonblank title and abstract, earliest DOI/title-linked version. There were 1,748 abstracts present, so missing text dominates exclusion. Original support ranged from **70 to 369** per topic (median **103.5**, max/min ratio **5.27**). The training-side shortfall was **1,548** works for the *planning* target of 225 per topic, or **2,523** for 300. The 225 target is a pragmatic support target, not a theoretical minimum guaranteeing classifier performance.

| Primary topic | Original usable | Missing abstract | Gap to 225 | Estimated raw needed |
|---|---:|---:|---:|---:|
| T10028 | 149 | 21.6% | 76 | 97 |
| T10036 | 369 | 19.8% | 0 | 0 |
| T10052 | 127 | 28.2% | 98 | 137 |
| T10100 | 104 | 38.5% | 121 | 197 |
| T10181 | 94 | 16.1% | 131 | 157 |
| T10201 | 86 | 15.5% | 139 | 167 |
| T10331 | 103 | 25.4% | 122 | 164 |
| T10462 | 120 | 14.9% | 105 | 124 |
| T10664 | 190 | 17.0% | 35 | 43 |
| T10775 | 104 | 15.4% | 121 | 144 |
| T10812 | 73 | 27.0% | 152 | 209 |
| T11307 | 84 | 22.2% | 141 | 182 |
| T11689 | 73 | 22.3% | 152 | 196 |
| T12026 | 70 | 21.3% | 155 | 198 |

Estimates divide each topic's shortfall by its *observed local usable fraction* and round upward. They are planning estimates, not a forecast of independent usable records: OpenAlex sampling may return IDs already present locally, DOI/title-linked versions, and records with different text completeness. A targeted expansion was justified because 13 of 14 topics were below 225 and the sum of estimated raw needs (2,015) fit the predefined 3,000-record ceiling. T10036 was not targeted for positive examples because it already had 369. Independent human scope review remains pending, especially for broad T10036 and T10028, optimization T10100, and neighboring NLP/CV topics.

This targeted ML corpus must **not** be pooled with the proportional 12,000-work sample for publication trends, OA associations, impact estimates, or population-level topic proportions. The approved population aggregates remain separate.
