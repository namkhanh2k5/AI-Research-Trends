# Phase 2 Collection Final Gate

**Gate date:** 2026-10-19 UTC

**Decision:** ready for the controlled 12,000-work run; the run has not started.

## Accepted controls

- The plan declares the validated primary non-retracted population artifact, its
  SHA-256, the exact approved filter, and `group_by=publication_year`.
- Collection recomputes Hamilton largest-remainder allocation from all six `N_h`
  values and rejects inconsistent totals, `n_h`, remainders, nominal `n_h/N_h`,
  or nominal `N_h/n_h` weights.
- The current validated allocation remains 1,606, 1,650, 1,615, 1,865, 2,288,
  and 2,976 records for 2020–2025, totaling 12,000.
- Raw page and probe writes use exclusive temporary files, `fsync`, and atomic
  rename. Interrupted or malformed orphan files are quarantined with hashes and
  provenance instead of being accepted as checkpoints.
- Resume checks plan/config hashes, seed, page size, and safe paths. Its default
  `all` mode re-fetches every checkpointed page and compares ordered canonical Work
  IDs before requesting new pages. `sampled` and `minimal` are documented weaker
  options; recovered orphan pages are mandatory probes in every mode.
- A resume mismatch stores the new probe response, marks the run incomplete, and
  refuses to mix retrieval snapshots. Existing raw files are not changed.
- Completed runs are immutable under normal resume. The read-only verifier checks
  all raw-page evidence plus the SHA-256 and ordered Work IDs of both JSONL outputs.
- Manifests report expected/checkpointed/on-disk pages, page and output bytes,
  page Work IDs, duplicate validation, API attempts/failures, probe evidence, and
  final completeness.

Validation results:

- offline suite: **65 passed, 1 skipped** (live probe skipped by default);
- opt-in live OpenAlex probe: **1 passed** on 2026-10-19;
- plan regeneration and collector dry-run: passed for exactly 12,000 works;
- full 12,000-work collection: not executed.

## Remaining risks

- OpenAlex does not provide database snapshot isolation. `minimal` checks only one
  page per started stratum and `sampled` checks its boundaries; neither establishes
  complete sample stability. Default `all` checks all existing page memberships,
  but cannot prove metadata stability or prevent changes after probing. Restart a
  fresh run if strict single-snapshot comparability is required.
- Immediate seeded repeats were stable in the live probe, but uniform inclusion
  probability and stability across OpenAlex updates remain unverified. Weights are
  nominal and must be described as such.
- Population counts may change after plan creation even when the saved source and
  plan remain internally valid. Regenerate aggregates and the plan if collection
  is delayed materially.
- The collector keeps 12,000 validated work dictionaries and IDs in memory until
  final JSONL creation. Monitor memory and disk during this bounded run. For larger
  targets, stream to append-only staging storage and use DuckDB/SQLite for a
  disk-backed ID set rather than extending the in-memory design.
- Raw response pages, probe responses, and raw/interim JSONL intentionally require
  additional disk space. A complete manifest—not file presence alone—is the
  success criterion.

## Exact controlled-run command

From the repository root, after confirming `.env` contains a valid key and the
dry-run still reports 12,000 planned records:

```bash
source .venv/bin/activate
openalex-collect-stratified \
  --plan data/metadata/phase2_sampling_plan.json \
  --config config/topics.yaml \
  --raw-root data/raw/openalex_stratified \
  --interim-root data/interim/openalex_stratified \
  --seed 20251019 \
  --per-page 100 \
  --resume-verify all \
  --execute
```

Safe validation without collection:

```bash
openalex-collect-stratified \
  --plan data/metadata/phase2_sampling_plan.json
```

Resume only the same plan/config/seed/page-size combination:

```bash
openalex-collect-stratified \
  --plan data/metadata/phase2_sampling_plan.json \
  --config config/topics.yaml \
  --raw-root data/raw/openalex_stratified \
  --interim-root data/interim/openalex_stratified \
  --seed 20251019 \
  --per-page 100 \
  --resume-manifest data/raw/openalex_stratified/stratified_<UTC>/manifest.json \
  --resume-verify all \
  --execute
```

After completion, verify without modifying the run:

```bash
openalex-verify-collection \
  data/raw/openalex_stratified/stratified_<UTC>/manifest.json
```
