# Frozen 2024 development error diagnostics

This audit is read-only over the **681 original-sample, in-catalogue 2024 development works** and the checksum-verified expanded Linear SVM. It does not inspect the 2025 final test. Local aggregate-only output is `data/analysis/finalization_p3_diagnostics_20261101_v3/`; its manifest records hashes of the code, closed run, integrated split and original-sample `work_topics.parquet`. No record title, abstract, or Work ID is published here.

The model disagreed with the OpenAlex primary-topic silver label on **82/681 (12.04%)** works. Errors concentrate at low maximum SVM margin, but the margin is not a probability:

| Maximum-margin quartile | Works | Errors | Error rate |
|---|---:|---:|---:|
| Q1, lowest | 171 | 57 | 33.33% |
| Q2 | 170 | 16 | 9.41% |
| Q3 | 170 | 8 | 4.71% |
| Q4, highest | 170 | 1 | 0.59% |

Abstract-length quartiles gave **25/171 (14.62%)**, **21/170 (12.35%)**, **15/170 (8.82%)**, and **21/170 (12.35%)** errors from shortest to longest; length is not monotonic with correctness. By work type: article **44/450 (9.78%)**, preprint **37/228 (16.23%)**, review **1/3** (too small to interpret). English-language records had **75/652 (11.50%)** disagreements; other/missing-language records **7/29 (24.14%)**, also imprecise due small support. These are descriptive development strata, not causal effects or validated subgroup fairness claims.

For **48/82** disagreements, the SVM-predicted topic appears among the work's *secondary OpenAlex topics* in the original Phase 3 `work_topics` bridge. This does **not** prove the model was semantically correct: it indicates that a single primary-topic metric can penalize a plausible alternate native membership. OpenAlex topic scores are not independent human adjudication. Largest directed confusions remain T10181→T10028 (7), T10028→T10181 (7), and T10036→T10052 (7), consistent with catalogue overlap that deserves human review.

Relative to original-only SVM predictions on the **same works**, expansion changed **36** original-wrong cases to right and **19** original-right cases to wrong; **63** were wrong under both. This is a net improvement, not uniform benefit. Paired 500-resample 95% intervals for expanded SVM macro-F1 difference are **[0.0042, 0.0419]** versus expanded Logistic Regression and **[0.0051, 0.0408]** versus expanded ComplementNB. These intervals do not include uncertainty in OpenAlex labels or sample selection.

Year-specific validation differences cannot be estimated from this **single 2024 development year** without opening the sealed 2025 test or changing the declared design. Training-year composition is described separately; it is not a substitute for per-year validation. Most errors are low-margin, but high-margin disagreements exist. Even a high-margin suggestion requires user confirmation.

Reproduce with `openalex-final-ml-diagnostics --closed-run data/analysis/finalization_p3_models_20261101_v1 --output-dir data/analysis/finalization_p3_diagnostics_rebuild_v1` using local Git-ignored inputs and an unused destination. The CLI preserves aggregate-only outputs and an immutable manifest.
