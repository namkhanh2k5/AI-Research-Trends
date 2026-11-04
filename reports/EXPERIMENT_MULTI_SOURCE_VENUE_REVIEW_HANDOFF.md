# Independent Review Handoff — Venue Experiment

Branch: `experiment/venue-discovery-data-poc`; base/current report-generation HEAD: `31b7dd02d42fd9ebc3e67e60291f149dc27f6b95`. The final pushed SHA must be checked in GitHub after delivery. Source manifests and row-level outputs are local only at `data/analysis/venue_discovery_experiment/venue_poc_20261104_v1`; they are intentionally Git-ignored and cannot be reconstructed by cloning alone without restoring the original local Phase 2/3 artifacts.

Input SHA-256: original raw `b8734cd3da2cba8c2c9ff8a9742d46d62585e55604f18630274f6bb8fbc178af`; expansion raw `cc946d6970cbfbafcfe58b236699f2f27772545865f68b5b693872f87ef87126`. Experiment manifest: `data/analysis/venue_discovery_experiment/venue_poc_20261104_v1/experiment_manifest.json`. Canonical venue table: 3,230 rows; one-per-Work paper links: 11,506 rows. Crossref main: 289 valid, 210 404, one DOI mismatch; retraction: 100 valid DOI responses. RQ7 paired cohort: 502 source records; venue IDs 250→251. RQ8: 1843 2024 queries, 592 candidates, oracle ceiling 35.4%, V3 Recall@5 12.3%, MRR@10 0.073. Full details are in the six experiment reports and local manifest.

Validation: 231 offline tests passed, 9 intentionally skipped; `pip check` clean. Original Phase 2, expansion, integrated data, Phase 4 outputs and frozen ML experiments passed their read-only verifiers. The experiment verifier checks input, output, figure and code hashes. No 2025 final-test labels were read.

Reproduction (requires private local artifacts; **do not repeat API collection unless needed**):

```bash
python -m ai_research_trends.experiments.venue_inventory --output-dir data/analysis/venue_discovery_experiment/new_run --doi-limit 500
python -m ai_research_trends.experiments.venue_enrichment crossref --selection data/analysis/venue_discovery_experiment/new_run/crossref_selection.parquet --output-dir data/analysis/venue_discovery_experiment/new_run/crossref --cap 600
python -m ai_research_trends.experiments.venue_retraction --output-dir data/analysis/venue_discovery_experiment/new_run/retractions
python -m ai_research_trends.experiments.venue_verify data/analysis/venue_discovery_experiment/venue_poc_20261104_v1
pytest -q -ra -o addopts=''
python -m pip check
```

The two collection commands above are dry runs without `--execute`. To inspect completed evidence instead, verify all SHA-256 entries in `experiment_manifest.json` and provider checkpoint manifests. Findings are development-only; neither human correctness nor 2025 final-test evaluation was performed. Verdict: RQ7 CONDITIONAL GO; RQ8 journal-only CONDITIONAL GO, general venue recommender NO-GO.
