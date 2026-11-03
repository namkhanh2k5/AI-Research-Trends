# Finalization Phase 2 — data integration audit

## Scope and provenance

The original Phase 2/3 12,000-work dataset and the separate 2,515-work targeted ML expansion were read from local, Git-ignored artifacts. The original 123-page collection verifier, expansion 80-page verifier, eight Phase 3 Parquet checksums, Phase 4's 64-output verifier, and Phase 6B topic-run verifier passed before integration. The expansion is *not* a probability sample and is excluded from population and original-sample research estimates. No Phase 1–4 source file was changed.

The primary output is `data/processed/ml_topic_classification/finalization_p2_20261101_v3/` (local only), with `split_manifest.json` recording every input/output SHA-256, source run IDs, code and protocol hashes, row counts, UTC processing time, exclusions and checks. Its read-only verifier passed. An independent rerun in `_v3_rerun/` produced identical SHA-256 hashes for all eight Parquet outputs. Earlier local v1/v2 rehearsals are superseded; v3 masks sealed 2025 labels from general development tables and matches the final protocol document.

## Identity and split accounting

| Measure | Observed |
|---|---:|
| Original source rows | 12,000 |
| Targeted expansion source rows | 2,515 |
| Total source rows | 14,515 |
| Transitive Work-ID/DOI/normalized-title groups | 14,470 |
| Groups containing multiple source records | 45 |
| Cross-period exact version groups | 3 |
| Development-period topic-label conflict groups | 0 |
| High-similarity cross-period near-title pairs | 1 |
| Usable 2020–2023 train | 7,002 (5,055 original + 1,947 expansion) |
| Usable 2024 validation | 1,843 (original only) |
| Usable 2025 sealed test | 2,318 (count only; original only) |

The source-grain audit records 11,163 eligible representatives, 3,055 missing abstracts, 248 short abstracts, 3 missing titles, 42 nonrepresentative versions, 3 lower-period cross-version records, and 1 lower-period near-title risk held out pending review. The text floor is at least 30 abstract words for both sources. Transitive grouping uses exact canonical Work ID, normalized DOI and normalized title; it does not infer identity from author names. For cross-period groups, the later split wins and the earlier record cannot enter model development. The near-title audit is a conservative high-similarity screen, **not a guarantee that all semantic duplicates were found**.

Train contains 3,355 frozen-catalogue examples and 3,647 outside-catalogue examples. The new expansion contributes 1,638 and 309 respectively. Five selected topics remain below the 225-row planning target by a combined 23 rows; this is not a reason to silently collect more or change the catalogue. The 2024 validation set is kept separate. General audit and canonical tables mask `primary_topic_id` and `topic_score` for 2025; only `test_2025_sealed.parquet` retains locked labels. No 2025 class distribution, performance metric or prediction was inspected in this phase.

## Scientific cautions

The 225-row target is an engineering support heuristic, not an empirical learning-curve or generalization guarantee. OpenAlex topic labels are silver labels, not human ground truth. Topic assignments can change with the OpenAlex classifier snapshot. Class balance here is deliberately affected by targeted expansion, so it cannot estimate population topic prevalence. Version grouping by title may over-group generic titles; the full source audit and version-group table allow investigation. Human review is pending, and the sealed test must remain unopened until the final model/evaluation protocol is frozen.

Verification command:

```bash
openalex-verify-integrated-topics data/processed/ml_topic_classification/finalization_p2_20261101_v3 --compare-dir data/processed/ml_topic_classification/finalization_p2_20261101_v3_rerun
```
