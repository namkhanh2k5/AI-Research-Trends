# Final reproducibility guide

The reproducible chain is: OpenAlex verified aggregation and collection → Phase 3 normalized Parquet → Phase 4 analytical outputs → targeted ML integration and frozen development evaluation → Phase 2 finalization web data → Phase 3 finalization model bundle → Phase 4 finalization Streamlit UI. Each prior phase has its own manifest, checksum verifier, CLI, report and precise commands. **Do not rerun acquisition merely to start the website.**

On the machine with the ignored local artifacts, from repository root:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,web,deliverables]"
openalex-build-web-data verify data/analysis/finalization_p2_web_data_20261101_v3
openalex-verify-final-ml data/analysis/finalization_p3_models_20261101_v1
pytest -q -ra
pip check
streamlit run dashboard/app.py --server.address 127.0.0.1
python deliverables/generate.py
```

The report Markdown is source of truth for generated DOCX/PDF. The slide generator uses the published tracked figures. Verify output files with `pdfinfo` and inspect rendered pages. The local LibreOffice installation may need an isolated profile; the generated DOCX/PPTX remain valid if conversion is temporarily blocked.

Science boundaries: 2025 ML test remains sealed; the frozen config says execution is false. Human ratings are absent until actual reviewers submit them. Development metrics must not be promoted to final-test metrics. Exact OpenAlex snapshot counts can change if upstream records change; use the checked-in reports and local manifest for this study rather than silently refreshing science during presentation.
