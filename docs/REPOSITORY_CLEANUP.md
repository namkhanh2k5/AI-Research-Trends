# Repository cleanup and artifact retention

## Current active scope

The supported project is the OpenAlex AI/CV study (RQ1–RQ6), the Streamlit
Topic Explorer, the frozen TF-IDF/Linear SVM bundle, and its published
academic deliverables. RQ7/Crossref and the experimental Venue Discovery
pipeline were removed from the active tree.

## Retained canonical artifacts

| Purpose | Canonical location |
| --- | --- |
| Original collected 12,000-paper snapshot | `data/raw/openalex_stratified/stratified_20261019T155909Z/` |
| Original normalized analysis dataset | `data/processed/openalex_stratified/stratified_20261019T155909Z/` |
| Final RQ1–RQ4 analytical run | `data/analysis/phase4_stratified_20261019T155909Z_v3/` |
| Published figures, statistics and studies | `reports/`, `docs/` |
| RQ5 feasibility audit | `data/analysis/phase5_literature_pilot_20261028_v4/` |
| Final RQ6 topic-validation run | `data/analysis/phase6b_topic_validation_20261028_v3/` |
| Final integrated ML data | `data/processed/ml_topic_classification/finalization_p2_20261101_v3/` |
| Model evaluation evidence | `data/analysis/finalization_p3_models_20261101_v1/` |
| Open-set evaluation evidence | `data/analysis/finalization_p3_open_set_20261101_v1/` |
| Frozen application model | `models/finalization_p3/topic_placement_v2/` |
| Website data package | `data/analysis/finalization_p2_web_data_20261101_v3/` |

The remaining original Phase 2 and ML expansion raw data are intentionally kept
for provenance; the local demo does not require downloading them.

## Reader-facing consolidation (2026-11-05)

Start with [the project overview](PROJECT_OVERVIEW.md),
[research methodology](RESEARCH_METHODOLOGY.md),
[web guide](WEB_APPLICATION.md), [reproducibility](REPRODUCIBILITY.md), and the
[report index](../reports/README.md). Repeated setup/proposal/handoff prose was
merged into those guides; original predeclared protocols and manifest-hashed
documents remain in place. Phase 6 published aggregate tables moved from
`reports/phase6a/` and `reports/phase6b/` to
`reports/phase6/pilot/` and `reports/phase6/validation/`; its support figure
moved to `reports/phase6/figures/`. All these published artifact bytes and
their source hashes are unchanged. The [unified Phase 6 report](../reports/phase6/PHASE6_REPORT.md)
and [artifact map](../reports/phase6/artifact_map.json) distinguish pilot,
reproduction, metadata, validation and integrated RQ6 runs.

The five original Phase 6-related `data/analysis/` directories did **not**
move. Their manifests describe distinct runs and some downstream consumers
expect original paths; the 16 identical pilot/reproduction outputs also have
different manifests. Deleting one would lose a separately verifiable run, while
Git already deduplicates equal blobs internally. This is a deliberate
provenance-preserving exception to physical consolidation, not a hidden second
canonical result. The old report filenames retained at the top level are
detailed historical evidence; readers should enter through the new index.

## Removed from the active branch

- RQ7/RQ7.1 Crossref ETL, AI-assisted source validation, historical Venue
  Discovery code, reports, test modules and experimental datasets.
- Phase 4 noncanonical reruns/dry runs and duplicate published-figure exports.
- Superseded Phase 5 candidate snapshots, repeated literature/retrieval runs.
- Earlier Phase 6 pilots and topic-validation versions.
- Superseded Phase 2 integrated datasets, Phase 3 model rerun, and model v1.
- Intermediate `data/interim/` LFS copies, smoke-test snapshots and old pilot
  collection outputs.
- Disposable browser screenshots/probe outputs from the old web audits;
  scientific figures and the two report/presentation Chrome assets remain.

This is a **retention policy**, not a claim that prior experiments never
happened. Their findings and research decisions remain documented in reports.
The older repository snapshot `811e98f7b3db9fba9d7fd187dbecce963fa0a863`
contains the original full workspace for historical reference. Git history
and Git LFS objects are not rewritten or purged by these commits.

The integrated ML manifest still records the retired
`expansion_interim` JSONL and its original SHA-256. The current verifier
reports this one historical source as unavailable, while checking every
retained input and output against its recorded hash, size and row count, then
rechecking split identities and isolation. It cannot independently replay
the original expansion transformation without the retired interim file.
Phase 4 manifests contain old absolute paths; verification and report
generation resolve them only within the current checkout and retain the
original checksum requirements.

## Efficient fresh checkout

```bash
git lfs install
GIT_LFS_SKIP_SMUDGE=1 git clone --depth 1 https://github.com/namkhanh2k5/AI-Research-Trends.git
cd AI-Research-Trends
git lfs pull --include="models/finalization_p3/topic_placement_v2/model.joblib,data/analysis/finalization_p2_web_data_20261101_v3/paper_index.parquet"
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev,web,deliverables]"
openalex-build-web-data verify data/analysis/finalization_p2_web_data_20261101_v3
streamlit run dashboard/app.py --server.address 127.0.0.1
```

For a complete active-artifact reproducibility checkout, run `git lfs pull`
without filters. Only an old snapshot can reproduce a deleted historical
intermediate run exactly. Actual GitHub LFS storage utilization is not
decreased by removing current-tree pointers alone; a separate, deliberate
retention and history management decision would be needed.

## Scientific and publication safeguards

The original 12,000-work analytical sample remains distinct from the targeted
ML development expansion. The published 2025 labels and answer keys no longer
meet independent sealed/blind evaluation requirements. Third-party data
redistribution permissions must be reviewed separately. Do not treat source
availability as consent to redistribute it.
