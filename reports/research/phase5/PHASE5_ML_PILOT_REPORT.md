# Phase 5 ML pilot decision — REVISE

No supervised ranking experiment or inference recommender was run. The decision
was made **before model comparison** from the verified G1/G2 audit: the 2023
median ID-level pool overlap is 10.0% at ≥2 historical citers,
and only 727/289,110 edges have candidate
publication dates available in the local sample. Candidate-generation recall,
Recall@10/20, nDCG@20, MRR, warm/cold-start and latency are **not measured**.
Reporting model scores now would hide the candidate-pool and temporal-validity
bottlenecks.

| Method | Recall@20 | nDCG@20 | MRR | Latency | Reason |
|---|---|---|---|---|---|
| Global Popularity | Not run | Not run | Not run | Not run | G2/temporal-metadata gate failed |
| Subarea Popularity | Not run | Not run | Not run | Not run | G2/temporal-metadata gate failed |
| BM25 | Not run | Not run | Not run | Not run | G2/temporal-metadata gate failed |
| Co-citation | Not run | Not run | Not run | Not run | G2/temporal-metadata gate failed |
| Rank Fusion | Not run | Not run | Not run | Not run | G2/temporal-metadata gate failed |
| Logistic Regression | Not run | Not run | Not run | Not run | G2/temporal-metadata gate failed |
| Random Forest | Not run | Not run | Not run | Not run | G2/temporal-metadata gate failed |
| LightGBM Classifier | Not run | Not run | Not run | Not run | G2/temporal-metadata gate failed |
| LambdaMART | Not run | Not run | Not run | Not run | G2/temporal-metadata gate failed |

The code provides tested, deterministic eligibility, historical pool construction,
leave-one-query-out popularity, visible/hidden reference splitting and implicit
negative sampling primitives for a later controlled experiment. An uncited candidate
is unobserved, not human-confirmed irrelevant. Historical citation recovery is at
most a proxy for relevance; no human evaluation or citation-necessity claim exists.
No saved model, vectorizer, candidate index or website was created.

Next: a small separate historical-citing-work expansion and targeted candidate-date
enrichment, followed by a new gate audit. Only if coverage and temporal validity
improve should the team fit BM25 and leakage-safe ranking baselines, then compare
Logistic Regression/other models on query-disjoint temporal folds.
