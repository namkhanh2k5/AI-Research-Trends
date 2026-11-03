# Finalization Phase 2 — non-destructive ML integration protocol

Status: predeclared implementation policy, 2026-11-01. This augments [the Phase 1 proposed contract](../config/finalization_phase2_integration.yaml); it does not alter the original eight Phase 3 analytical tables or population aggregates.

## Identity and grouping

The input grain is `(dataset_origin, canonical Work ID)`. Exact Work IDs are canonical OpenAlex `https://openalex.org/W…` IDs. DOI equality uses a stripped, case-folded DOI without the `doi.org` resolver prefix. A normalized-title key uses Unicode NFC, case-folding and collapsed nonword runs; only keys of at least 20 characters participate. Union–find connects rows sharing **any** of these three keys, transitively. Empty DOI/title keys never link rows. Each group gets a stable ID derived from the lexicographically smallest Work ID. All original and expanded source rows remain in a private source audit, even when a group is excluded.

Rare-token-blocked near-title comparisons are a *separate, reviewable risk audit*, not an automatic identity assertion. A high-similarity cross-period pair may conservatively exclude a training record pending adjudication. This heuristic can miss rephrased duplicates; it cannot prove all semantic version leakage is absent.

## Representative and split precedence

The split is fixed by publication year: 2020–2023 train, 2024 development validation, 2025 sealed test. Expansion records are allowed only in train. For a group crossing periods, the latest evaluation period wins (`test > validation > train`); all lower-period versions are excluded. This rule uses only dates/identity keys for the sealed 2025 side, never its labels or outcomes. Among records in the winning period, prefer valid title and abstract of at least 30 words; then prefer an original Phase 3 source; then earlier publication date; then smaller canonical Work ID. A newer complete expansion record may therefore represent a training-only group when the earlier original record lacks usable text. **No fields are silently spliced across Works.** The selected representative retains its own label and provenance; the original row remains auditable. This is a deliberate refinement of the Phase 1 original-first proposal because original-first alone can waste a complete later version.

If multiple train/validation records in a group have conflicting primary-topic labels, mark the group `topic_label_conflict` and exclude it from model fitting or development evaluation pending adjudication. The sealed 2025 labels are not inspected for conflicts during Phase 2. All records lacking a usable title/abstract are retained in the audit and excluded from model-ready splits; neither field is fabricated. Missing DOI/language is preserved as null and does not alone exclude a record. The 30-word abstract floor is applied uniformly to original and expanded Works, so counts may differ from Phase 6A and Phase 1's provisional eligibility audit.

## Outputs and evidence

The 2025 primary-topic ID and score are null-masked in all general development and audit tables, including excluded rows. Only `test_2025_sealed.parquet` retains these labels; Phase 2 processes its row count and checksum, never its class distribution or predictions.

`ml_papers.parquet` has **one row per version-group representative** (including excluded representatives), not one row per raw source record. Private `source_record_audit.parquet` retains every original and expansion row with group, source, resolution and reason. `version_groups.parquet` summarizes each group without losing conflict or cross-period flags. `train.parquet`, `validation_2024.parquet` and `test_2025_sealed.parquet` contain only usable final representatives. The sealed test artifact is created and hashed but Phase 2 code reports only its total row count, not its class labels, predictions or classwise support. The split manifest records source/output hashes, record counts, quality and leakage checks, run ID and code hash. Completed output directories are immutable; reproduction uses a new directory and compares deterministic table hashes.

Training-only targeted records must never enter the original 12,000-work bibliometric sample, population trends, OA/citation estimands, or public research-paper explorer. OpenAlex primary topics are automated **silver labels**, not independently verified truth. Human review packages and restricted keys stay local, blinded and separated from model-development decisions.
