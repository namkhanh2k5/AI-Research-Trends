# Phase 5 — Bounded literature-retrieval diagnostic

This is a small proxy test, **not** the performance forecast for a full literature recommender. The Git-ignored measurement runs are `data/analysis/phase5_candidate_enrichment_20261028_v2/` and `data/analysis/phase5_retrieval_diagnostic_20261028_v4/`. The latter completed at 2026-10-28 03:22:27 UTC; both manifests contain input/output SHA-256 values. No supervised model was trained.

Selection CSV SHA-256: `2c98726d4ef8e65cde5de0bc8f5f6f9f813097033d8fb3dcf3c18fccfcb94989`; extracted metadata CSV SHA-256: `307b0efa1b67c99b6ae4710f61c45968e48b84aee1de2839706aeeb8630de15c`. These hashes identify local evidence, not downloadable data; the raw API bodies and candidate CSVs are intentionally excluded from Git.

## Candidate universe and leakage boundary

The only graph feature is popularity: distinct 2020–2022 sampled citing works per referenced ID. The enrichment list was fixed **before** examining 2023 query references: 900 highest-frequency candidates and a seeded audit sample of 100 frequency-one candidates, all from the expanded historical pool. No 2023+ citing edge influences selection or popularity. The query input is title plus abstract; **all** of each query's observed references are hidden from features and used only as retrospective proxy positives for evaluation. TF-IDF (word unigrams/bigrams, `min_df=2`) was fitted on candidate title/abstract text only. Fusion uses reciprocal rank `1/(60 + rank)` from popularity and text scores. No citation edge, hidden reference or 2023 query text is used to fit the vectorizer.

OpenAlex returned 973/1,000 selected works; 27 returned HTTP 404. The verifier checked all **1,000 raw response hashes**, including 404 bodies. Among 973 returned records, 973 have titles, 760 abstracts, 972 exact publication dates, 915 DOIs, 973 OA-status values, and 973 landing-page URLs. All 972 nonmissing dates agree with publication year. These completeness percentages describe this **training-frequency-selected subset**, not the entire 12,019-ID ≥2 historical pool. Notably, 16 returned candidates currently have publication year later than 2022 even though their IDs were cited by a 2020–2022 sampled work. OpenAlex is retrospective and mutable; a historical citation edge does not by itself certify metadata chronology.

The `/rate-limit` check reported 10,000 daily credits available before enrichment and 9,996 afterward (USD 0.0004 used), consistent with free singleton lookups and four charged requests from the separate opt-in live integration probe. There were no quota or retry-exhaustion failures in the completed v2 enrichment. An earlier v1 attempt stopped after ten retrieved records on a 404; its incomplete manifest and raw evidence were retained, and v2 explicitly distinguished unavailable IDs from transient API failures. The key is neither printed nor stored in these outputs.

## Temporal overlap, 2023 held-out queries

The evaluation set is the same 909 eligible 2023 queries with 37,980 unique observed reference edges. The selected 1,000 IDs overlap 2,822 of those edges at ID level (7.43%). The 973 retrievable IDs overlap 2,777 (7.31%). On the 2,777 enriched-subset overlaps:

| Relationship to each query's exact publication date | Overlapping edges |
|---|---:|
| Candidate published in an earlier calendar year | 2,670 |
| Same calendar year, candidate date not later than query date | 38 |
| Candidate date later than query date | 64 |
| Candidate date missing or invalid | 5 |

The conservative earlier-year overlap is 2,670/37,980 (7.03% of all observed edges); exact-date nonfuture overlap is 2,708/37,980 (7.13%). Same-year dates are reported separately because recorded publication dates need not capture when a paper became discoverable. Unknown dates are not treated as valid. In the full expanded ≥2 pool, 6,347/37,980 edges overlap by ID, but only 2,769 overlapping edges have enrichment metadata; 3,578 remain unenriched. Within the 2,769 enriched ≥2-pool overlaps, 2,662 are earlier-year, 38 same-year nonfuture, 64 later-date, and 5 unknown. Do **not** extrapolate the selected subset's date-valid percentage to the remaining pool.

## Baseline ranking results

Every method ranks the same per-query universe of **959** title-bearing candidates with known publication dates no later than the query's exact date; IDs without dates, future-dated IDs, and the query's own ID are excluded. Each method is evaluated against *all* observed references for each of the 909 queries, so zero-coverage queries remain in end-to-end denominators. These are historical citation-recovery proxies, not human relevance labels.

| Method | Mean / median date-valid subset coverage | Mean end-to-end Recall@20 | Mean end-to-end Recall@50 | Mean conditional Recall@20* | Queries with ≥1 hit@20 |
|---|---:|---:|---:|---:|---:|
| Distinct historical-citer popularity | 7.18% / 3.70% | 1.55% | 2.36% | 18.51% | 269/909 (29.6%) |
| TF-IDF title/abstract cosine | 7.18% / 3.70% | 1.84% | 2.51% | 27.65% | 338/909 (37.2%) |
| Reciprocal-rank fusion | 7.18% / 3.70% | **2.53%** | **3.68%** | 34.97% | 398/909 (43.8%) |

\* Conditional Recall@20 averages only the 568 queries with at least one observed reference in the date-valid candidate subset; 341/909 have no such positive. Candidate-generation Recall@20/50 here is the same top-K observed-reference recovery as end-to-end Recall@K because the candidate set is fixed and all references are hidden. The relatively larger conditional number does not rescue the low end-to-end ceiling. The combined scoring and sorting of **all three** methods took a median 3.70 ms/query and P90 6.85 ms/query in this run, excluding loading, TF-IDF fitting, API access and any application layer. This hardware-dependent timing is not a production latency claim.

The full expanded historical pool's 12.1% median *ID overlap* and this bounded subset's 3.7% median *date-valid overlap* describe different candidate universes and cannot be compared as a model improvement or regression. The subset is deliberately nonrandom and favors popular works; the remaining pool could have different metadata completeness and chronology. No human relevance judgments, stable historical OpenAlex snapshot, supervised evaluation or user study exists. See the [coverage reassessment](PHASE5_COVERAGE_REASSESSMENT.md) and [final decision](PHASE5_FINAL_DECISION.md).
