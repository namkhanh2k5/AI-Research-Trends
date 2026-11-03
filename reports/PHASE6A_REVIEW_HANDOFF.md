# Phase 6A external-review handoff

Repository branch: `feature/phase6-topic-classification-pilot`. Phase 6A code commit SHA: `6d6db7be8f6135f9cc13d9855835f542b17f37d8`. Base Phase 5 commit: `8af68caa91de37fc01b2b116df5254c5b2c869b9`. Primary evidence: [full feasibility report](PHASE6A_TOPIC_CLASSIFICATION_FEASIBILITY.md), [pre-model selection protocol](../docs/PHASE6_TOPIC_SELECTION_PROTOCOL.md), [catalogue and source descriptions](../config/phase6_topic_catalogue.yaml), [human annotation instructions](../docs/PHASE6_HUMAN_ANNOTATION_GUIDELINES.md), and `src/ai_research_trends/ml/topic_pilot.py`.

## Verified, on the local data

- Inputs: 12,000 works and 36,000 topic memberships from the Phase 3 validated run. `works.parquet` SHA-256 `9318c456d916b8c9a35b0a3c86a829a92347083357693593e743abb0253264d4`; `work_topics.parquet` SHA-256 `e65356b899f3c9dec4d9d47ec9dae54557b23dc1709a1b3ea1d4c5f746acf6d5`. Completed Phase 3 manifest SHA-256 `5d21e6187f0cf569b284ea399ffff02cb02d29d1e936a5fa716c7c96758de19c`.
- Rank-1 topic matches the work's primary topic for all 12,000. After text and version exclusions, 9,431 works remain. Ten possible duplicate/version groups contain multiple works; no conflicting labels were seen in those groups. The audit covers 106 primary topics; only nine meet 120/30 training/validation support, and only five pass provisional AI/CV semantic scope.
- Provisional selected IDs: `T10036`, `T10664`, `T10028`, `T10052`, `T10462`. Training 2020–2023: 955 works. Validation 2024: 379 in-catalogue plus 1,494 out-of-catalogue text-eligible works. Dedicated 2025 locked split: 2,373 IDs/version groups, not evaluated. Selection uses only training/validation support and semantic review, never 2025 class counts.
- On the identical 379-paper validation set, macro-F1: majority 0.111, verified-description match 0.579, Logistic Regression 0.849, Complement NB 0.827, Linear SVM 0.953. Logistic accuracy 0.860. Its paired macro-F1 improvement over the description baseline has 95% bootstrap interval [0.199, 0.329]. This is **agreement with OpenAlex silver labels**.
- Catalogue coverage is 18.4% of text-eligible 2020–2023 and 20.2% of text-eligible 2024. The provisional 8–15-topic gate fails. With uncalibrated Logistic maximum-probability threshold 0.5, 159/379 in-catalogue examples would be rejected while 310/1,494 out-of-catalogue papers would be assigned confidently.
- Validation uses title/abstract only; TF-IDF is fitted on training text. Version groups are isolated across periods. The five-class diagnostic does not inspect 2025 model errors or tune on 2025. Local artifacts and their SHA-256 hashes are under `data/analysis/phase6_topic_pilot_20261028_v11/`; paper text, prediction rows and restricted answer key are intentionally Git-ignored.
- Verification: Phase 3 read-only validator 29/29 checks passed; v11/v12 produced 16/16 identical output hashes; [eight published aggregate audit tables](phase6a/README.md) and the support PNG match source hashes. Offline test suite: 137 passed, one opt-in live test skipped; `pip check` clean; installed pilot CLI `--help` passed.

## Interpretation and untested assumptions

**Interpretation:** high closed-set agreement is promising for an educational silver-label prediction exercise, but the 20.2% coverage and poor open-set diagnostic make a broad topic-selection website premature. The decision is **REVISE**, not GO. A model trained on OpenAlex's own automated labels may imitate their title/abstract patterns; it cannot establish independent scientific correctness.

The 120/30 primary support gate and 8–15-topic aim were documented before fitting. The smaller five-class contingency was added after preliminary support inspection but before model fitting. Treat its metrics as exploratory, not a preregistered confirmatory success.

**Untested:** human semantic validity, inter-rater agreement, temporal stability after taxonomy updates, full-population transportability, robust near-duplicate removal, calibration, and whether a justified broader catalogue can attain comparable classwise performance. Thirty-six blinded 2024 records and a separate answer key are prepared; **human label validation pending**. No annotation scores or kappa were invented.

## Questions for the external reviewer

1. Are the five provisional scope decisions defensible, especially broad neural-network applications and medical image segmentation?
2. Should the final undergraduate task be explicitly narrowed to a five-topic educational demonstration, or should an independently reviewed regrouping be defined before further modelling?
3. Is a 20.2% validation-period catalogue reach acceptable for a narrowly described use case? If not, what prospective coverage requirement is appropriate?
4. What human-label adjudication size and open-set evaluation would be enough before a user-facing scientific claim?

No Phase 1–5 output was modified; no 2025 test metric or human-label result is claimed.
