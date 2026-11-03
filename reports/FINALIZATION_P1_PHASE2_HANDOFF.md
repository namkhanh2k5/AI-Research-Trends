# Finalization Phase 1 → Phase 2 integration handoff

**Repository:** `namkhanh2k5/AI-Research-Trends`; branch `feature/finalization-p1-targeted-data-expansion`, based on `6e9c7390d53e6573b6379ba492d139edac45ac0a`. The delivery commit is the tip of that branch (`git rev-parse HEAD`); this text deliberately does not embed its own self-referential hash. All paths below are **local**; GitHub contains code, reports and small aggregates, **not** the acquisition data or `.env`.

## Verified source evidence

| Artifact | Local path / result |
|---|---|
| Original Phase 2 run | `data/raw/openalex_stratified/stratified_20261019T155909Z/manifest.json`; 12,000 unique works, 123 pages, original raw/interim SHA-256 `b8734cd3da2cba8c2c9ff8a9742d46d62585e55604f18630274f6bb8fbc178af` |
| Original Phase 3 tables | `data/processed/openalex_stratified/stratified_20261019T155909Z/`; works SHA-256 `9318c456d916b8c9a35b0a3c86a829a92347083357693593e743abb0253264d4` |
| Gap audit | `data/analysis/finalization_p1_gap_20261101_v1/`; 14 selected topics, 1,746 original usable training works |
| Label-drift audit | `data/analysis/finalization_p1_label_drift_20261101_v1/`; 120/120 old/current primary labels agree, 120 response hashes valid |
| Capacity counts and plan | `data/analysis/finalization_p1_source_counts_20261101_v1/`; `data/metadata/finalization_phase1_collection_plan.json`; 2,515 planned, 80 pages |
| Separate smoke run | `data/raw/openalex_ml_expansion_smoke/ml_expansion_20261101T052404Z/manifest.json`; 36 unique works, 12 pages, verifier PASS |
| Production run | `data/raw/openalex_ml_expansion/ml_expansion_20261101T052506Z/manifest.json`; 2,515 unique works, 80 pages, verifier PASS |
| Production raw JSONL | `data/raw/openalex_ml_expansion/ml_expansion_20261101T052506Z/works.jsonl`; SHA-256 `cc946d6970cbfbafcfe58b236699f2f27772545865f68b5b693872f87ef87126` |
| Production interim JSONL | `data/interim/openalex_ml_expansion/ml_expansion_20261101T052506Z/records.jsonl`; SHA-256 `cd60da68c9d53ffe181e2f4ca847bbad21baf1952e840aa8537e0b1ae67533a3` |
| Private quality staging | `data/analysis/finalization_p1_quality_20261101_v2/`; 2,515-row `record_audit.csv` and aggregate tables, with checksums in its manifest |

The [small public aggregate package](finalization_p1/reproducibility_manifest.json) records all source-manifest and published-table hashes. If these local files do not exist on another machine, do **not** substitute GitHub artifacts or synthetic records. Transfer the verified local data under an approved research-data mechanism before integration.

## Observed yield and exclusions

The production run has **2,515 raw and unique newly fetched Work IDs**, of which **33 IDs already occur in the original 12,000**. Under precedence rules there are **1,947** provisionally usable new texts: **1,638** selected-topic and **309** outside-topic. Final mutually exclusive exclusions: 499 missing abstracts, 33 short abstracts (<30 words), 33 original-ID overlaps, two original training DOI/title-version overlaps, and one missing title. No held-out ID/DOI/normalized-title collision was observed. A title/DOI key is a conservative but incomplete semantic-duplicate detector. Combined selected-topic training support is **3,384**, with gaps T10181=2, T10201=5 and T10812=5 below the target 225. All **148** topic names without verified metadata were in unassessed broad-source categories; selected-topic query IDs and assessed names were consistent.

## Contract for the next execution

The [proposed schema and governance contract](../config/finalization_phase2_integration.yaml) defines a future `ml_papers.parquet` at one canonical Work ID per row. Required fields include original text, primary topic, publication date/year, DOI, language/type, version group, collection run ID, retrieval time, label snapshot, dataset origin, ML role, text-quality status and exclusion reason. Preserve nullable metadata; never fill missing abstracts or guess identities. Keep raw response bodies and per-page hashes immutable.

Use the **original Phase 3 work** when an ID or DOI/normalized-title version group overlaps; keep later/new raw evidence for audit but do not double-count it. New-new versions use earliest publication date then canonical Work ID. Group by DOI/title *before* any split; inspect ambiguous collisions manually. `2020–2023` is training, `2024` is validation, `2025` is locked test. The 2,515 new works may enter training only after eligibility/identity checks. They may **not** enter the original analytical sample, population aggregates, Phase 4 EDA estimands, validation or test. Held-out identities may be used for leakage checks; held-out labels or outcomes must not drive topic selection, quota planning, filtering or tuning. Do not fit a vectorizer, classifier or threshold on validation/test data in Phase 2.

The fourteen labels are OpenAlex-generated primary-topic snapshots, **not human ground truth**. Keep the Phase 3 snapshot distinct from the 2026-11-01 expansion snapshot; log any future conflicting labels instead of silently harmonizing them. Obtain independent scope review using the Phase 6B blind annotation guidance and the [review queue](finalization_p1/human_topic_review_queue.csv), with explicit attention to broad T10036/T10028, T10100 optimization and neighboring NLP/CV overlaps. Every row in that queue remains marked `pending`.

## Exact next commands

From the repository root after `python -m venv .venv`, `source .venv/bin/activate`, and `pip install -e '.[dev]'`:

```bash
openalex-verify-collection data/raw/openalex_stratified/stratified_20261019T155909Z/manifest.json
openalex-verify-ml-expansion data/raw/openalex_ml_expansion/ml_expansion_20261101T052506Z/manifest.json
openalex-audit-label-drift --verify-manifest data/analysis/finalization_p1_label_drift_20261101_v1/manifest.json
pytest -q -ra
pip check
```

The **next development task** is a non-destructive Phase 2 integration/independent annotation pilot: load the original and expansion manifests, verify hashes, create a version-grouped *training-only* staging table, and run a small blinded scope review. There is deliberately no command here that replaces Phase 3 tables or launches full ML training. After human review, decide whether the 12-example residual target gap merits a narrowly justified collection; at present, a new large crawl is not supported by the measurements.

**Readiness:** GO for controlled Phase 2 integration and human review. NOT YET GO for final model training, performance claims or population-level use of targeted records.
