# Finalization Phase 3 — supervised topic placement (development results)

## 1. Executive summary

The frozen 14-topic task is technically viable as **assisted** placement, but not as autonomous classification. On 681 original-sample, in-catalogue 2024 development works, the expanded-training Linear SVM attained macro-F1 **0.8808** against OpenAlex primary-topic silver labels. On a separate 2024 open-set evaluation (1,105 eligible works), its rejection rule accepted **21.66%** of out-of-catalogue works despite a ≤20% calibration target. Human semantic review has not been submitted, and the 2025 final test remains **sealed**. The decision is **CONDITIONAL GO** for a human-confirmed Phase 4 prototype, not a validated deployment.

## 2. Research task

Input is a draft title and abstract; output is a ranked suggestion among a frozen catalogue of 14 OpenAlex topics, a rejection/confirmation state, and a linked Topic Brief. The model predicts agreement with OpenAlex's *primary topic*, not an independently adjudicated scientific truth or paper quality. Topics outside the catalogue must be handled explicitly.

## 3. Sources and scope

The verified integrated dataset is `data/processed/ml_topic_classification/finalization_p2_20261101_v3/` (split-manifest SHA-256 `7feee5f38bb98a33ec3fbd936e9a197a5caa08b2a1559719c9e316201c44a2c5`). It contains 14,515 records: original Phase 2 sample plus targeted training-side expansion, 14,470 version groups. Training is 2020–2023 (7,002 eligible records, of which 3,355 are in the catalogue); 2024 development validation has 1,843 original-sample records (681 in the catalogue, 1,162 outside). The 2025 sealed test has 2,318 records and was **not read for model selection, calibration, or this report**. Catalogue and topic metadata hashes are frozen in `config/finalization_p3_frozen_evaluation.yaml`. The expanded data are **not** used to estimate publication prevalence.

## 4. Expansion ablation

Among the 3,355 selected training rows, 1,717 came from the original sample and 1,638 from targeted expansion. On the same 681 validation rows, Linear SVM macro-F1 rose from **0.8506** to **0.8808** (+0.0302, model-specific tuning); a fixed-C=1 comparison gave **0.8501** to **0.8808**. A 500-draw paired bootstrap for expanded minus original SVM gave macro-F1 difference 95% interval **[0.0084, 0.0527]**. The learning-curve points were 0.8501 (0 added), 0.8773 (548), 0.8708 (1,090), and 0.8808 (1,638): improvement is observed overall but not monotonic. See [expansion audit](FINALIZATION_P3_DATA_EXPANSION_ABLATION.md) and [training-support figure](figures/finalization_p3/training_support.png).

## 5. Features

Only cleaned title and abstract text enters the learner. Word TF-IDF uses unigrams/bigrams, `min_df=2`, `max_features=50000`, and `sublinear_tf=True`, fitted **inside** each training fold. No citation, journal, publication year, ID, or OpenAlex label is an input feature. For SVM, title-only macro-F1 was **0.7331**, abstract-only **0.8769**, combined **0.8808** on the same 2024 group. These are development comparisons, not a search for a final-test optimum.

## 6. Model selection and tuning

Three supervised models were tuned with three-fold `StratifiedGroupKFold` on historical training records only: ComplementNB (alpha 0.5/1/2), Logistic Regression (C 0.3/1/3), and Linear SVM (C 0.3/1/3). Version groups are kept together; the 2024 group is not a tuning fold. The champion rule was declared before experiments: highest expanded-data macro-F1; within 0.01, lower open-set outside false acceptance and latency. Linear SVM with **C=1** won on closed-set macro-F1. See [model-selection record](FINALIZATION_P3_MODEL_SELECTION.md).

## 7. Baselines and supervised comparison

All values below use the **same 681 in-catalogue 2024 original-sample works** and OpenAlex silver labels.

| Method | Original-only macro-F1 | Expanded macro-F1 | Expanded accuracy |
|---|---:|---:|---:|
| Majority class | — | 0.0248 | 0.2100 |
| Official-description TF-IDF match | — | 0.5522 | 0.5742 |
| ComplementNB | 0.7652 | 0.8580 | 0.8532 |
| Logistic Regression | 0.7710 | 0.8580 | 0.8649 |
| Linear SVM | 0.8506 | **0.8808** | **0.8796** |

The description baseline uses only official topic descriptions and is not a supervised learner. Paired 500-resample intervals for expanded SVM macro-F1 minus expanded LR and NB are **[0.0042, 0.0419]** and **[0.0051, 0.0408]**, respectively; they do not account for silver-label error or sampling uncertainty. See [model comparison](FINALIZATION_P3_MODEL_COMPARISON.md) and [figure](figures/finalization_p3/model_comparison.png).

## 8. Per-class evaluation

The champion's weakest measured classes included T10181 (36 validation works, F1 **0.7042**), T10028 (84, **0.8000**), and T10331 (22, **0.8182**). These class supports are small; uncertainty and semantic ambiguity matter. Full per-class metrics are in the ignored, checksum-verified local `per_class.csv` and [per-class figure](figures/finalization_p3/per_class_f1.png).

## 9. Error analysis

