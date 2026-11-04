# RQ8 — Historical Publication-Venue Discovery Feasibility

Input is a manuscript title and abstract. Output is a **historically evidenced venue shortlist for investigation**, not acceptance prediction, quality ranking or a currently-open call. Temporal index: 2020–2023; evaluation: 2024 development (not an independent final test). Sealed 2025 labels/records were not used. Version groups are disjoint.

The verified integrated dataset contains 7,002 eligible historical training papers and 1,843 2024 development queries. With minimum two historical papers per rankable venue, the common pool contains 3,156 papers, 592 venues (591 journals, **1 conference**). Only 653 of 1843 historical query venues appear in this pool: oracle candidate ceiling **35.4%**. The 2024 development set contains no resolved conference target, so conference ranking is **not evaluated**.

All methods share this identical candidate universe and all 1,843 queries remain in the end-to-end denominator, including missing/unsupported historical venue labels. V1 uses the **frozen title+abstract classifier** only when its threshold is met (806 queries), otherwise falls back to historical popularity; the query's true OpenAlex topic is never used for ranking. V2 fits TF-IDF only on historical text and aggregates the 100 nearest papers; V3 compares query text with historical venue profiles.

| Method | Recall@1 | Recall@3 | Recall@5 | Recall@10 | MRR@10 |
|---|---:|---:|---:|---:|---:|
| v0_popularity | 0.021 | 0.037 | 0.049 | 0.075 | 0.034 |
| v1_frozen_topic_frequency | 0.026 | 0.044 | 0.060 | 0.086 | 0.041 |
| v2_tfidf_papers | 0.039 | 0.081 | 0.107 | 0.149 | 0.068 |
| v3_venue_profiles | 0.040 | 0.092 | 0.123 | 0.154 | 0.073 |


V3 improves Recall@5 over popularity by 0.073 absolute (0.061–0.086 paired-bootstrap 95% development interval, seed 20261104). However, **12.3%** end-to-end Recall@5 is low; conditional Recall@5 among the 653 represented historical venues is **34.6%**. Historical venue is only one observed publication outcome; another venue could also be reasonable.

Candidate ceiling by minimum historical support (same 2024 denominator, diagnostic only): threshold 1 = 826/1843 (44.8%); 2 = 653/1843 (35.4%); 3 = 551/1843 (29.9%); 5 = 451/1843 (24.5%); 10 = 332/1843 (18.0%). At threshold 1, most extra venues are singletons, weakening evidence per suggestion. More data might help candidate coverage, but may not fix venue ambiguity or ranking.

## Failure and support analysis

| Historical support of observed venue | 2024 queries | Candidate coverage | V3 Recall@5 |
|---|---:|---:|---:|
| 0 | 1190 | 0.0% | 0.0% |
| 2 | 102 | 100.0% | 15.7% |
| 3-4 | 100 | 100.0% | 11.0% |
| 5-9 | 119 | 100.0% | 18.5% |
| 10+ | 332 | 100.0% | 53.3% |


The observed venue is missing or outside the candidate pool for 1190 of 1843 queries. Among 2024 development papers, 481 have no resolved journal/conference target; the other 1362 resolve to journals. **There is no resolved conference target**, so this pilot cannot justify conference recommendations. Popularity favors large historical journals; thin-tail venues are poorly represented. Provider naming, publication-year differences, evolving venue scope and OpenAlex source taxonomy remain unresolved. Group-specific topic counts are recorded in the local `retrieval_breakdown.json`, not interpreted as population prevalence.

The local `venue_retrieval_index.joblib` powers a **no-network CLI**; it does not imply that venue aims, scope, APCs, deadlines, indexing, or acceptance likelihood are known. Topic routing uses OpenAlex silver labels and must not be presented as validated human truth. Manual topic selection is available. Abstract availability in this eligible subset is 100% by construction; missing-abstract papers remain in the inventory but not the query benchmark. Subgroup metrics and predictions are local, Git-ignored (`retrieval_breakdown.json`, `venue_benchmark_predictions.parquet`).

**Decision: CONDITIONAL GO only for a narrowly scoped journal discovery research prototype with abstention and explicit historical-evidence warnings; NO-GO for a broad journal-and-conference recommender or acceptance predictor.** An independently judged relevance study and more historical journal support are needed before user-facing claims.
