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
  topic suggestion with out-of-catalogue warning, literal sampled-paper search,
  and a separate content-similarity paper-discovery index. An optional bounded
  OpenAlex sync adds recent papers to that similarity index without changing
  the historical research snapshot.
- A frozen TF-IDF + Linear SVM topic-suggestion bundle. Its labels are
  OpenAlex-generated, suggestions require user confirmation, independent human
  validation is pending, and the historical 2025 test labels were made public in the uploaded workspace; that test is no longer independently sealed.
- An [academic report](deliverables/report/FINAL_ACADEMIC_REPORT.md), editable
  [presentation](deliverables/presentation/FINAL_PRESENTATION.pptx) and
  [demo script](deliverables/presentation/DEMO_SCRIPT.md).

The earlier citation-aware literature recommender was rejected as the main ML task; see the [RQ5 decision](reports/research/phase5/PHASE5_FINAL_DECISION.md). The new TF-IDF discovery feature searches similar *text* in the original sample; it does not revive citation recommendation or certify relevance.

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

The [project overview](docs/PROJECT_OVERVIEW.md),
[research methodology](docs/RESEARCH_METHODOLOGY.md),
[data dictionary](docs/DATA_DICTIONARY.md) and
[Phase 4 research report](reports/research/phase4/PHASE4_ANALYSIS_REPORT.md) explain estimands,
missingness and non-causal interpretation. Custom LLM/Multimodal/RAG text rules
are not equivalent to OpenAlex-native topics or population counts.

## Phase 4 — Research Results & Visualizations

These five GitHub-readable previews link to the verified
[Phase 4 report](reports/research/phase4/PHASE4_ANALYSIS_REPORT.md):

- [Annual publications in the complete defined population](reports/figures/phase4/rq1_population_counts.png) — RQ1 population aggregate, not sample prevalence.
- [Native-topic trends](reports/figures/phase4/rq1_native_topic_trends.png) — overlapping OpenAlex topic series within that defined population.
- [Citation distribution](reports/figures/phase4/rq2_citation_distribution.png) — RQ2 description of the detailed sample.
- [Adjusted OA coefficients](reports/figures/phase4/rq3_adjusted_coefficients.png) — RQ3 conditional associations, not causal effects.
- [Country co-affiliation network](reports/figures/phase4/rq4_country_network.png) — RQ4 sampled collaboration links, not a global network.

See the [unified Phase 6 report](reports/phase6/PHASE6_REPORT.md),
[RQ6 topic-support chart](reports/phase6/figures/topic_support.png) and
[ML development report](reports/machine_learning/FINALIZATION_P3_FINAL_ML_REPORT.md) for
classification evidence. The 2024 development results are **not** final-test
results or independent human semantic accuracy.

## Install and run locally

Python 3.11+ on Ubuntu/Linux:

```bash
git lfs install
# Minimal clone: do not download all research LFS objects by default.
GIT_LFS_SKIP_SMUDGE=1 git clone --depth 1 https://github.com/namkhanh2k5/AI-Research-Trends.git
cd AI-Research-Trends
# Restore the model, web index and canonical works needed to build discovery:
git lfs pull --include="models/topic_placement_v2/model.joblib,data/artifacts/web/topic_explorer/paper_index.parquet,data/processed/openalex_stratified/stratified_20261019T155909Z/works.parquet"
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
openalex-build-web-data verify data/artifacts/web/topic_explorer
openalex-paper-discovery build
openalex-paper-discovery verify \
  --works data/processed/openalex_stratified/stratified_20261019T155909Z/works.parquet \
  --web-dir data/artifacts/web/topic_explorer
streamlit run dashboard/app.py --server.address 127.0.0.1
```

The Topic Explorer works without the model. The "Classify My Research" page
offers both topic suggestions and independent text-similarity search; the latter
also works after `no_confident_match` or if the model is unavailable. The
build-once index is Git-ignored and independently checksum-verified; it is not
rebuilt on every app launch. Its default results require title and abstract;
optional title-only results carry a comparability warning. For CLI search:

```bash
openalex-paper-discovery search --title "Neural translation with multilingual attention models" --top-k 5
```

### Refresh recent application papers

