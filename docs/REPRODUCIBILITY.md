# Reproducibility and artifact map

Use a clean Ubuntu/Linux Python 3.11+ environment. Retained data and model
artifacts are in Git LFS; the separate Paper Discovery index is Git-ignored and
must be built once. No collection or retraining is required to start the site.

```bash
git lfs install
GIT_LFS_SKIP_SMUDGE=1 git clone --depth 1 https://github.com/namkhanh2k5/AI-Research-Trends.git
cd AI-Research-Trends
git lfs pull --include="models/topic_placement_v2/model.joblib,data/artifacts/web/topic_explorer/paper_index.parquet,data/processed/openalex_stratified/stratified_20261019T155909Z/works.parquet"
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev,web,deliverables]"
python -m pip check
python -m pytest -q -ra -o addopts=''
openalex-build-web-data verify data/artifacts/web/topic_explorer
openalex-paper-discovery build
openalex-paper-discovery verify
streamlit run dashboard/app.py --server.address 127.0.0.1
```

Run plain `git lfs pull` for complete retained-artifact verification. The
original immutable collection, processed tables, Phase 4 run, Phase 5 audit,
Phase 6 run, integrated ML tables, final model and web package have distinct
manifests and verifiers. Their exact current paths are in
[PROJECT_HANDOFF.md](../PROJECT_HANDOFF.md), the
[Phase 6 map](../reports/phase6/artifact_map.json), and
[artifact contract](MODEL_AND_DATA_ARTIFACTS.md). The five historical Phase 6
experiment identities (plus the RQ6 publication manifest) have been migrated into `data/analysis/phase6/` with immutable
original manifest bytes and an explicit old-to-new map; use
`openalex-verify-phase6` to check both provenance and canonical artifacts.
Other versioned analysis runs retain their original locations. For full checks
use the existing CLI `--help` and relevant phase reports, not a rerun of collection.

Active application paths are declared once in
[`config/application.yaml`](../config/application.yaml). The old web/model
run-named paths and three historical config names are symlinks to byte-identical
canonical files, so historical manifest hashes remain valid. The symbolic
links require a Git checkout with symlink support; Ubuntu/Linux is the tested
environment. Do not copy just the link without its target. The Paper Discovery
index remains rebuildable and ignored at `data/artifacts/web/paper_discovery/`.

The original collection and preprocessing manifests contain historical
absolute paths. Their read-only verifiers map each recorded project path into
the **current checkout** and still require the original SHA-256. The original
interim JSONL was retired from the current tree; the recorded raw and interim
JSONL SHA-256 values are identical. A missing interim file is therefore
verified against the retained raw JSONL **only when both declared hashes and
the actual bytes agree**. The CLI reports
`verified_identical_raw_fallback`; it does not claim an independently restored
interim file. A present but corrupted interim file fails, without fallback.

```bash
openalex-verify-collection data/raw/openalex_stratified/stratified_20261019T155909Z/manifest.json
openalex-validate-processed --output-dir data/processed/openalex_stratified/stratified_20261019T155909Z --plan data/metadata/phase2_sampling_plan.json --population data/metadata/population_counts_pre_phase2.json --config config/topics.yaml
openalex-validate-phase4 data/analysis/phase4_stratified_20261019T155909Z_v3
openalex-verify-phase6
openalex-verify-topic-run --run-dir data/analysis/phase6/validation
openalex-verify-final-ml data/analysis/finalization_p3_models_20261101_v1
openalex-build-web-data verify data/artifacts/web/topic_explorer
```

The model service validates its manifest and inference-code compatibility
before loading trusted local `joblib`; an arbitrary external pickle/joblib is
unsafe even if it has an internally consistent checksum. An authorized
separate transfer can use `openalex-restore-local-artifact` as documented in
the artifact contract; the local copy still requires an approved source and
manifest authentication. GitHub availability is not a redistribution-rights
assessment. Historical 2025 labels and reviewer keys were published, so this
snapshot cannot support an independent sealed-test claim.

`python deliverables/generate.py` regenerates editable DOCX/PPTX from tracked
source Markdown and figures; PDF rendering also requires LibreOffice and
appropriate fonts. Inspect rendered pages, not just the source files. A
localhost health check can use `curl --fail
http://127.0.0.1:8501/_stcore/health` after starting Streamlit; health alone
does not establish page-level or responsive UI correctness. Optional browser
tests require the browser extra and `AI_TRENDS_RUN_BROWSER_TESTS=1`.

`.env` is only for authorized new OpenAlex requests. Never print or commit API
keys. The [retention policy](archive/REPOSITORY_CLEANUP.md) explains which old runs
were removed from the current tree; their commits still exist in history.
