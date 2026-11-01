# Targeted training expansion: matched 2024 ablation

The source is the validated 2020–2023 integrated training split. Of 7,002 eligible records, 3,355 carry one of the frozen 14 primary-topic silver labels: 1,717 original-sample and 1,638 targeted-expansion records. The evaluation set is fixed at 681 in-catalogue, original-sample 2024 works. Expansion is training-only and is not a prevalence sample.

| Model | Original-only macro-F1 | Expanded macro-F1 | Change | Paired 500-draw 95% interval for change |
|---|---:|---:|---:|---:|
| ComplementNB | 0.7652 | 0.8580 | +0.0928 | [0.0602, 0.1286] |
| Logistic Regression | 0.7710 | 0.8580 | +0.0870 | [0.0582, 0.1219] |
| Linear SVM | 0.8506 | 0.8808 | +0.0302 | [0.0084, 0.0527] |

These comparisons independently retuned each training source using historical group-aware CV. Holding the final SVM hyperparameter fixed at C=1 yields macro-F1 **0.8501** (original) versus **0.8808** (expanded), which isolates the addition from a parameter change more closely. At fixed C, cumulative targeted additions of 0, 548, 1,090, and 1,638 works gave macro-F1 0.8501, 0.8773, 0.8708, and 0.8808. The non-monotonic sequence does not support extrapolation beyond the observed sample.

The expansion improves aggregate agreement with OpenAlex labels, but class-level outcomes differ. T11307 and T10181 recall improved, whereas T10036 and T10028 recall declined. Targeted acquisition favors selected classes and may amplify OpenAlex label conventions. It is not evidence that all AI research topics benefit, and it must never enter population-trend denominators. Figures: [support](figures/finalization_p3/training_support.png), [learning curve](figures/finalization_p3/learning_curve.png).

Reproduce locally with `openalex-final-ml --output-dir data/analysis/<new-immutable-run>` after verifying the integrated Phase 2 manifest. Source predictions and model binaries are Git-ignored; aggregate metrics are in the [main report](FINALIZATION_P3_FINAL_ML_REPORT.md).