The SVM disagreed with the OpenAlex primary label for **82/681** works. Its lowest-margin quartile had **57/171** disagreements, versus **1/170** in the highest; margins are not probabilities. Among the 82 disagreements, **48** predicted topics also appear as an OpenAlex secondary topic, suggesting single-label ambiguity but not proving semantic correctness. Largest directed confusions include T10181→T10028 (7), T10028→T10181 (7), and T10036→T10052 (7); the [confusion matrix](figures/finalization_p3/confusion.png) shows the full pattern. Expansion corrected 36 previously wrong cases but made 19 previously right cases wrong; T10036 and T10028 recall declined. Abstract-length quartile error rates were not monotonic, and preprints showed 37/228 disagreements versus articles 44/450; no causal or subgroup-fairness conclusion follows. Full aggregate evidence is in the [error diagnostics](FINALIZATION_P3_ERROR_DIAGNOSTICS.md). Dominant SVM terms are association diagnostics, not causal explanations of the OpenAlex labels.

## 10. Sampling bias and generalization

Expansion was targeted to catalogue topics and historical years. It changes training composition and cannot establish improvement for other topics, future years, or the global AI population. The original 2024 validation is held fixed to make the ablation comparable. Grouping by version family reduces duplicate leakage; residual near-duplicates and label drift remain possible. The fixed-parameter ablation is the cleaner estimate of data addition, but still reflects this chosen targeted addition and one development set. Year-specific **validation** performance cannot be estimated from only the 2024 development year without opening the sealed 2025 test.

## 11. Open-set rejection and abstention

The 2024 original-sample development set was divided by version group into **738 calibration** and **1,105 evaluation** records; the evaluation group contains 408 in-catalogue and 697 outside. A threshold was chosen on calibration only to target ≤20% outside false acceptance. For the selected SVM, the frozen raw-margin threshold is **−0.22227267687798036** (not a probability); on evaluation, in-catalogue acceptance was **0.8309**, outside false acceptance **0.2166**, AUROC **0.8919**, and correct accepted placements / all eligible **0.2833**. The outside false-acceptance 500-draw bootstrap interval was approximately **[0.188, 0.246]**. The target was **not met** on the held-out development group. A separate explicit-OTHER LR scored better on some open-set measures (AUROC 0.9473, outside false acceptance 0.1750), but was exploratory relative to the predeclared champion rule. See [open-set report](FINALIZATION_P3_OPEN_SET_EVALUATION.md) and [ROC figure](figures/finalization_p3/open_set_roc.png).

## 12. Human semantic validation

The Phase 2 human-review package exists, but no two independent real-rater submissions were available at execution. No inter-rater agreement, semantic accuracy, or catalogue-adequacy claim is made. See [human-validation status](FINALIZATION_P3_HUMAN_VALIDATION_STATUS.md).

## 13. Final 2025 test

**SEALED / not evaluated.** `config/finalization_p3_frozen_evaluation.yaml` explicitly has `allow_final_test_execution: false`. The one-time command checks a documented human-approval gate before opening the test table. There are no 2025 predictions or results in this branch. See [final-test status](FINALIZATION_P3_FINAL_TEST_STATUS.md).

## 14. Inference architecture

The trusted local bundle `models/finalization_p3/topic_placement_v2/` contains the selected pipeline, topic catalogue, frozen threshold/configuration, and SHA-256 manifest. A loader checks artifact hashes and source compatibility before deserialization. Every suggestion requires user confirmation; no automatic placement is enabled. A blank/very short abstract is rejected explicitly. The model binary is intentionally Git-ignored; reviewers must rebuild it from verified local data. See [inference integration](FINALIZATION_P3_INFERENCE_INTEGRATION.md).

## 15. Topic Brief integration

`TopicPlacementService.explore_research_draft` reuses the Phase 2 `ResearchData` interface for verified topic briefs, population publication trends, sampled citation context, and OA context. A model suggestion only previews a brief; a manually selected catalogue topic remains available even when the model abstains. Research context continues to distinguish population aggregates from the original 12,000-work detailed sample. Training expansion is excluded from that landscape context.

## 16. Scientific limitations

OpenAlex primary-topic labels are generated silver labels, not human ground truth. Only fourteen topics are supported. The selected model's development false-acceptance rate exceeded the calibration target. All metrics are from one historical split and one original-sample 2024 development cohort, not a final independent 2025 test. Abstention scores are model margins or probabilities, not proof of true topic membership. Missing title/abstract records are outside the model-ready denominator. Human review and deployment security remain open.

## 17. Technical decision

**CONDITIONAL GO for a research-prototype Phase 4 website with assisted, confirmable suggestions only.** Do not label the system a validated autonomous topic classifier. A stronger open-set policy may be considered after independent human evaluation and a new, documented development decision; do not silently replace the frozen 2025 procedure.

## 18. Phase 4 handoff

Build the accessible interface around the service contract, display rank/margin and limitations, require explicit topic confirmation, show Topic Brief source scope, and keep the model binary local or distributed via a separately approved mechanism. Obtain genuine human ratings and an independent scope decision before enabling one-time 2025 evaluation. See the [reviewer handoff](FINALIZATION_P3_PHASE4_HANDOFF.md).
