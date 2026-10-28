# Phase 6B — Final topic-classification feasibility review

## Executive verdict: **REVISE; do not adopt a general topic finder**

The 14-topic expansion is technically learnable against OpenAlex's automated primary-topic labels: it covers **689/1,873 (36.8%)** of text-eligible 2024 sampled works, and the best 2024 closed-set model (TF-IDF + Linear SVM) reaches macro-F1 **0.857** (paper-bootstrap 95% interval **[0.830, 0.878]**). But a classifier deployed on arbitrary titles and abstracts must also know when *not* to assign one of its 14 labels. At the threshold chosen on a separate 2024 calibration subset, it accepts only **307/414 (74.2%)** in-catalogue papers and incorrectly accepts **136/710 (19.2%)** outside-catalogue papers. Only **287/1,124 (25.5%)** of all eligible evaluation papers are both accepted and assigned their OpenAlex primary topic correctly. The precommitted ≥80% in-catalogue acceptance gate fails. Independent human semantic review has not occurred. The **2025 final test remains sealed**; there is no 2025 model result.

The bounded recommendation for this Introduction to Data Science project is a **five-topic educational demonstration** with explicit abstention and silver-label warnings, not an unrestricted AI/CV topic discovery product. This is a revision, not a final scientific-validity GO. The 14-topic result remains a useful research diagnostic, not wasted work.

## 1. Data integrity and prospective decisions

The study frame is the already approved 2020–2025 OpenAlex AI/CV primary-subfield sample, not all global AI research. No new OpenAlex works were collected. The unchanged Phase 3 source contains **12,000** unique works and **36,000** work-topic relationships; its read-only validator passed **29/29** checks. The source `works.parquet` SHA-256 is `9318c456d916b8c9a35b0a3c86a829a92347083357693593e743abb0253264d4`, `work_topics.parquet` is `e65356b899f3c9dec4d9d47ec9dae54557b23dc1709a1b3ea1d4c5f746acf6d5`, and the Phase 3 manifest is `5d21e6187f0cf569b284ea399ffff02cb02d29d1e936a5fa716c7c96758de19c`.

The [expanded-catalogue protocol](../docs/PHASE6B_EXPANDED_CATALOGUE_PROTOCOL.md), [decision criteria](../docs/PHASE6B_DECISION_CRITERIA.md), selected IDs and official metadata hash were committed as `dd437f8` **before expanded model fitting**. These criteria are project-specific, not universal. The 2024 development set had already been examined in Phase 6A, so this is not a claim of full preregistration. The completed canonical local run is `data/analysis/phase6b_topic_validation_20261028_v3/` (Git-ignored), timestamp `2026-10-28T13:10:45.980654+00:00`, manifest SHA-256 `8adeee71c0b37d3e5b85d06360d2d471b72618daf1a4427b023570664bac9c79`. Its read-only verifier passed **34/34 output hashes**. All 34 v2/v3 output hashes matched, demonstrating a deterministic rerun of the corrected method; timing and manifest timestamps naturally differ. The first v1 run used a seeded random calibration split, contrary to the protocol's stable-hash wording, so it was retained but **not** used for the final decision; v2/v3 use a deterministic version-group hash split. No prior run was overwritten.

Only 2020–2024 records enter development: **9,024** source works, **7,058** after nonblank title/abstract and version isolation, **5,185** training (2020–2023) and **1,873** 2024 validation. Catalogue selection and support use no 2025 labels. The local Phase 6A experiment was independently rerun; its 16/16 output hashes matched the prior completed run. Its five-topic SVM macro-F1 **0.953** and Logistic Regression **0.849** were reproduced. All labels here are OpenAlex-generated **silver labels**, not independent human truth.

## 2. Expanded catalogue and scope

Twenty candidate primary topics met the relaxed *pre-2025* support rule (≥70 training and ≥20 validation records). We provisionally retained 14 AI/CV method/task topics. Official names, full descriptions, hierarchy, reasons, overlap caveats, all 20 support counts and source URLs are in the [published scope table](phase6b/scope_review.csv), backed by a hashed OpenAlex topic-metadata snapshot. Independent domain review remains outstanding, especially for broad T10036/T10028 and cross-domain metaheuristics T10100. The six exclusions/uncertainties were not reassigned on the basis of model performance.

