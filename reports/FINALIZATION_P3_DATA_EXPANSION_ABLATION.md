# Targeted training expansion: matched 2024 ablation

The source is the validated 2020–2023 integrated training split. Of 7,002 eligible records, 3,355 carry one of the frozen 14 primary-topic silver labels: 1,717 original-sample and 1,638 targeted-expansion records. The evaluation set is fixed at 681 in-catalogue, original-sample 2024 works. Expansion is training-only and is not a prevalence sample.

| Model | Original-only macro-F1 | Expanded macro-F1 | Change | Paired 500-draw 95% interval for change |
|---|---:|---:|---:|---:|
| ComplementNB | 0.7652 | 0.8580 | +0.0928 | [0.0602, 0.1286] |
| Logistic Regression | 0.7710 | 0.8580 | +0.0870 | [0.0582, 0.1219] |
| Linear SVM | 0.8506 | 0.8808 | +0.0302 | [0.0084, 0.0527] |

These comparisons independently retuned each training source using historical group-aware CV. Holding the final SVM hyperparameter fixed at C=1 yields macro-F1 **0.8501** (original) versus **0.8808** (expanded), which isolates the addition from a parameter change more closely. At fixed C, cumulative targeted additions of 0, 548, 1,090, and 1,638 works gave macro-F1 0.8501, 0.8773, 0.8708, and 0.8808. The non-monotonic sequence does not support extrapolation beyond the observed sample.

The expansion improves aggregate agreement with OpenAlex labels, but class-level outcomes differ. T11307 and T10181 recall improved, whereas T10036 and T10028 recall declined. Targeted acquisition favors selected classes and may amplify OpenAlex label conventions. It is not evidence that all AI research topics benefit, and it must never enter population-trend denominators. Figures: [support](figures/finalization_p3/training_support.png), [learning curve](figures/finalization_p3/learning_curve.png).

The following descriptive composition uses **all eligible 2020–2023 model-ready rows**, not just the 14-class subset. Counts come from the frozen training-run manifest and demonstrate why the targeted addition cannot be treated as representative:

| Source | Eligible rows | Selected-topic rows | 2020 / 2021 / 2022 / 2023 | Article / preprint / review | English / all | Mean abstract words |
|---|---:|---:|---|---|---:|---:|
| Original analytical sample | 5,055 | 1,717 | 1,099 / 1,225 / 1,250 / 1,481 | 3,818 / 1,210 / 27 | 4,680 / 5,055 | 183.55 |
| Targeted training expansion | 1,947 | 1,638 | 410 / 465 / 488 / 584 | 1,244 / 685 / 18 | 1,854 / 1,947 | 184.62 |

The expansion has a much larger fraction of in-catalogue labels and more preprints proportionally. No population or inclusion weights are inferred. In the paired same-paper SVM comparison, expansion corrected **36** original-only errors but introduced **19** new errors, as measured in the [aggregate error audit](FINALIZATION_P3_ERROR_DIAGNOSTICS.md).

Reproduce locally with `openalex-final-ml --output-dir data/analysis/<new-immutable-run>` after verifying the integrated Phase 2 manifest. Source predictions and model binaries are Git-ignored; aggregate metrics are in the [main report](FINALIZATION_P3_FINAL_ML_REPORT.md).
