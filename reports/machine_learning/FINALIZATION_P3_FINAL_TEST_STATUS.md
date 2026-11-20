# 2025 final-test result

**EVALUATED ONCE on 2026-11-20.** The frozen `topic_placement_v2` Linear SVM and its
2024-calibrated threshold were applied, without any change, to the 2,318 eligible
original-sample 2025 works. Labels are OpenAlex primary-topic **silver labels**; every
number below measures agreement with them, not human-judged semantic accuracy.

## Authorization and provenance

Phase 3 kept 2025 sealed until two independent human raters signed off. No rating was
ever collected, and on 2026-11-20 that review was withdrawn from project scope. The
[protocol amendment](../../config/final_test_2025_amendment.yaml) records this decision.
It leaves the [frozen protocol](../../config/finalization_p3_frozen_evaluation.yaml)
byte-identical and authorizes exactly one run. The model, classes, feature rule,
threshold, denominators and metrics are unchanged.

Git history shows the frozen protocol and model hash `b066ba80…` were committed on
2026-11-01 (`87ac7b5`). The 2025 table was first committed on 2026-11-04 (`811e98f`).
The labels are OpenAlex silver labels that were always available through the API, so the
seal was a procedural rule rather than a secret. Git history, not an external auditor,
is the evidence that 2025 played no part in model, feature or threshold selection.

`openalex-final-test` verified the amendment, frozen hashes, integrated split and
label-free 2025 columns before writing the project
[registry](../../data/analysis/finalization_p3_final_test_registry.json). It read the
label column only after that. The registry blocks any second run. Outputs are in
`data/analysis/finalization_p3_final_test_2025_v1/` (`result.json`, `per_class.csv`,
`confusion.csv`, `predictions.parquet`).

## Results

| Metric | 2024 development | 2025 hold-out (once) |
|---|---:|---:|
| Closed-set works (in catalogue) | 681 | 831 |
| Macro-F1 | 0.8808 | **0.8698** [0.8440, 0.8931] |
| Accuracy | 0.8796 | 0.8736 |
| Open-set works (in / outside) | 1,105 (408 / 697) | 2,318 (831 / 1,487) |
| In-catalogue acceptance | 0.8309 | 0.7954 [0.7686, 0.8208] |
| Outside false acceptance (target ≤ 0.20) | 0.2166 | **0.2098** [0.1927, 0.2291] |
| AUROC in vs outside | 0.8919 | 0.8781 |
| Accuracy among accepted in-catalogue | 0.9233 | 0.9486 |
| Correct accepted placement / all eligible | 0.2833 | 0.2705 |

Brackets are 500-draw bootstrap 95% intervals with seed 20251019. The 2024 open-set
column is the 1,105-work evaluation group; 2025 uses all eligible works, as the frozen
`evaluation_denominators` specify.

## Interpretation

- **Closed set holds up.** The 2024 point estimate (0.8808) lies inside the 2025 interval.
  There is no evidence of material one-year degradation, and the 2024 figure was not
  merely an artefact of model selection.
- **The open-set target is still not met.** The point estimate of outside false
  acceptance (20.98%) exceeds 20%, although the interval includes 20%. In-catalogue
  acceptance fell 3.5 points. Every suggestion therefore still requires user confirmation.
- **About 64% of eligible 2025 works fall outside the 14 topics.** End-to-end correct
  placement is therefore low (27%), even though accepted in-catalogue suggestions are 95%
  correct.

## Per-class F1, sorted by change

| Topic | n 2024 | F1 2024 | n 2025 | F1 2025 | Δ |
|---|---:|---:|---:|---:|---:|
| T11307 Domain Adaptation and Few-Shot Learning | 42 | 0.841 | 39 | 0.716 | −0.125 |
| T12026 Explainable Artificial Intelligence (XAI) | 35 | 0.925 | 38 | 0.835 | −0.090 |
| T10812 Human Pose and Action Recognition | 21 | 0.933 | 18 | 0.872 | −0.062 |
| T11689 Adversarial Robustness in Machine Learning | 39 | 0.909 | 56 | 0.849 | −0.060 |
| T10775 Generative Adversarial Networks and Image Synthesis | 53 | 0.906 | 64 | 0.884 | −0.022 |
| T10036 Advanced Neural Network Applications | 143 | 0.889 | 160 | 0.876 | −0.013 |
| T10100 Metaheuristic Optimization Algorithms Research | 34 | 0.970 | 35 | 0.958 | −0.012 |
| T10331 Video Surveillance and Tracking Methods | 22 | 0.818 | 29 | 0.821 | +0.003 |
| T10664 Sentiment Analysis and Opinion Mining | 58 | 0.941 | 77 | 0.948 | +0.007 |
| T10462 Reinforcement Learning in Robotics | 45 | 0.936 | 71 | 0.952 | +0.016 |
| T10028 Topic Modeling | 84 | 0.800 | 134 | 0.833 | +0.033 |
| T10181 Natural Language Processing Techniques | 36 | 0.704 | 35 | 0.740 | +0.036 |
| T10052 Medical Image Segmentation Techniques | 45 | 0.889 | 42 | 0.955 | +0.066 |
| T10201 Speech Recognition and Synthesis | 24 | 0.870 | 33 | 0.939 | +0.070 |

Several classes have fewer than 40 test works, so single-class changes are noisy. The
largest confusions in 2025 are NLP Techniques ↔ Topic Modeling (7 and 6 works) and
Advanced Neural Network Applications → Domain Adaptation (6). Those labels overlap by
design and are not necessarily errors.

## Limits

These results come from one temporal hold-out year with OpenAlex silver labels. No model,
threshold or catalogue change may be made on the basis of these results and then
re-reported on 2025.
