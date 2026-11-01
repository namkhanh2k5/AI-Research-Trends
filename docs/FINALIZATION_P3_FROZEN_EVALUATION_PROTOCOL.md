# Frozen development configuration; final 2025 test still sealed

This document and [`config/finalization_p3_frozen_evaluation.yaml`](../config/finalization_p3_frozen_evaluation.yaml) record the selected development model **before** any 2025 predictions or label inspection. The model is TF-IDF word unigrams/bigrams + LinearSVC (`C=1`, seed 20251019), trained on the 2020–2023 integrated historical rows only. The fourteen OpenAlex primary-topic silver labels and class order are frozen in the machine-readable configuration. The 2024 original-sample data were used for development model comparison and a group-isolated 40% calibration / 60% open-set evaluation; no 2024 rows were used to refit the packaged model. This preserves the fitted model and threshold already evaluated rather than silently changing training conditions before final assessment.

The score is a **raw multiclass SVM decision margin, not a probability**. The rejection threshold is `-0.22227267687798036`, selected as the lowest 2024-calibration score meeting an outside-catalogue false-acceptance target of ≤20% *on calibration*. On the disjoint 2024 evaluation subset it yielded 21.7% outside false acceptance; no threshold was changed after that result. The product therefore provides **assisted suggestions only**, always requiring user confirmation. The lower suggestion-strength boundary is `-0.516798309254057` (calibration score 25th percentile capped at the rejection threshold). These statuses express model score strength, not semantic certainty.

Closed-set final-test denominator, if ever authorized, is 2025 eligible works whose OpenAlex primary topic belongs to the frozen catalogue. Open-set denominator is **all** eligible 2025 works. Required metrics and exact SHA-256 hashes are frozen in the YAML file. The future one-time evaluator must verify the input, model, catalogue and reviewer-gate hashes, then write to a new immutable local output directory. Never retune after inspecting final-test results.

`FINAL_TEST_STATUS: SEALED`. There are no two genuine independent human ratings yet, and catalogue scope remains materially unverified. The technical config is frozen for review, but **human scope approval is absent**; `allow_final_test_execution: false` documents this. The guarded CLI refuses to read the sealed table without a separate, privately stored approval JSON containing two completed rating paths, distinct sign-offs, an explicit no-fundamental-scope-issue decision and matching protocol/model hashes. This gate cannot itself prove that a person, rather than software, authored the ratings; external reviewer audit is still required.

Only after genuine human review and an explicit, reviewed update to the gate status may an authorized researcher run the following template once, with a new output directory:

```bash
openalex-final-test --execute-once \
  --human-gate data/analysis/finalization_p3_human_approval.json \
  --frozen-protocol config/finalization_p3_frozen_evaluation.yaml \
  --model-dir models/finalization_p3/topic_placement_v2 \
  --web-dir data/analysis/finalization_p2_web_data_20261101_v3 \
  --test-path data/processed/ml_topic_classification/finalization_p2_20261101_v3/test_2025_sealed.parquet \
  --output-dir data/analysis/finalization_p3_final_test_ONCE
```

**Do not run this command now.** The approval JSON does not exist. Human ratings, test predictions and the model binary are Git-ignored and must not be pushed.
