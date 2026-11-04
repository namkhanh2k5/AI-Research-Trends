# AI Research Trends & Scientific Impact

A reproducible undergraduate Data Science study of the **OpenAlex-defined AI/CV
research landscape**, with bibliometric analysis and an assisted research-topic
explorer. The project asks how publications, citation impact, Open Access and
co-affiliation changed in 2020–2025. It also examines reference-network
limitations and topic-label reliability. It does **not** cover all global AI research.

## What the project provides

- A timestamped OpenAlex collection, eight normalized Parquet tables, and
  documented data-quality checks.
- Population-level publication counts kept separate from a 12,000-work
  detailed sample. Raw citations are not measures of research quality.
- RQ1–RQ6 analyses, research reports and figures, with separate data for bibliometrics and ML.
- A local Streamlit explorer: research landscape, 14-topic briefs, assisted
  topic suggestion, sampled-paper search and methodology/model evaluation.
- A frozen TF-IDF + Linear SVM topic-suggestion bundle. Its labels are
  OpenAlex-generated, suggestions require user confirmation, independent human
  validation is pending, and the historical 2025 test labels were made public in the uploaded workspace; that test is no longer independently sealed.
- An [academic report](deliverables/report/FINAL_ACADEMIC_REPORT.md), editable
  [presentation](deliverables/presentation/FINAL_PRESENTATION.pptx) and
  [demo script](deliverables/presentation/DEMO_SCRIPT.md).

The earlier citation-aware literature recommender was rejected as the main ML task; see the [RQ5 decision](reports/PHASE5_FINAL_DECISION.md). The published application instead focuses on an assisted topic explorer.

**Stack:** Python 3.11+, requests, pandas/PyArrow, NumPy/SciPy,
scikit-learn, Matplotlib/Seaborn, Streamlit/Plotly and pytest. The source
package and CLI entry points are defined in `pyproject.toml`.

## Study scope and research questions

The primary population consists of OpenAlex articles, reviews and preprints
published from **2020-01-01 through 2025-12-31**, whose *primary* topic belongs
to subfield 1702 (Artificial Intelligence) or 1707 (Computer Vision and Pattern
Recognition), excluding known retractions. The original snapshot contains
937,493 such works; the all-work sensitivity population contains 942,825.
These are timestamped OpenAlex counts, not timeless global AI totals. The
12,000-work year-stratified sample supports detailed analyses; its API-based
sampling weights are **nominal**, not proven inverse inclusion probabilities.
Targeted historical ML expansion is a third, separate dataset.

| Question | Subject | Main source |
|---|---|---|
| RQ1 | Publication and native-topic trends | Population aggregates |
| RQ2 | Citation impact, age and field | Original detailed sample |
| RQ3 | Open Access associations, not effects | Original detailed sample |
| RQ4 | Institutional/country co-affiliation | Original detailed sample |
| RQ5 | Reference-network coverage and retrieval feasibility | Sampled reference edges |
| RQ6 | Topic-label scope and ambiguity | Frozen catalogue and development data |

The [research report](reports/PHASE4_ANALYSIS_REPORT.md),
[data-collection strategy](docs/DATA_COLLECTION_STRATEGY.md),
[data dictionary](docs/DATA_DICTIONARY.md) and
[project limitations](docs/FINAL_PROJECT_LIMITATIONS.md) explain the estimands,
missingness and non-causal interpretation. Custom LLM/Multimodal/RAG text rules
are not equivalent to OpenAlex-native topics or population counts.

## Phase 4 — Research Results & Visualizations

These five GitHub-readable previews link to the verified
[Phase 4 report](reports/PHASE4_ANALYSIS_REPORT.md):

- [Annual publications in the complete defined population](reports/figures/phase4/rq1_population_counts.png) — RQ1 population aggregate, not sample prevalence.
- [Native-topic trends](reports/figures/phase4/rq1_native_topic_trends.png) — overlapping OpenAlex topic series within that defined population.
- [Citation distribution](reports/figures/phase4/rq2_citation_distribution.png) — RQ2 description of the detailed sample.
- [Adjusted OA coefficients](reports/figures/phase4/rq3_adjusted_coefficients.png) — RQ3 conditional associations, not causal effects.
- [Country co-affiliation network](reports/figures/phase4/rq4_country_network.png) — RQ4 sampled collaboration links, not a global network.

