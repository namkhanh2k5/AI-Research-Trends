# RQ5 exploratory extension and literature-discovery decision gate

**RQ5:** What prior literature does sampled AI/CV research build on, and how
concentrated, how old, and how primary-subfield-specific is that observed
knowledge base?

This extends, rather than changes, the original RQ1–RQ4. The unit for reference
availability is a sampled citing work. The unit for citation concentration is a
unique referenced Work ID and its number of distinct citing works **within the
sample**. Neither is the OpenAlex population or global citation impact.

## Prespecified pilot decisions

G1 query eligibility requires a nonblank title, an abstract with at least 50
characters and eight whitespace-separated words, at least ten matched canonical
OpenAlex references, and a valid publication date consistent with year. The
5/10/15-reference thresholds are sensitivity checks. An OpenAlex empty reference
list is reported separately from missing; neither proves the work cites nothing.

G2 uses eligible 2020–2022 works as historical citers, eligible 2023 works as
evaluation queries, and candidate IDs cited by at least two **distinct**
historical citers. Frequency thresholds one and three and nested fractions of
the historical queries are sensitivity checks. Every query denominator is its
unique matched reference IDs. Pool coverage is simple ID overlap with this
historical universe; it is **not** candidate-generation recall. Candidate dates
are checked when locally available. Unknown dates prevent a fully time-valid
coverage claim. The provisional 40% median overlap threshold is a decision aid,
not a universal scientific criterion.

No supervised training, candidate-generation comparison or inference interface
should be claimed if the gate fails. If the gate later passes, use query-disjoint
temporal folds, fit text vectorizers on permitted training data only, construct
popularity/co-citation from historical edges, remove each training query's own
complete reference list from its graph features, and separate given from hidden
references. Unknown citations are implicit unobserved interactions, never
human-verified negatives. Duplicate versions and retrospective OpenAlex metadata
must be audited before any practical recommendation claim.

The executed result is [REVISE](../reports/PHASE5_FEASIBILITY_REPORT.md). The
current sample can support reference EDA, but the ID-level candidate pool and
publication-date metadata are too limited for a defensible supervised pilot.
The [RQ5 report](../reports/PHASE5_REFERENCE_EDA_REPORT.md) and
[ML decision report](../reports/PHASE5_ML_PILOT_REPORT.md) state measured and
unmeasured quantities separately. No new OpenAlex API requests were made.

## Final bounded follow-up (2026-10-28)

The paragraph above records the **first** audit and is retained as historical
methodology, not the final gate. The follow-up used all historical edge-bearing
2020–2022 sampled works as citers, varied distinct-citer thresholds 1/2/3,
repeated five seeded pool-growth subsamples, and separately enriched at most
1,000 candidates selected from 2020–2022 frequency alone. A title/abstract-only
diagnostic hid every 2023 query reference from features. See the
[coverage reassessment](../reports/PHASE5_COVERAGE_REASSESSMENT.md),
[retrieval diagnostic](../reports/PHASE5_RETRIEVAL_DIAGNOSTIC.md), and
[final NO-GO decision](../reports/PHASE5_FINAL_DECISION.md). This result does
not erase the exploratory value of RQ5; it redirects the main supervised ML
component toward an independently audited topic-classification task.
