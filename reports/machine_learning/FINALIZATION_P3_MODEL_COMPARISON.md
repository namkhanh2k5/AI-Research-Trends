# Supervised model and baseline comparison

All closed-set numbers use **the same 681 original-sample 2024 works** whose OpenAlex primary topic belongs to the frozen 14-topic catalogue. Training is historical 2020–2023 only. Labels are OpenAlex-generated silver labels.

| Method | Original-only macro-F1 | Expanded macro-F1 | Expanded accuracy | Expanded weighted-F1 |
|---|---:|---:|---:|---:|
| Majority class | — | 0.0248 | 0.2100 | 0.0729 |
| Topic-description TF-IDF cosine | — | 0.5522 | 0.5742 | 0.5770 |
| ComplementNB | 0.7652 | 0.8580 | 0.8532 | 0.8520 |
| Logistic Regression | 0.7710 | 0.8580 | 0.8649 | 0.8652 |
| Linear SVM | 0.8506 | **0.8808** | **0.8796** | **0.8796** |

The official-description baseline is label-description retrieval, not supervised training. The Linear SVM is the strongest closed-set learner under the predeclared Macro-F1 rule. The paired 500-resample interval for expanded minus original SVM Macro-F1 is **[0.0084, 0.0527]**; individual resample intervals are expanded **[0.8514, 0.9037]** and original **[0.8192, 0.8768]**. On the same works, paired expanded-SVM minus expanded-LR and expanded-NB intervals are **[0.0042, 0.0419]** and **[0.0051, 0.0408]**. These bootstrap intervals quantify paper-level resampling variation on this fixed development cohort, not uncertainty from OpenAlex sampling, topic-label error, or future years. See the [aggregate error diagnostics](FINALIZATION_P3_ERROR_DIAGNOSTICS.md).

The three supervised families use a TF-IDF pipeline whose vocabulary is fitted within historical group-aware CV folds. Their grids and selection rule were frozen in [the experiment protocol](../../docs/protocols/FINALIZATION_P3_ML_EXPERIMENT_PROTOCOL.md). The 2025 test remains sealed. [Comparison chart](../figures/finalization_p3/model_comparison.png) and [per-class chart](../figures/finalization_p3/per_class_f1.png).
