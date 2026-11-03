# Finalization Phase 3 handoff

**Gate: conditional GO.** The engineering dataset is ready; independent semantic validation is pending. The local integrated run is `data/processed/ml_topic_classification/finalization_p2_20261101_v3/`. Train and validation data are respectively `train.parquet` (7,002) and `validation_2024.parquet` (1,843). `test_2025_sealed.parquet` (2,318) must not be loaded for fitting, feature tuning, threshold choice, error analysis or catalogue revision. General tables mask its labels. All local data and human-review materials are Git-ignored; do not expect them on GitHub.

Verify before model work:

```bash
openalex-verify-integrated-topics data/processed/ml_topic_classification/finalization_p2_20261101_v3 --compare-dir data/processed/ml_topic_classification/finalization_p2_20261101_v3_rerun
openalex-verify-rq6 data/analysis/finalization_p2_rq6_20261101_v3 --published-dir reports/finalization_p2
openalex-prepare-human-review verify data/analysis/finalization_p2_human_review_20261101_v1
openalex-topic-population verify data/analysis/finalization_p2_topic_population_20261101_v2
openalex-build-web-data verify data/analysis/finalization_p2_web_data_20261101_v3
openalex-bind-finalization-p2 verify data/analysis/finalization_p2_master_20261101_v1.json
pytest -q -ra
pip check
```

Train a simple TF-IDF + logistic/linear SVM baseline first on usable training text. Evaluate only on the 2024 split; include outside-catalogue/abstention handling, per-class precision/recall, calibration and confusion. Use group-safe cross-validation within train if tuning; preserve Work-ID/DOI/title version groups. Compare 3–4 credible models only if the baseline and course schedule justify it. Record exact feature sources, missing-text exclusions, fixed random seeds, validation choice and fit time. Never report OpenAlex-label agreement as independent semantic correctness. The targeted 2,515-work expansion is training-only; do not use its class proportions as population prevalence.

Two independent human raters must complete the private 40-example calibration and 100-example evaluation packages. The review protocol and locked answer keys are described in [the human-review handoff](../docs/FINALIZATION_P2_HUMAN_REVIEW.md). If they identify a fundamental scope error, version the catalogue and retrain/revalidate **before** the final 2025 test is opened. The final website should consume the verified [web data contract](../docs/FINALIZATION_P2_WEB_DATA_CONTRACT.md) and attach a model-inference service later; keep original-sample research statistics separate from the ML training pool.

The 14-topic OpenAlex population aggregates were retrieved on 2026-11-01, later than the original Phase 4 population snapshot. Any comparison across snapshots must disclose this difference and possible topic-classifier drift. No new OpenAlex call is required to run the prepared local web query functions.