| Topic ID | Verified OpenAlex name | Train 2020–23 | Validation 2024 | Scope note |
|---|---|---:|---:|---|
| T10028 | Topic Modeling | 149 | 85 | broad NLP cluster |
| T10036 | Advanced Neural Network Applications | 369 | 146 | broad CV/deep learning |
| T10052 | Medical Image Segmentation Techniques | 127 | 45 | CV task, medical setting |
| T10100 | Metaheuristic Optimization Algorithms Research | 104 | 36 | cross-domain; human review needed |
| T10181 | Natural Language Processing Techniques | 94 | 36 | NLP/language modelling |
| T10201 | Speech Recognition and Synthesis | 86 | 24 | audio/language methods |
| T10331 | Video Surveillance and Tracking Methods | 103 | 22 | CV tracking |
| T10462 | Reinforcement Learning in Robotics | 120 | 45 | RL, robotics-specific |
| T10664 | Sentiment Analysis and Opinion Mining | 190 | 58 | NLP task |
| T10775 | Generative Adversarial Networks and Image Synthesis | 104 | 53 | generative CV |
| T10812 | Human Pose and Action Recognition | 73 | 21 | CV pose/action |
| T11307 | Domain Adaptation and Few-Shot Learning | 84 | 42 | transfer learning |
| T11689 | Adversarial Robustness in Machine Learning | 73 | 39 | robust ML |
| T12026 | Explainable Artificial Intelligence (XAI) | 70 | 37 | interpretability |

Catalogue A is the original five `T10036/T10664/T10028/T10052/T10462`; Catalogue B contains all 14 above. Their training sizes are **955** and **1,746**, and their 2024 validation sizes are **379** and **689**. Coverage is **20.2%** versus **36.8%**, a **+16.6 percentage-point** change in this sampled, text-eligible slice. Do **not** read these as full-population topic shares. B coverage across 2020–2024 eligible works rises from **31.6%** to **36.8%** by year; across subfields it is **30.5%** for 1702 and **41.5%** for 1707; by type **29.9%** article, **49.0%** preprint, **35.1%** review (only 37 eligible reviews); by language **35.4%** English, **24.0%** other recorded languages and **23.7%** missing language. See the four [coverage CSVs](phase6b/catalogue_b_coverage_year.csv). These are descriptive sample slices, with unverified sampling probabilities and small subgroup denominators.

## 3. Phase 6A SVM sanity and duplicate audit

On the exact five-class 2024 slice, SVM accuracy is **0.950**, weighted-F1 **0.950**, macro-F1 **0.953** (bootstrap 95% interval **[0.934, 0.973]**). Its macro-F1 advantage over Logistic Regression has paired bootstrap interval **[0.064, 0.146]**. All five SVM recalls are nonzero and range from **0.906** (T10028) to **0.978** (T10052); classwise precision/recall/F1 and the complete confusion matrix are [published](phase6b/catalogue_a_linear_svm_per_class.csv). The most common A confusion is five T10028 papers assigned T10664, consistent with overlapping NLP terms. SVM fit time in this run was **0.648 s** and batched inference including vectorization **0.167 s/379 papers**; hardware-specific, not a production latency promise.

The audit found **zero** cross-period exact title+abstract, normalized-title and canonical-DOI groups among eligible 2020–2024 works. A rare-token title blocker compared **37,456** candidate train/validation pairs and found **zero** near-duplicate pairs at its documented similarity thresholds; thus the near-duplicate sensitivity removes zero validation works and leaves SVM macro-F1 unchanged. This is not proof that no reworded versions exist. There were **three cross-period exact-abstract strings** with different titles. Local inspection found reused journal/thesis boilerplate; one 2024 T12026 record shares boilerplate with a 2020 T10764 work, which is **outside** both trained catalogues. No in-catalogue training/validation pair shared those boilerplate abstracts. Record-level IDs/text remain local. This anomaly reinforces that abstract availability does not guarantee useful abstract content.

The five-class SVM uses only title and abstract TF-IDF. It reaches macro-F1 **0.863** using title only, **0.945** using abstract only, and **0.953** with both. Top positive terms include `language`, `text`, `bert` for T10028 and `object`, `detection`, `recognition`, `image` for T10036 ([term audit](phase6b/catalogue_a_svm_top_terms.csv)). This is credible lexical discrimination, but it likely tracks vocabulary also used by OpenAlex's automated topic assignment. It does **not** prove nuanced scientific understanding or human semantic validity. Predictive features exclude topic IDs/scores, authors, citations and publication metadata; TF-IDF is fitted on training only.

