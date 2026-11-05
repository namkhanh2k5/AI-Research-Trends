# Human semantic-validation status

**Status: PENDING.** The Phase 2 blinded review package exists for two independent human reviewers (40 calibration and 100 evaluation items each), but no completed, authenticated real-human rating submissions were supplied during this Phase 3 execution. We did **not** create ratings, estimate inter-rater agreement, infer semantic accuracy, or certify catalogue coverage. OpenAlex labels remain *silver labels* throughout the reported development metrics.

The next owner should obtain two genuinely independent completed evaluation files, validate them against the blinded package with the existing `human_review_workflow` validator, report agreement and disagreements, and obtain an explicit catalogue/scope decision. The two reviewers must not see each other's labels before submission. Neither a model prediction nor synthetic/AI-generated ratings can substitute for this review.

Until then, the 2025 test gate stays disabled and the service must be presented only as an assisted suggestion prototype. This is a substantive scientific limitation, not a routine missing checkbox.
