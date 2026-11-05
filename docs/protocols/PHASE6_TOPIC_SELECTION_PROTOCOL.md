# Phase 6A topic-catalogue selection protocol (pre-model)

Status: predeclared pilot protocol, written before inspecting model validation results. The unit is one Phase 3 work; its single `primary_topic_id` is an OpenAlex **silver** label. The AI/CV corpus is not the universe of all AI research.

## Fixed splits and eligibility

- Training: publication years 2020–2023; validation: 2024; 2025 is a locked test set. No 2025 class frequencies, labels or outcomes may influence catalogue choice, hyperparameters, diagnostics, or this pilot's decision.
- Require nonblank title and abstract. Preserve Unicode; collapse whitespace only. Work IDs identify rows. Detect possible versions using canonical DOI (when present), otherwise a normalized title independent of topic label. A group spanning years is assigned to its earliest eligible year; later-version rows are excluded from this pilot so one research work cannot cross splits. Conflicting primary labels in groups are counted, not silently resolved.
- Selection support is counted **after** text filtering and version-group isolation: at least 120 training and 30 validation works. These are pilot feasibility thresholds, not universal scientific cutoffs. Do not lower them after seeing model metrics.

## Scientific scope review

Review each eligible primary topic's OpenAlex name, available description and primary subfield. Mark `in`, `out`, or `manual_review`. `in` means the named concept principally describes an AI/CV method, model, task, or methodological subarea; an application of AI to an unrelated discipline alone does not qualify. Ambiguous intersections (e.g., imaging applications or generic information systems) are `manual_review` and excluded from the provisional model catalogue until independently reviewed. Do not treat a topic's source subfield membership alone as evidence of semantic fit. Source topic scores are classifier outputs, not confidence probabilities or scientific quality.

Select up to 15 and aim for at least 8 supported `in` topics. If more than 15 qualify, rank by training support (descending), then topic ID (ascending); this tie-break uses no test data. If fewer than 8 qualify, stop the primary catalogue gate and report its failure; only the explicitly marked contingency diagnostic below may run. The catalogue is intentionally bounded and cannot represent all AI/CV publications. Keep out-of-catalogue 2024 records for open-set diagnostics; do not train them as an invented negative class.

**Transparent contingency, not a replacement gate:** After the first training/validation support inspection indicated that eight classes were unlikely, but **before any model was fitted or evaluated**, this contingency was added: if the 8-topic target fails but at least four semantically defensible topics meet the unchanged 120/30 support thresholds, a 4–7-topic *non-confirmatory diagnostic* may be trained to measure silver-label textual separability. It cannot yield a GO verdict for the requested 8–15-topic application. Report the failed primary gate and the smaller experiment separately. This was a post-audit, pre-model amendment, not a fully preregistered primary gate; it does not relax the class-support rule. Subsequent wording clarifications did not change the criteria.

## Model and decision gate

Compare majority and, only if genuine topic descriptions exist, description-similarity baselines with training-only TF-IDF + logistic regression on **2024**. Optional Naive Bayes/SVM may be diagnostic. Select a simple prespecified logistic configuration (`ngram_range=(1,2)`, `min_df=2`, `max_features=50_000`, `C=1`, fixed seed); do not tune on 2025. Primary metric: macro-F1; also report accuracy, weighted-F1, per-class results and class support. For a provisional GO, seek at least a 0.10 absolute macro-F1 gain over the strongest executable baseline, no catastrophic class with zero recall, and plausible but not assumed open-set rejection. Human label validation remains required before claiming semantic correctness or a user-facing classifier. A model that agrees with OpenAlex may still be scientifically wrong.

The scope-review table, exact selected IDs, exclusions and unresolved cases will be stored with the run. Human reviewers have not yet approved this provisional catalogue.