The original 2020–2025 research dataset, population counts, reports and frozen
classifier never change. `openalex-sync-application` maintains a separate local
`data/application/openalex_sync/` store and rebuilds the TF-IDF discovery index
from the original sample plus validated recent application records. Publication
dates are not synchronization dates. This is a **bounded publication-date
fallback**, not complete OpenAlex change-data capture: older newly indexed
works, retrospective metadata updates and deletions can be missed. See the
[web sync guide](docs/WEB_APPLICATION.md#optional-openalex-application-sync).

```bash
# After installing the package, restoring LFS inputs and building the original index:
openalex-sync-application --help
openalex-sync-application --lookback-days 3 --max-records 3000  # dry run
openalex-sync-application --lookback-days 3 --max-records 3000 --execute
# On interruption, use the incomplete run ID printed in its manifest:
openalex-sync-application --resume sync_YYYYMMDDTHHMMSSZ_XXXXXXXX --max-records 3000 --execute
```

Set `OPENALEX_API_KEY` in ignored `.env` before `--execute`. The web app only
reads the last validated index and never calls OpenAlex. No daily model
retraining or automatic changes to the research trend charts occur.

Classification needs `models/topic_placement_v2/`. For direct inference on a new
draft (a suggestion, not a human-validated topic label):

```bash
openalex-package-topic-model infer \
  --model-dir models/topic_placement_v2 \
  --title "Image segmentation with neural networks" \
  --abstract "We study a neural network approach to segmenting images and compare its behavior across several visual datasets and evaluation settings."
```

The [web application guide](docs/WEB_APPLICATION.md),
[technical discovery evaluation](reports/application/PAPER_DISCOVERY_TECHNICAL_EVALUATION.md),
[reproducibility guide](docs/REPRODUCIBILITY.md) and
[deployment guide](docs/DEPLOYMENT_GUIDE.md) explain the local-only demo and
verified artifact restoration. The selective `git lfs pull` above suffices for
the local demo after the discovery index is built; `git lfs pull` without a filter restores all 35 LFS paths
needed for full research verification. The published snapshot intentionally
omits some retired reruns and superseded model/data versions; the retained
Phase 6 pilot and reproduction are physically deduplicated under
`data/analysis/phase6/`. Verify them with `openalex-verify-phase6`; see
[artifact retention policy](docs/archive/REPOSITORY_CLEANUP.md). No public hosted URL exists.

## Data, ETL and reproducibility

```text
config/                      active study/catalogue/application settings; historical/ has frozen protocols
src/ai_research_trends/      crawling, preprocessing, analysis, ML, web
dashboard/                   Streamlit research and separate reviewer apps
data/raw/, interim/          original API responses and extracted records
data/processed/              normalized Parquet and integrated ML tables
data/artifacts/web/           verified Topic Explorer package; rebuildable discovery index
data/analysis/, metadata/    distinct historical analyses, manifests and profiles
models/topic_placement_v2/   frozen model bundle; binary uses Git LFS
notebooks/                   thin inspection notebooks
reports/, docs/              findings, methodology and published figures
deliverables/                academic report, presentation and demo
tests/unit/, integration/, browser/   offline tests; optional live/browser checks
```

The application reads its three active artifact locations from
[`config/application.yaml`](config/application.yaml). The verified web package
and frozen model retain their original bytes at the functional paths above;
their old run-named paths are narrow symbolic links for immutable provenance
and the hash-frozen inference CLI. Historical collection, pilot and proposed
integration YAMLs are byte-preserved under `config/historical/` with old-path
links. Seven repeated Phase 1 publication summaries and one repeated Phase 5
eligibility table now link to byte-identical canonical files. The original
sample, targeted expansion and integrated ML data remain separate datasets;
the application never treats the expansion as population evidence.

| Workstream | Canonical input/product | Main verification or user command |
|---|---|---|
| Data collection | `data/raw/openalex_stratified/` and population manifests | `openalex-verify-collection` |
| Data processing | `data/processed/openalex_stratified/` and separate ML integration | `openalex-validate-processed` |
| Research analysis | `data/analysis/phase4_*`, Phase 5 audit and `phase6/` | `openalex-validate-phase4`, `openalex-verify-phase6` |
| Machine learning | integrated ML table and `models/topic_placement_v2/` | `openalex-verify-integrated-topics`, `openalex-verify-final-ml` |
| Web application | `data/artifacts/web/topic_explorer/` and rebuildable discovery index | `openalex-build-web-data verify`, `streamlit run dashboard/app.py` |

Historical experiment CLI entry points remain installed for exact reproduction;
the commands above are the routine read-only checks. The frozen classifier
does not run during manual Topic Explorer browsing.

The [report index](reports/README.md),
[Phase 2 report](reports/research/phase2/PHASE2_COLLECTION_REPORT.md) and
[Phase 3 quality report](reports/research/phase3/PHASE3_DATA_QUALITY_REPORT.md) identify the
original collection and preprocessing runs. Targeted ML development records
must not be silently merged into the 12,000-work analytical sample.

Core commands expose `--help`: `openalex-collect-stratified`,
`openalex-verify-collection`, `openalex-preprocess`,
`openalex-validate-processed`, `openalex-analyze-phase4`,
`openalex-validate-phase4`, `openalex-analyze-rq6` and
`openalex-package-topic-model`.
The new `openalex-paper-discovery` command provides `build`, `verify` and
`search` subcommands. The retrieval package is separate from the frozen SVM
bundle and the original verified web-data package.
New collection commands must use a **new versioned output directory**;
do not rerun acquisition or training just to start the website.

For an agent-facing map of exact local paths and remaining work, read
[PROJECT_HANDOFF.md](PROJECT_HANDOFF.md). The public repository contains source,
raw and processed research data, reviewer packages, former sealed-test records
and model binaries. Publication does **not** prove redistribution permission or
independent blind-test validity. Review those issues before external reuse.