## 4. Closed-set comparison on 2024 OpenAlex silver labels

Each table compares models on the *same in-catalogue examples within that catalogue*. Percentile 95% intervals are 300 fixed-seed paired paper-bootstrap draws over 2024 records, not population-level uncertainty or uncertainty in the silver labels. A and B use different label universes and cannot be ranked as the same task.

| Method | A accuracy | A macro-F1 (95% CI) | A weighted-F1 | B accuracy | B macro-F1 (95% CI) | B weighted-F1 |
|---|---:|---:|---:|---:|---:|---:|
| Train-majority | .385 | .111 [.100, .122] | .214 | .212 | .025 [.022, .028] | .074 |
| Official-description TF-IDF match | .625 | .577 [.519, .631] | .625 | .572 | .550 [.510, .585] | .575 |
| Complement NB | .834 | .827 [.786, .868] | .829 | .792 | .775 [.732, .803] | .784 |
| Logistic Regression | .860 | .849 [.805, .890] | .856 | .788 | .773 [.733, .803] | .781 |
| Linear SVM | **.950** | **.953 [.934, .973]** | **.950** | **.862** | **.857 [.830, .878]** | **.860** |

For B, the best SVM is **+0.307 macro-F1** above the strongest baseline (description matching). Its paired macro-F1 difference from Logistic Regression has bootstrap 95% interval **[.060, .117]**. Training-only 3-fold CV chose SVM `C=3`; best-parameter fold macro-F1 values were **.866, .846, .829** (mean .847). B top-3 silver-label accuracy is **.972**. SVM training search took **9.84 s** and batched validation inference including vectorization **0.206 s/689 works** (~0.300 ms/work); loading, text cleaning and web transport are excluded. No embedding model was run: the bounded conventional baselines already answer the feasibility question without adding compute or a new dependency.

The [B classwise table](phase6b/catalogue_b_linear_svm_per_class.csv) shows all 14 recalls nonzero, but weaker T10181 NLP techniques (**21/36 = 58.3%**) and T11307 domain adaptation (**29/42 = 69.0%**). The [B confusion matrix](phase6b/catalogue_b_linear_svm_confusion.csv) shows **11** T10181 works assigned broad T10028; six T10775 GAN/image-synthesis works assigned broad T10036. These are OpenAlex-label disagreements, not automatically model mistakes or mislabelled papers. 2020–2023 training folds and 2024 validation support only limited temporal robustness; 2025 remains untested.

## 5. Open-set rejection and real-world denominator

The 2024 eligible set was split by deterministic version-group hash within primary-topic/outside strata: **749** calibration works (275 inside, 474 outside) and disjoint **1,124** evaluation works (414 inside, 710 outside). The primary SVM rejection score is the maximum raw one-vs-rest decision score, **not a probability**. The threshold **−0.14025548** was selected on calibration alone to keep outside false acceptance ≤20%; calibration achieved **204/275 (74.2%)** inside acceptance and **94/474 (19.8%)** outside false acceptance. Without changing it, the disjoint evaluation gave:

| Measure | SVM, independent 2024 evaluation | Denominator |
|---|---:|---|
| In-catalogue acceptance | **307/414 = 74.2%** | OpenAlex primary topic in 14 |
| In-catalogue false rejection | 107/414 = 25.8% | In 14 |
| Out-of-catalogue false acceptance | **136/710 = 19.2%** | Primary topic outside 14 |
| AUROC distinguishing in/out | .868 | All 1,124 |
| Accepted papers actually in catalogue | 307/443 = 69.3% | All accepted |
| Correct class among accepted in-catalogue | 287/307 = 93.5% | Accepted in 14 |
| Selective risk / in-catalogue coverage | 6.5% / 74.2% | Accepted-in / all in |
| End-to-end correct placement | **287/1,124 = 25.5%** | **All eligible** evaluation works |

An uncalibrated Logistic Regression maximum-probability diagnostic, threshold selected by the same calibration cap, reaches **65.2%** in acceptance, **18.7%** outside false acceptance and **22.1%** end-to-end correct placement; its raw probabilities are not shown to be calibrated. The SVM is preferable but still fails the fixed ≥80% acceptance gate. The closed-set 0.857 macro-F1 applies only to papers already known to have an OpenAlex primary topic in B; it must not replace the all-paper workflow denominator. The observed 69.3% accepted precision depends on the sampled inside/outside mixture and does not transport directly to other submissions.

