# Open-set development evaluation and abstention

The original-sample 2024 eligible cohort (1,843) was partitioned by version group into a **738-work threshold-calibration** group and a disjoint **1,105-work evaluation** group. The evaluation group contains **408 in-catalogue** and **697 outside-catalogue** works. All fitted model parameters use 2020–2023 training only. For each score family, the lowest calibration threshold satisfying an outside false-acceptance cap of 20% was frozen before computing evaluation outcomes. Scores are method-specific; SVM margins are **not probabilities**.

| Rejection method | In-catalogue acceptance | Outside false acceptance | AUROC in vs out | Correct accepted in / all eligible |
|---|---:|---:|---:|---:|
| Train-CV sigmoid-calibrated LR | 0.6225 | 0.2023 | 0.8024 | 0.2217 |
| Raw LR maximum probability | 0.7941 | 0.1793 | 0.8878 | 0.2724 |
| Raw SVM maximum margin (selected) | **0.8309** | **0.2166** | **0.8919** | **0.2833** |
| NB maximum probability | 0.6618 | 0.2281 | 0.8091 | 0.2290 |
| Explicit 15-class OTHER LR | 0.9265 | 0.1750 | 0.9473 | 0.3023 |

For the chosen SVM, threshold **−0.22227267687798036** and a lower confirmation floor **−0.516798309254057** derive from calibration. In evaluation, **339/408** in-catalogue works and **151/697** outside works were accepted; **313/1,105** were both accepted and correctly placed. The 500-resample outside false-acceptance 95% interval is approximately **[0.188, 0.246]**. Thus the calibration target did **not** transfer cleanly to this evaluation group. The final service treats even high-margin suggestions as unconfirmed.

The explicit-OTHER approach is a promising **exploratory benchmark**, but replacing the selected champion based on these same development outcomes would be post hoc. A future model-policy revision needs a newly declared protocol and separate validation. The 2025 final test is sealed and cannot arbitrate development changes while genuine human scope review is pending.

See [ROC](../figures/finalization_p3/open_set_roc.png), [risk–coverage](../figures/finalization_p3/risk_coverage.png), and [threshold sensitivity](../figures/finalization_p3/threshold_sensitivity.png). These estimates measure OpenAlex-label agreement within a restricted original-sample development cohort, not real-world semantic correctness or calibrated catalogue membership probabilities.
