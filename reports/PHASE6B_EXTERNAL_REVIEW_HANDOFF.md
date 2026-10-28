# External-review handoff — Phase 6B topic classification

**Repository:** [namkhanh2k5/AI-Research-Trends](https://github.com/namkhanh2k5/AI-Research-Trends) · **review branch:** [`feature/phase6b-topic-final-validation`](https://github.com/namkhanh2k5/AI-Research-Trends/tree/feature/phase6b-topic-final-validation) (the branch page shows the current tip SHA). The protocol/decision freeze was committed as `dd437f837dc27ae9a622fe29cf8053f974d24c00` before expanded fitting. **Prior Phase 6A decision:** REVISE, because the five selected OpenAlex topics covered only 20.2% of text-eligible sampled 2024 works despite SVM macro-F1 0.953.

## What was tested

The original five-topic catalogue A had **955** 2020–2023 training and **379** 2024 validation works; the provisionally reviewed 14-topic catalogue B had **1,746** training and **689** validation works. Both use only nonblank title+abstract, one work per exact DOI/title version group, and OpenAlex **primary-topic silver labels**. B covers **36.8% (689/1,873)** of eligible 2024 sampled works versus A's **20.2% (379/1,873)**. This is not a full-population topic share. All 14 B topics meet pre-2025 support ≥70 training / ≥20 validation. The [scope table](phase6b/scope_review.csv) has IDs, official descriptions, hierarchy and provisional in/out/uncertain reasons; [catalogue config](../config/phase6b_catalogue.yaml) freezes the list.

| 2024 model | A macro-F1 | B macro-F1 | B accuracy | B weighted-F1 |
|---|---:|---:|---:|---:|
| Train-majority | .111 | .025 | .212 | .074 |
| Official-description match | .577 | .550 | .572 | .575 |
| Complement NB | .827 | .775 | .792 | .784 |
| Logistic Regression | .849 | .773 | .788 | .781 |
| Linear SVM | **.953** | **.857** | **.862** | **.860** |

B SVM macro-F1 paper-bootstrap 95% interval: **[.830, .878]**, best-parameter training-fold scores **.866/.846/.829**. All 14 classes have nonzero recall; weak points include T10181 NLP techniques **21/36** and T11307 domain adaptation **29/42**. Its confusion matrix shows **11** T10181→T10028 and **6** T10775→T10036. See [per-class results](phase6b/catalogue_b_linear_svm_per_class.csv), [matrix](phase6b/catalogue_b_linear_svm_confusion.csv), [full aggregate summary](phase6b/summary.json), and [main interpretation](PHASE6B_FINAL_TOPIC_VALIDATION_REPORT.md). A and B metrics describe different label universes.

## Open-set gate and verdict

The 2024 data were divided by stable version-group hash, within silver-label strata: **749** calibration and **1,124** independent evaluation works. The SVM's maximum decision score is not a probability. A threshold chosen only on calibration to cap outside false acceptance at 20% produced **307/414 (74.2%)** in-catalogue acceptance and **136/710 (19.2%)** out-of-catalogue false acceptance on independent evaluation. Accepted in-catalogue class accuracy was **287/307 (93.5%)**; overall correct placement was just **287/1,124 (25.5%)**. The fixed ≥80% in-catalogue acceptance gate failed. The five-class high score is technically reproducible, with no exact title/DOI/text cross-period duplicates; three shared boilerplate abstract strings were found, but no selected training/validation class pair shared them. A blocked near-duplicate audit found zero pairs among 37,456 candidates, with documented recall limits. TF-IDF uses only train-period title+abstract; 2025 labels are not consulted by the Phase 6B development code.

**Human-label status:** no independent ratings. The 14-topic scope is a single-researcher provisional judgement. Local blind 40/100-example sheets and a two-rater importer are ready, but the answer keys/paper text stay private. **2025 final test:** **not run**, because a fixed development gate failed; the local run manifest says `sealed_not_evaluated`. **Offline Topic Brief:** implemented, checksum-verified and exercised on in-scope/out-of-scope example inputs; no full website. Scientific correctness and public usefulness remain unproven.

**Decision: REVISE.** Do **not** officially adopt a general 14-topic AI/CV topic finder. The bounded path is a clearly labelled **five-topic educational demonstration** with abstention and human review before user-facing scientific claims. Do not change the catalogue/threshold on 2025 to rescue the expanded design. This preserves Phases 1–4 and a feasible supervised-model comparison for an introductory Data Science project, subject to an examiner approving the narrower product claim.

## Evidence and questions for reviewer

The local canonical `data/analysis/phase6b_topic_validation_20261028_v3/manifest.json` has SHA-256 `8adeee71c0b37d3e5b85d06360d2d471b72618daf1a4427b023570664bac9c79`; a read-only check verified 34/34 outputs, and the corrected v2/v3 runs matched 34/34 output hashes. The unchanged Phase 3 validator passed 29/29 table checks. The [protocol](../docs/PHASE6B_EXPANDED_CATALOGUE_PROTOCOL.md) and [decision criteria](../docs/PHASE6B_DECISION_CRITERIA.md) precede expanded fitting. Source and test code: [final-validation pipeline](../src/ai_research_trends/ml/topic_final_validation.py), [Topic Brief](../src/ai_research_trends/ml/topic_brief.py), [two-rater importer](../src/ai_research_trends/ml/topic_annotation.py), [offline tests](../tests/test_phase6b_final_validation.py). The [README](../README.md) has rerun commands, requiring local Git-ignored Phase 3 data.

Please assess: (1) Is T10100 methodologically coherent in an AI/CV catalogue, or should it remain outside pending domain review? (2) Does reproducing OpenAlex lexical labels meet the course's supervised-ML objective if called *silver-label agreement*? (3) Is the proposed five-topic educational scope honest and useful, given poor broad open-set placement? (4) What minimum two-rater evidence would you require before user-facing semantic claims? A website would still need a UI, restricted input handling, explicit abstention, model/data provenance display, accessibility, deployment tests and a non-causal bibliometric context; **none is claimed complete**.
