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

## Removed from the active branch

- RQ7/RQ7.1 Crossref ETL, AI-assisted source validation, historical Venue
  Discovery code, reports, test modules and experimental datasets.
- Phase 4 noncanonical reruns/dry runs and duplicate published-figure exports.
- Superseded Phase 5 candidate snapshots, repeated literature/retrieval runs.
- Earlier Phase 6 pilots and topic-validation versions.
- Superseded Phase 2 integrated datasets, Phase 3 model rerun, and model v1.
- Intermediate `data/interim/` LFS copies, smoke-test snapshots and old pilot
  collection outputs.

This is a **retention policy**, not a claim that prior experiments never
happened. Their findings and research decisions remain documented in reports.
The older repository snapshot `811e98f7b3db9fba9d7fd187dbecce963fa0a863`
contains the original full workspace for historical reference. Git history
and Git LFS objects are not rewritten or purged by these commits.

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
