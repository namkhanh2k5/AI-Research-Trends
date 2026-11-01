# Phase 3 → Phase 4 reviewer handoff

## Decision and provenance

**CONDITIONAL GO** to a human-confirmed prototype; no autonomous topic assignment. Branch: `feature/finalization-p3-final-ml` (commit SHA is the branch HEAD after delivery). Integrated source: `data/processed/ml_topic_classification/finalization_p2_20261101_v3/`, split-manifest SHA-256 `7feee5f38bb98a33ec3fbd936e9a197a5caa08b2a1559719c9e316201c44a2c5`; catalogue: frozen Phase 6B, 14 topics. The source data, local model binary, record-level predictions and private human-review files are **not** committed.

## Verified development results

- Historical training: 1,717 original-sample plus 1,638 targeted-expansion selected-topic works. Original 2024 in-catalogue validation: 681; all eligible 2024: 1,843.
- Closed-set macro-F1 on the same 681: majority 0.0248; topic-description match 0.5522; expanded ComplementNB 0.8580; expanded Logistic Regression 0.8580; expanded Linear SVM **0.8808**. Original-only Linear SVM 0.8506; fixed-C comparison 0.8501→0.8808.
- Open-set 2024 split: calibration 738; evaluation 1,105 (408 in/697 out). Selected SVM at frozen margin −0.22227267687798036: in acceptance 0.8309; outside false acceptance **0.2166**; AUROC 0.8919; end-to-end correct accepted placement 0.2833. The 20% calibration target was not achieved on evaluation.
- Exploratory explicit-OTHER LR yielded outside false acceptance 0.1750 and end-to-end 0.3023 on the same 2024 evaluation cohort; it was **not** silently substituted for the predeclared champion.
- Human semantic validation: **PENDING**. 2025 test: **SEALED**.

## Model and service

Champion: expanded Linear SVM, C=1; bundle `models/finalization_p3/topic_placement_v2/`, model binary SHA-256 `b066ba80ab0768052f585fa1ed2e6b56c24f46c511508b3394580452e40bb788`, bundle manifest SHA-256 `fb78307f219c933e35151a905ca327e00a058ec4cca3c99f294d41b0ab93907d`. The binary is Git-ignored and is reproducible only when the local Phase 2 data are available. Use `openalex-package-topic-model infer --help` for a command-line smoke test, or call `TopicPlacementService(...).explore_research_draft(...)` from the future UI. The service previews verified Topic Brief content via `ResearchData`; it always requires user confirmation.

## Evidence classes

**Verified:** local source and result manifests/checksums, 2024 silver-label metrics, 2024 calibration/evaluation disjointness, local inference smoke, original population/sample separation. **Interpretation:** targeted expansion improves aggregate silver-label agreement on this development cohort, while abstention remains imperfect. **Unresolved:** true semantic correctness, representativeness for arbitrary user drafts, final 2025 generalization, deployment-safe model distribution, and actual user usability.

## Reviewer commands and remaining web tasks

```bash
openalex-verify-integrated-topics data/processed/ml_topic_classification/finalization_p2_20261101_v3
openalex-verify-final-ml data/analysis/finalization_p3_models_20261101_v1
openalex-verify-final-ml data/analysis/finalization_p3_open_set_20261101_v1
pytest -q -ra
python -m pip check
```

Execution on the local verified workspace: `pytest -o addopts='' -q -ra` **189 passed, 1 opt-in live OpenAlex test skipped**; `python -m pip check` **No broken requirements found**; all six new console scripts returned `--help` successfully. The closed-run verifier checked **14/14** output files, the open-run verifier **23/23**. A second independent closed run reproduced metrics, ablation, learning-curve, feature-ablation and per-class results exactly; its model binaries remain local. Nine published development PNGs total **602,622 bytes**, and each matches its figure manifest SHA-256. A real 2024 inference smoke covered a confident in-catalogue suggestion, out-of-catalogue abstention, an intermediate-score case, manual selection, invalid abstract and missing brief; the last two raised `ValueError` and `KeyError` as intended. No live OpenAlex request was required.

The UI must display the 14-topic scope, the non-probability SVM margin, abstention status, model version, limitations, and a manual confirmation control. It should separate population-trend charts from original-sample context and never include targeted expansion in publication estimates. Human rating submission, independent scope review, a reviewed 2025 gate decision, and secure model-artifact delivery remain external tasks. Full measured results and charts: [main report](FINALIZATION_P3_FINAL_ML_REPORT.md), [open-set report](FINALIZATION_P3_OPEN_SET_EVALUATION.md).
