# Paper-discovery technical evaluation (original sample)

This report is a local functionality and reproducibility check, **not** a human relevance evaluation. The new retrieval feature is separate from RQ5's rejected historical citation recommender. The original Phase 3 `works.parquet` checksum was `9318c456d916b8c9a35b0a3c86a829a92347083357693593e743abb0253264d4`; the existing web manifest checksum was `a3378abf249b567cf34893cefa7d56d6291577a8e9c9ce5ec85a31640f13c15d`. Both were checked before building. The frozen topic-model code and bundle were not modified.

| Measure | Observed |
|---|---:|
| Original sample works | 12,000 |
| Excluded for insufficient title | 439 |
| Exact DOI duplicates removed | 0 |
| Exact normalized text duplicates removed | 3 |
| Indexed unique works | 11,558 (96.3% of source) |
| Usable title+abstract; default-searchable | 9,075 (75.6% of source) |
| Title-only; opt-in | 2,483 |
| TF-IDF shape / nonzeros | 11,558 × 50,000 / 1,071,779 |
| Index artifact bytes, including manifest | 8,962,975 (~8.55 MiB) |

Two independent full builds produced identical SHA-256 values for all three content artifacts: `matrix.npz` `226fd3292e45594c58874bce9b1b138013cc1914219c1ab0a61f405e2830c832`; `papers.parquet` `ad5f8310d261af41ea5f7485f974dcca4377dd02581f7d0dd9cc9f0d9123955c`; `vectorizer.json` `b0c023546a71d85d7bf798cc0be45fb367f104f18687f85e4960dc3d79492079`. Manifest creation times differ by design. In one Python 3.12.3 process with scikit-learn 1.9.1 and 50 original-sample title/abstract queries, median search latency was **101.0 ms**, observed p95 **110.1 ms**. Process RSS rose from 187.9 to 286.4 MiB when loading the index (98.5 MiB delta); this includes Python/Pandas/scikit-learn object overhead, not just disk file size. These are local diagnostics, not a service-level guarantee.

Three *synthetic, non-test* example query themes and top-three Work IDs under default full-text search:

| Synthetic theme | Ranked Work IDs | Cosine scores |
|---|---|---|
| Medical image segmentation | W3123982987, W7220095509, W3012260740 | .341, .265, .256 |
| Multilingual neural translation | W4307203459, W4384263525, W4213075978 | .356, .345, .324 |
| Robotic reinforcement learning | W3175580674, W7216041361, W4417233168 | .226, .196, .194 |

These IDs and scores demonstrate functioning lexical retrieval only. Their scientific relevance has **not** been judged. A high cosine value may reflect shared words, generic methods, or title length; a low value does not prove irrelevance. Missing abstracts create coverage bias. Exact duplicate removal does not establish version-group deduplication. The local corpus is only the original sampled OpenAlex frame, not all published AI/CV papers. Citation counts are displayed as metadata and never affect rank. No independent human relevance labels exist; Precision@K/Recall@K/MRR/nDCG are **NOT VERIFIED**. Topic-classifier margins are separately model-specific and are not comparable with cosine scores.

The frozen 2024 development open-set evidence was re-read from the verified published evidence source: 738 calibration works, 1,105 evaluation works (408 in-catalogue, 697 outside), SVM threshold `−0.22227267687798036`, 83.09% in-catalogue acceptance, 21.66% outside false acceptance, AUROC .8919 and 28.33% correct accepted placement over all eligible evaluation works. These are development/silver-label measures, not 2025 final or human-semantic results. The UI therefore never treats a score-strength status as an automatic topic assignment.

Reproduce the local package check with `openalex-paper-discovery verify --works data/processed/openalex_stratified/stratified_20261019T155909Z/works.parquet --web-dir data/analysis/finalization_p2_web_data_20261101_v3`. Browser and full-suite results are reported in the final task handoff; no OpenAlex request or model retraining was performed.

Final local checks in the fresh clone: `python -m compileall -q src dashboard deliverables tests` passed; `python -m pip check` reported no broken requirements; `python -m pytest -q -ra -o addopts=''` reported **242 passed, 9 skipped** (seven opt-in Chrome tests, one live OpenAlex probe, one absent private development aggregate). The separately opted-in Chrome suite reported **7 passed** at 1440×900 and 1280×800, including manual topic confirmation, `no_confident_match`, model-unavailable behavior and paper discovery without a classifier result. The original web-data verifier reported 22/22 outputs valid, 12,000 papers and 14 Topic Briefs; the frozen model loader accepted its existing manifest and threshold. These checks establish mechanics, not human topic or paper relevance correctness.
