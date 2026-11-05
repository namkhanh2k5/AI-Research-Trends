# Finalization Phase 4 — deployment status

**Local/private:** PASS. The site starts with `streamlit run dashboard/app.py --server.address 127.0.0.1 --server.port 8501`; a real local HTTP health check returned 200 and `ok`. The owning server process was stopped after testing. The six pages also passed programmatic Streamlit navigation tests using local verified artifacts.

**Public hosting:** NOT DONE. GitHub includes source, published figures and final written deliverables, but deliberately excludes the 12,000-paper web index, model binary, raw/interim/processed data, human ratings and sealed test. A public app cannot be built solely from this repository. Redistributing the model and metadata/abstract package requires rights/privacy and artifact governance review; exposing the blind-reviewer UI publicly would be inappropriate. No public URL, uptime, external security or accessibility certification is claimed.

The intended deployment procedure is in `docs/DEPLOYMENT_GUIDE.md`. Run verifiers before a private release and keep all artifacts outside static web roots. The app makes no OpenAlex API requests at runtime. There is no automatic refresh or 2025 test execution.
