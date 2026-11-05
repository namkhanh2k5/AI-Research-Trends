# Project overview and research boundaries

This undergraduate Data Science project studies the **OpenAlex-defined AI/CV
research landscape**. Its complete-year observation window is 2020-01-01 to
2025-12-31; eligible work types are article, review and preprint; the primary
OpenAlex topic must belong to subfield 1702 (AI) or 1707 (Computer Vision and
Pattern Recognition). Primary estimates exclude retractions. This is not all
global AI research. The unit is one canonical OpenAlex Work ID; authorships,
affiliations, topics and references are bridge relationships, not additional
papers. The [original question definitions](RESEARCH_QUESTIONS.md) remain as
the historical pre-analysis protocol.

| Question | Evidence and interpretation |
| --- | --- |
| RQ1 — topic/publication evolution | Timestamped, complete OpenAlex year and native-topic aggregates for the defined corpus; overlapping topics are not additive. |
| RQ2 — citation impact | Original 12,000-work detailed sample, age/field/type context and FWCI availability; raw citations are not scientific quality. |
| RQ3 — Open Access | Descriptive and adjusted **associations** in the original sample, not causal effects. |
| RQ4 — collaboration | Distinct institution and affiliation-country bridges from the original sample; missing affiliations do not mean no collaboration. |
| RQ5 — reference network | Historical candidate-pool feasibility and citation-edge diagnostics; the citation recommender was not adopted as the main ML task. |
| RQ6 — topic labels | Scope, ambiguity, silver-label classification and open-set limitations; independent human semantic validity remains pending. |

The original population snapshot is 937,493 non-retracted works (942,825 with
retractions included). The proportionally year-stratified detailed sample has
12,000 unique works. Targeted historical ML expansion is a **third dataset**,
used only for ML training. API sampling uniformity was not established, so
nominal sample weights are not guaranteed inverse inclusion probabilities.
Source values and exact timestamps are in the [collection report](../reports/research/phase2/PHASE2_COLLECTION_REPORT.md)
and [sample quality report](../reports/research/phase3/PHASE3_DATA_QUALITY_REPORT.md); do not
hardcode these snapshot counts in processing logic.

The [Phase 4 report](../reports/research/phase4/PHASE4_ANALYSIS_REPORT.md) covers RQ1–RQ4,
the [Phase 5 decision](../reports/research/phase5/PHASE5_FINAL_DECISION.md) covers RQ5, and
the [unified Phase 6 report](../reports/phase6/PHASE6_REPORT.md) covers RQ6.
The project supplies a local Streamlit explorer and a frozen title/abstract
TF-IDF + Linear SVM topic **suggestion** model. Model agreement with OpenAlex
labels is not human-validated topic truth. The historical 2025 labels and
answer keys were later published, so this public snapshot cannot claim an
independently sealed final test. Public hosting and redistribution rights
remain separate decisions.