## 6. Human validation and Topic Brief proof of concept

The run generated local blind sheets with **40 calibration** and **100 evaluation** title/abstract examples, randomized topic-option order, and *separate restricted answer keys*. The two independent rating columns are blank. No human ratings, inter-rater agreement or independently established topic accuracy exist. The importer rejects incomplete/invalid ratings and can calculate agreement and OpenAlex/model acceptance only after real ratings are supplied. The catalogue is a **single-researcher provisional** scope review; no human semantic endorsement is claimed. The [annotation instructions](../docs/PHASE6B_HUMAN_REVIEW_INSTRUCTIONS.md) keep reviewers blind to OpenAlex and model labels.

The local offline [Topic Brief](../src/ai_research_trends/ml/topic_brief.py) proof of concept loads a SHA-verified SVM model, rejects invalid title/abstract input, returns ranked candidate IDs/names and raw scores, abstains when its fixed threshold is not reached, and attaches a brief with verified OpenAlex descriptions and **2020–2024 detailed-sample** year/OA/citation context. A medical-image segmentation example was placed as T10052; an archaeology/pottery example returned `no_confident_match`. These are demonstrations, **not** measured user satisfaction. The brief does not have exact primary-topic full-population counts or a validated core-literature list, so both are explicitly unavailable. No website was built. Model binaries, paper text, Work-ID-level predictions and answer keys stay Git-ignored.

## 7. Scientific interpretation and next gate

The study's population trends and Phase 4 bibliometrics remain separate from this sampled ML task. The Phase 2 detailed sample has unverified server-side inclusion probabilities; the 2024 class mix is therefore a diagnostic mix, not a prevalence estimate. Title/abstract missingness excludes 1,966 of 2020–2024 source works (after all eligibility exclusions); non-English performance and taxonomic drift remain unvalidated. OpenAlex primary-topic labels are automated and mutually exclusive at the work level, although actual research areas overlap. Broad and narrow topics compete as labels. The high text-model score may partly reflect reproducing the OpenAlex classifier's own lexical decision boundary. The 14-topic catalogue is provisional; forcing an outside paper into it risks an authoritative-looking false label. No research-quality inference follows from model score or citations.

**Gate result:** catalogue coverage (36.8%), closed-set performance (.857; all 14 recalls nonzero), baseline advantage (+.307), duplicate/leakage checks and offline proof of concept pass their technical checks. The independent open-set acceptance target fails (74.2% < 80%), and human semantic validity is pending. Therefore the condition for a one-time final 2025 evaluation is **not met**. We have not frozen a final 2025 protocol or examined 2025 predictions; `test_2025=sealed_not_evaluated` is recorded in the completed local manifest. Do not relax the threshold or tune on 2025 after seeing this result.

**Next task:** have two independent subject-aware reviewers rate the already prepared 100-example blind evaluation sheet, with the 40-example sheet used to settle instructions only. Then decide whether a clearly labelled **five-topic educational demonstration** with mandatory abstention is acceptable. Do not claim a comprehensive 14-topic classifier or start the final website as an unrestricted topic finder. This narrow path fits a course project and preserves all earlier research, but official adoption still requires human validation and a product-scope decision.

## Reproduce and verify

From the repository root after `pip install -e ".[dev]"`:

```bash
openalex-validate-processed --output-dir data/processed/openalex_stratified/stratified_20261019T155909Z --plan data/metadata/phase2_sampling_plan.json --population data/metadata/population_counts_pre_phase2.json --config config/topics.yaml
openalex-pilot-topics --output-dir data/analysis/phase6a_reproduction_NEW
openalex-validate-topics-final --output-dir data/analysis/phase6b_topic_validation_NEW
openalex-verify-topic-run --run-dir data/analysis/phase6b_topic_validation_NEW
pytest -q -ra
pip check
```

The commands require local Git-ignored Phase 3 data; GitHub contains the small [public aggregate summary](phase6b/summary.json) and [aggregate CSVs](phase6b/README.md), not the raw/sample paper records or model artifact. A new versioned run is required for each reproduction; outputs are never overwritten.
