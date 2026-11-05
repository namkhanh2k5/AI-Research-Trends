# Local research explorer and paper discovery

The local Streamlit app has six pages: Home, Research Landscape (RQ1–RQ4),
Topic Explorer, Classify My Research, Paper Explorer and Methodology/Model
Evaluation. Start it with `streamlit run dashboard/app.py --server.address
127.0.0.1`. It is a research prototype, not a public hosted service.

Browser → `dashboard/app.py` → `ai_research_trends.web.service` → verified
`ResearchData`/web package. Only “Suggest topics” loads the trusted frozen
TF-IDF/Linear SVM bundle on demand. Manual Topic Explorer needs neither the
model nor a live OpenAlex request. “Find similar papers” loads a separately
built, checksum-verified original-sample TF-IDF/cosine index. Neither normal
browsing nor inference calls OpenAlex. A separate local-only reviewer UI lives
at `dashboard/reviewer.py` and must never be exposed to public users.

## User workflow

- Home and Research Landscape distinguish complete defined-population RQ1
  counts from original-sample RQ2–RQ4 results. Topic Briefs show official
  descriptions, population trends and sample context for the selected topic.
- Classification requires a nonblank title and an abstract of at least 50
  characters/eight words. Top-three topic suggestions and raw SVM score-strength
  statuses are **not calibrated probabilities**. `no_confident_match` means
  possible absence from fourteen chosen topics, not from all AI. A person must
  confirm or manually override. Draft edits invalidate previous suggestions.
- Paper Explorer filters and paginates only the original 12,000 sampled works.
  Literal keyword search is distinct from similarity-based discovery.
- Paper Discovery requires a descriptive title of at least five words/20
  characters; a supplied abstract needs eight words/50 characters. It returns
  up to 20 lexically similar original-sample papers, with optional year,
  primary-topic and work-type filters. Unknown/zero overlap is omitted; ties
  break by Work ID. The indexed sample had 11,558 eligible papers; only 9,075
  have usable title **and** abstract for default comparisons. Title-only
  candidates are opt-in because their scores are not directly comparable.

The discovery builder checks the Phase 3 works and web-package source hashes,
deduplicates exact DOI and normalized title/abstract matches, repeats the title
twice, and fits word unigram/bigram TF-IDF (`min_df=2`, ≤50,000 features,
sublinear TF, English stop words, float32). It saves a sparse matrix, portable
vocabulary/IDF JSON and display metadata, with SHA-256 and sizes in an immutable
manifest. It is Git-ignored and rebuildable; no full-text paper collection,
live API call or automatic app-start rebuild is performed. Non-English content
is retained but English-centric vocabulary can underperform. Search ranking
is not a relevance, novelty or plagiarism judgement. No independent human
Precision@K, Recall@K, MRR or nDCG has been established; see the
[technical evaluation](../reports/application/PAPER_DISCOVERY_TECHNICAL_EVALUATION.md).

## Build and inspect

After the [LFS restoration and installation](REPRODUCIBILITY.md):

```bash
openalex-build-web-data verify data/analysis/finalization_p2_web_data_20261101_v3
openalex-paper-discovery build
openalex-paper-discovery verify --works data/processed/openalex_stratified/stratified_20261019T155909Z/works.parquet --web-dir data/analysis/finalization_p2_web_data_20261101_v3
openalex-paper-discovery search --title "Neural translation with multilingual attention models" --top-k 5
streamlit run dashboard/app.py --server.address 127.0.0.1
```

`AI_TRENDS_WEB_DATA`, `AI_TRENDS_MODEL` and `AI_TRENDS_DISCOVERY_INDEX`
override local paths. The reviewer UI requires a separate localhost process,
for example `AI_TRENDS_REVIEWER=reviewer_a streamlit run dashboard/reviewer.py
--server.address 127.0.0.1`; give each real reviewer only their own package.
The app needs no `.env` key. For deployment and rights cautions see the
[deployment guide](DEPLOYMENT_GUIDE.md).
