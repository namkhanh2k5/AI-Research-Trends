# Human semantic-validation status

**Status: WITHDRAWN from project scope on 2026-11-20. Not performed.** A blinded package for
two reviewers was prepared, with 40 calibration and 100 evaluation items each. No rating
was ever submitted. The project owner withdrew the review instead of leaving it pending.
The decision is recorded in the [protocol amendment](../../config/final_test_2025_amendment.yaml).

Consequences:

- No inter-rater agreement, semantic accuracy or catalogue-adequacy claim is made. All model
  metrics, including the [2025 hold-out result](FINALIZATION_P3_FINAL_TEST_STATUS.md),
  measure agreement with OpenAlex primary-topic *silver labels*.
- The rating interface, rating validators and agreement analysis were removed. The
  blank package in `data/analysis/finalization_p2_human_review_20261101_v1/` and the Phase 6
  blind sheets remain as checksum-bound historical records only.
- The application continues to present topic placement as an assisted suggestion that the
  user must confirm.
