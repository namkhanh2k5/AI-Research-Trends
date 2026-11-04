# Project handoff (local research workspace)

Start with [README.md](README.md) for the study and app. This file is the short
map for the next coding agent; it is **not** permission to refresh results or
use the 2025 test labels for evaluation.

## What works now

- OpenAlex collection and validation (`src/ai_research_trends/crawling/`);
  normalized works, topics, affiliations and references
  (`preprocessing/`); bibliometric/statistical RQ1–RQ4 analyses
  (`analysis/`).
- RQ5 reference-network feasibility and RQ6 topic-label analysis; the
  citation recommender was rejected as the main ML task.
- Frozen TF-IDF/Linear SVM assisted topic placement, Topic Briefs and
  `dashboard/app.py`. A separate build-once TF-IDF/cosine index searches
  textually similar original-sample papers. Topic suggestions use OpenAlex silver labels and
  require explicit user confirmation. `dashboard/reviewer.py` is a separate
  local human-review workflow.
- Academic report and slides in `deliverables/`; research outputs and figures
  in `reports/` and `data/analysis/`.

## Research artifact map

| Purpose | Path |
|---|---|
| Original 12,000-work raw run | `data/raw/openalex_stratified/stratified_20261019T155909Z/` |
| Original eight Parquet tables | `data/processed/openalex_stratified/stratified_20261019T155909Z/` |
| Population counts and sampling plan | `data/metadata/population_counts_pre_phase2.json`, `data/metadata/phase2_sampling_plan.json` |
| Integrated ML development data | `data/processed/ml_topic_classification/finalization_p2_20261101_v3/` |
| Website data package | `data/analysis/finalization_p2_web_data_20261101_v3/` |
| Frozen topic model | `models/finalization_p3/topic_placement_v2/` |
| Rebuildable original-sample paper-discovery index | `data/analysis/paper_discovery_original_sample_v1/` (ignored; build locally) |

The original analytical sample and targeted ML development data have
**different purposes and selection mechanisms**. Do not use targeted records
for population prevalence or silently merge them into the 12,000-work sample.
The repository is public and the complete workspace transfer includes
restricted answer keys, blind reviewer packages, raw paper text and 2025
labels. Their former blind/sealed status is **compromised by publication**.
Do not claim a subsequent independent sealed-test evaluation on this copy,
and do not expose the human reviewers to answer keys before their work.

Large `*.jsonl`, `*.parquet`, `*.joblib` and `*.pkl` files use Git LFS.
Prefer a shallow clone and fetch only runtime assets for website work:

```bash
git lfs install
GIT_LFS_SKIP_SMUDGE=1 git clone --depth 1 https://github.com/namkhanh2k5/AI-Research-Trends.git
cd AI-Research-Trends
git lfs pull --include="models/finalization_p3/topic_placement_v2/model.joblib,data/analysis/finalization_p2_web_data_20261101_v3/paper_index.parquet,data/processed/openalex_stratified/stratified_20261019T155909Z/works.parquet"
```

Run plain `git lfs pull` to fetch the 35 retained LFS paths for full research
verification. Historical reruns and intermediate outputs were intentionally
pruned from the current tree. Read [retention details](docs/REPOSITORY_CLEANUP.md).


The clone contains datasets and the saved model, but **not** `.env` or a
Python environment. Configure credentials locally only if making new API
requests. Public availability does not establish redistribution rights for
third-party metadata or model inputs.

## Setup and everyday commands

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev,web,deliverables]"
python -m pip check
python -m pytest -q -ra -o addopts=''
openalex-build-web-data verify data/analysis/finalization_p2_web_data_20261101_v3
openalex-paper-discovery build
openalex-paper-discovery verify
streamlit run dashboard/app.py --server.address 127.0.0.1
```

`OPENALEX_API_KEY` (local ignored `.env`) is needed only for new OpenAlex
requests. `OPENALEX_CONTACT_EMAIL` is optional; `AI_TRENDS_WEB_DATA`,
`AI_TRENDS_MODEL`, and `AI_TRENDS_DISCOVERY_INDEX` can override local app artifact paths. Never print or
commit credentials.

Direct frozen-model inference:

```bash
openalex-package-topic-model infer --help
```

## Where to read and what remains

- RQ1–RQ4: [Phase 4 research report](reports/PHASE4_ANALYSIS_REPORT.md).
  RQ5: [reference-network decision](reports/PHASE5_FINAL_DECISION.md).
  RQ6/ML: [topic validation](reports/PHASE6B_FINAL_TOPIC_VALIDATION_REPORT.md)
  and [model evaluation](reports/FINALIZATION_P3_FINAL_ML_REPORT.md).
- Independent human semantic validation remains **pending**.
  The 2025 final-test gate was historically sealed but is no longer
  independently sealed after this public workspace transfer. Public
  deployment and redistribution rights require separate review.
