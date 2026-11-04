# RQ7.1 metadata-validation sample

Source pilot verifier: **PASS**; 14 top-level/processed files verified. The source pilot's own verifier checked 1,427 stored artifacts. Fixed seed: **20261104**. Final selected: **100 distinct canonical Work IDs**. The selection hash uses the `rq7_1_review:` namespace to avoid reusing the prior Group-A cohort ordering. A preliminary local v1 with the reused hash was superseded without deletion; only v2 is used for results.

| Primary stratum | Selected | Group A | Group B |
|---|---:|---:|---:|
| S1_PUBLISHER | 30 | 22 | 8 |
| S2_LICENSE | 30 | 29 | 1 |
| S3_CONFLICT | 20 | 19 | 1 |
| S4_CROSSREF_404 | 20 | 11 | 9 |

Eligibility counts before sequential exclusion: recovered publisher 167, recovered license 277, any provider conflict 944, Crossref 404 440. Strata are assigned in the order shown, without replacement. Secondary flags remain in the private sample. No stratum was short; the code fails rather than silently redistributing. Year/type diversity is recorded in the private table but not quota-controlled. This is a **diagnostic sample**, not a prevalence estimator for the original 12,000 works or full AI/CV population. Private selected Work IDs, titles and review sheets remain Git-ignored at `data/analysis/rq7_quality_validation/rq7_1_20261104_v2`.

Review state: **PENDING_HUMAN_REVIEW** for all 100 works. No agreement or accuracy is claimed.
