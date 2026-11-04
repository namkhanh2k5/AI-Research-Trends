# Original-sample textual paper discovery

This is a **lexical content-similarity search**, not the RQ5 citation-network recommender, a plagiarism/novelty detector, or a verified ranking of the best papers. It uses only the original 12,000-work OpenAlex analytical sample. The targeted topic-ML expansion, 2025 test labels and OpenAlex API are not used. It does not estimate population prevalence.

## Contract and eligibility

Input is a descriptive title of at least five words/20 characters and an optional abstract. A supplied abstract must have at least eight words/50 characters; invalid input is rejected separately from a classifier's valid-but-low-margin `no_confident_match` status. Search returns up to 20 papers with Work ID, title, year, DOI if present, work type, primary OpenAlex topic, observed citation count, text coverage and cosine score. Year range, **primary** topic and work type can be filtered. The CLI can exclude an existing Work ID from its own results. Results with zero lexical overlap are omitted. Ties break by canonical Work ID. Metadata filters restrict the candidate set; they do not alter similarity scores or promote highly cited papers.

The builder requires the completed Phase 3 works checksum and the verified existing web package. A work must have a nonmissing title with at least five whitespace-separated words and 20 characters. Abstracts with fewer than eight words are treated as unavailable for retrieval. Exact repeated DOIs are deduplicated first, followed by exact case-folded, whitespace-normalized title+abstract duplicates; ties use earliest publication date then Work ID. Fuzzy near-duplicate/version detection is **not** claimed. Original Phase 3 files are never changed. The resulting package retains display metadata but does not copy paper abstracts.

Title is repeated twice when constructing the text representation, then the abstract is appended if usable. TF-IDF uses lowercase tokenization, English stop words, word unigrams/bigrams, `min_df=2`, at most 50,000 features, sublinear term frequency and float32 values. Non-English text is retained, but the English-centric vocabulary can underperform for it. A fitted vocabulary/IDF JSON and a sparse CSR matrix are saved; no dense all-pairs matrix or runtime download is used. The JSON avoids executable pickle and was byte-identical on two full rebuilds in the tested environment. `papers.parquet`, `matrix.npz` and `vectorizer.json` each have recorded SHA-256 and size. The manifest records source hashes, configuration, eligibility counts, shape, and build time. The index is immutable: an existing output path is refused, and build stages in a temporary sibling directory before rename.

Default search excludes title-only indexed records, because their cosine scores are not directly comparable with title+abstract records. The app offers an explicit opt-in to include them and labels their coverage. This means 11,558 works are indexed but 9,075 are default-searchable. The local index is Git-ignored to avoid duplicating research text/binaries; a fresh clone can rebuild it from retained Git LFS works. `AI_TRENDS_DISCOVERY_INDEX` can override the runtime index path. The app verifies the package before loading it and caches it per process; it never silently rebuilds an absent/corrupt index.

## Reproduce from repository root

```bash
git lfs pull --include="data/processed/openalex_stratified/stratified_20261019T155909Z/works.parquet,data/analysis/finalization_p2_web_data_20261101_v3/paper_index.parquet"
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev,web,deliverables]"
openalex-paper-discovery build
openalex-paper-discovery verify \
  --works data/processed/openalex_stratified/stratified_20261019T155909Z/works.parquet \
  --web-dir data/analysis/finalization_p2_web_data_20261101_v3
openalex-paper-discovery search --title "Neural translation with multilingual attention models" --top-k 5
streamlit run dashboard/app.py --server.address 127.0.0.1
```

Use a new versioned `--output-dir` for a new build. `verify` may omit source paths when only the portable index is available, but specifying both paths also compares the current source hashes to those recorded at build time. Checksums detect accidental corruption relative to the local manifest; they are not signatures proving authenticity against a malicious replacement of both manifest and files. Source licensing/redistribution and public hosting require separate review.

## Evaluation boundary

The deterministic tests cover input errors, exact/near text ranking, missing abstracts, duplicate IDs, filtering, self-exclusion, ties/ordering, tampering and rebuild equality. Real-data diagnostics are in [the technical evaluation](../reports/PAPER_DISCOVERY_TECHNICAL_EVALUATION.md). The examples there use synthetic queries and record retrieved IDs only; no paper was independently relevance-graded. Consequently Precision@K, Recall@K, MRR and nDCG are **not verified**. A bounded future human study could select independent query descriptions, have two reviewers grade each returned paper 2 (high), 1 (partial), or 0 (irrelevant), blind to rank/method, reconcile disagreements, then report metrics with query-level uncertainty. Do not use RQ5 citation-ID overlap as a relevance label for this text search.
