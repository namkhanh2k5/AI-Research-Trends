# Phase 6 — topic analysis and classification

This is the entry point for RQ6. Phase 6A (five-topic feasibility), Phase 6B
(fourteen-topic validation) and the later integrated ML development are **separate
experiments**, not successive versions of one result. Their original, hashed run
directories remain in place; [artifact_map.json](artifact_map.json) records each
role and path. The [pilot tables](pilot/README.md),
[validation tables](validation/README.md), and
[sample-topic figure](figures/topic_support.png) are together here for
reading; the figure describes the original 12,000-work sample, not the OpenAlex
population.

## Question and label boundary

RQ6 asks how reliable and separable selected OpenAlex primary-topic labels are
for text-based topic understanding. The study's AI/CV primary-subfield frame
contains 2020–2025 articles, reviews and preprints; the original detailed sample
has 12,000 unique works. OpenAlex primary topics are automated **silver** labels.
Agreement with them is not independently established semantic accuracy. Native
topic memberships, custom LLM/Multimodal/RAG text rules and the selected ML
catalogue are different classification layers. Their counts must not be added or
treated as full-population prevalence.

## Development path and evidence

| Stage | Distinct purpose | Measured evidence | Primary detail |
| --- | --- | --- | --- |
| 6A pilot | Pre-2025 support and five-class diagnostic after the 8–15-class gate failed | 955 historical training, 379 2024 validation; 20.2% of 1,873 text-eligible 2024 works in catalogue; SVM macro-F1 .953 on five silver labels | [Pilot report](../PHASE6A_TOPIC_CLASSIFICATION_FEASIBILITY.md), [selection protocol](../../docs/PHASE6_TOPIC_SELECTION_PROTOCOL.md) |
| 6B expansion | Prospectively fixed 14-topic catalogue and separate open-set check | 1,746 training, 689 2024 validation; 36.8% catalogue coverage; closed-set SVM macro-F1 .857; 2024 open-set evaluation: 307/414 (74.2%) inside accepted, 136/710 (19.2%) outside falsely accepted, 287/1,124 (25.5%) end-to-end correct against silver labels | [Validation report](../PHASE6B_FINAL_TOPIC_VALIDATION_REPORT.md), [scope table](validation/scope_review.csv), [decision criteria](../../docs/PHASE6B_DECISION_CRITERIA.md) |
| Integrated RQ6 and final ML development | Version-group isolation, targeted training expansion, frozen model and website assistance | 14-label SVM selected on 2024 development; open-set false acceptance in the later integrated development evaluation is 21.66%, **not** the 6B 19.2% result | [RQ6 analysis](../FINALIZATION_P2_RQ6_TOPIC_LABEL_ANALYSIS.md), [final ML report](../FINALIZATION_P3_FINAL_ML_REPORT.md) |

The 6A and 6B macro-F1 values have **different class universes and evaluation
denominators**. The 6B open-set result and final integrated model result also
have different data and thresholds; they are not interchangeable. The final
system uses a frozen TF-IDF/Linear SVM **assisted** topic-suggestion bundle,
not the 6A or 6B pilot artifact. Its suggestions require explicit user
confirmation. Only title and abstract enter its predictive features; TF-IDF is
fitted on permitted training folds. The integrated targeted ML records are not
added to RQ1–RQ4 population or original-sample estimands.

## Topic scope and human validation

The [frozen catalogue](../../config/phase6b_catalogue.yaml) has 14 selected
OpenAlex IDs. It evolved from a five-topic pilot; the
[expanded-catalogue protocol](../../docs/PHASE6B_EXPANDED_CATALOGUE_PROTOCOL.md)
records the 2020–2024 support criteria and six excluded/uncertain topics. Broad
labels such as T10036/T10028 and cross-domain T10100 can overlap narrower
topics. The [6B aggregate confusion and classwise tables](validation/README.md)
show where the model disagrees with OpenAlex, not where OpenAlex is proved wrong.
Official descriptions were captured in a hashed metadata snapshot, but the
catalogue is a single-researcher provisional scope decision.

The [pilot blind protocol](../../docs/PHASE6_HUMAN_ANNOTATION_GUIDELINES.md),
[6B human-review instructions](../../docs/PHASE6B_HUMAN_REVIEW_INSTRUCTIONS.md)
and [later two-reviewer workflow](../../docs/FINALIZATION_P2_HUMAN_REVIEW.md)
must be read as protocols, not completed human evidence. No genuine independent
two-human semantic validation has been established. The repository subsequently
published historical answer keys and 2025 labels; the 2025 test can no longer
be claimed as an independent sealed holdout in this public snapshot, even where
older time-stamped reports correctly described its earlier sealed state.

## Reproduction and provenance

The canonical 6B run is
`data/analysis/phase6b_topic_validation_20261028_v3/` with manifest SHA-256
`8adeee71c0b37d3e5b85d06360d2d471b72618daf1a4427b023570664bac9c79`.
The 6A pilot v12 and later reproduction have identical non-manifest outputs but
**different** manifests and run identities, so both remain at original paths.
The 6B metadata and integrated RQ6 runs are separate sources. The mapping file
lists their hashes. To verify the 6B run without retraining:

```bash
openalex-verify-topic-run --run-dir data/analysis/phase6b_topic_validation_20261028_v3
```

Use the [repository reproducibility guide](../../docs/REPRODUCIBILITY.md) for
the original sample, integrated model, web package and application. Preserve
all run manifest paths, source hashes and numerical outputs. Future human
ratings must be stored separately from the published research snapshot.
