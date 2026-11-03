# Development setup (Ubuntu/Linux)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,web,deliverables,browser]"
pip check
pytest -q -ra
openalex-build-web-data verify data/analysis/finalization_p2_web_data_20261101_v3
openalex-verify-final-ml data/analysis/finalization_p3_models_20261101_v1
streamlit run dashboard/app.py --server.address 127.0.0.1
```

The verified local data/model paths are defaults; set `AI_TRENDS_WEB_DATA` and `AI_TRENDS_MODEL` for other versioned packages. These paths are **not** in Git. A clean public clone can run fixture-based tests but cannot display the real app until private artifacts are rebuilt or transferred under an approved policy. The model loader demands compatible hashes. Do not make it point at an arbitrary downloaded joblib.

For an authorized separate checkout, use the checksum-verified `openalex-restore-local-artifact` workflow in [MODEL_AND_DATA_ARTIFACTS.md](MODEL_AND_DATA_ARTIFACTS.md). This requires access to the original approved packages. Chrome browser checks are opt-in: start Streamlit on port 8501 and run `AI_TRENDS_RUN_BROWSER_TESTS=1 pytest -q tests/browser/test_live_app.py`; screenshots are written under ignored `data/analysis/finalization_p4_1_browser_evidence/`. AppTest is not a substitute for actual Chrome inspection.

For reviewer A or B, run the separate localhost process as in `WEB_USER_GUIDE.md`. For academic files, run `python deliverables/generate.py`; this requires `python-docx`, `python-pptx`, LibreOffice and the tracked figure files. The generator reads the Markdown source; DOCX/PPTX are editable outputs, PDF are rendered derivatives. The report page count depends on installed fonts and paper size.

For a smoke test, run `streamlit run dashboard/app.py --server.headless true --server.port 8501 --server.address 127.0.0.1`, then `curl --fail http://127.0.0.1:8501/_stcore/health`. A successful health response confirms a running server, not that every data page has been visually reviewed. Use the UI and automated AppTest to inspect interactions.