See the [RQ6 topic-support chart](reports/figures/phase6/topic_support.png)
and [ML development report](reports/FINALIZATION_P3_FINAL_ML_REPORT.md) for
classification evidence. The 2024 development results are **not** final-test
results or independent human semantic accuracy.

## Install and run locally

Python 3.11+ on Ubuntu/Linux:

```bash
git lfs install
# Minimal clone: do not download all research LFS objects by default.
GIT_LFS_SKIP_SMUDGE=1 git clone --depth 1 https://github.com/namkhanh2k5/AI-Research-Trends.git
cd AI-Research-Trends
# Restore only the frozen app model and the compact website paper index:
git lfs pull --include="models/finalization_p3/topic_placement_v2/model.joblib,data/analysis/finalization_p2_web_data_20261101_v3/paper_index.parquet"
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev,web,deliverables]"
cp .env.example .env
python -m pip check
python -m pytest -q -ra -o addopts=''
```

Set `OPENALEX_API_KEY` in the ignored `.env` **only if running collection**;
normal browsing and inference make no OpenAlex calls. The app uses the
verified web-data package and trusted model bundle included in this workspace:

```bash
openalex-build-web-data verify data/analysis/finalization_p2_web_data_20261101_v3
streamlit run dashboard/app.py --server.address 127.0.0.1
```

The Topic Explorer works without the model; classification needs
`models/finalization_p3/topic_placement_v2/`. For direct inference on a new
draft (a suggestion, not a human-validated topic label):

```bash
openalex-package-topic-model infer \
  --model-dir models/finalization_p3/topic_placement_v2 \
  --title "Image segmentation with neural networks" \
  --abstract "We study a neural network approach to segmenting images and compare its behavior across several visual datasets and evaluation settings."
```

The [web user guide](docs/WEB_USER_GUIDE.md),
[artifact contract](docs/MODEL_AND_DATA_ARTIFACTS.md) and
[deployment guide](docs/DEPLOYMENT_GUIDE.md) explain the local-only demo and
verified artifact restoration. The selective `git lfs pull` above suffices for
the local demo; `git lfs pull` without a filter restores all 35 LFS paths
needed for full research verification. The published snapshot intentionally
omits historical reruns, pilots and superseded model/data versions; see
[artifact retention policy](docs/REPOSITORY_CLEANUP.md). No public hosted URL exists.

## Data, ETL and reproducibility

```text
config/                      frozen study and topic definitions
src/ai_research_trends/      crawling, preprocessing, analysis, ML, web
dashboard/                   Streamlit research and separate reviewer apps
data/raw/, interim/          original API responses and extracted records
data/processed/              normalized Parquet and integrated ML tables
data/analysis/, metadata/    versioned analyses, manifests and profiles
models/                      frozen model bundles; large artifacts use Git LFS
notebooks/                   thin inspection notebooks
reports/, docs/              findings, methodology and published figures
deliverables/                academic report, presentation and demo
tests/                       offline tests; optional live/browser checks
```

The [Phase 2 report](reports/PHASE2_COLLECTION_REPORT.md) and
[Phase 3 quality report](reports/PHASE3_DATA_QUALITY_REPORT.md) identify the
original collection and preprocessing runs. Targeted ML development records
must not be silently merged into the 12,000-work analytical sample.

Core commands expose `--help`: `openalex-collect-stratified`,
`openalex-verify-collection`, `openalex-preprocess`,
`openalex-validate-processed`, `openalex-analyze-phase4`,
`openalex-validate-phase4`, `openalex-analyze-rq6` and
`openalex-package-topic-model`.
New collection commands must use a **new versioned output directory**;
do not rerun acquisition or training just to start the website.

For an agent-facing map of exact local paths and remaining work, read
[PROJECT_HANDOFF.md](PROJECT_HANDOFF.md). The public repository contains source,
raw and processed research data, reviewer packages, former sealed-test records
and model binaries. Publication does **not** prove redistribution permission or
independent blind-test validity. Review those issues before external reuse.
