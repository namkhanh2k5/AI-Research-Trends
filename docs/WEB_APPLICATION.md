# Local research explorer and paper discovery

The local Streamlit app has six pages: Home, Research Landscape (RQ1–RQ4),
Topic Explorer, Classify My Research, Paper Explorer and Methodology/Model
Evaluation. Start it with `streamlit run dashboard/app.py --server.address
127.0.0.1`. It is a research prototype, not a public hosted service.

Browser → `dashboard/app.py` → `ai_research_trends.web.service` → verified
`ResearchData`/web package. Only “Suggest topics” loads the trusted frozen
TF-IDF/Linear SVM bundle on demand. Manual Topic Explorer needs neither the
model nor a live OpenAlex request. “Find similar papers” loads a separately
built, checksum-verified TF-IDF/cosine index (original sample, with optional
validated recent application papers). Neither normal
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
  up to 20 lexically similar indexed papers, with optional year,
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
openalex-build-web-data verify data/artifacts/web/topic_explorer
openalex-paper-discovery build
openalex-paper-discovery verify --works data/processed/openalex_stratified/stratified_20261019T155909Z/works.parquet --web-dir data/artifacts/web/topic_explorer
openalex-paper-discovery search --title "Neural translation with multilingual attention models" --top-k 5
streamlit run dashboard/app.py --server.address 127.0.0.1
```

`AI_TRENDS_WEB_DATA`, `AI_TRENDS_MODEL` and `AI_TRENDS_DISCOVERY_INDEX`
override the checked defaults in `config/application.yaml`. The reviewer UI requires a separate localhost process,
for example `AI_TRENDS_REVIEWER=reviewer_a streamlit run dashboard/reviewer.py
--server.address 127.0.0.1`; give each real reviewer only their own package.
The app needs no `.env` key. For deployment and rights cautions see the
[deployment guide](DEPLOYMENT_GUIDE.md).

`AI_TRENDS_APPLICATION_SYNC_ROOT` can point the app to a nondefault sync
store created with the same `openalex-sync-application --root` value. Set it
for both the scheduler and the web process when changing storage location.

## Optional OpenAlex application sync

The application has a separate, mutable `data/application/openalex_sync/`
store. It does not alter the original 2020–2025 sample, population aggregates,
Phase 3/4 outputs, evaluation splits, or the frozen SVM. Paper Explorer and
research charts remain original-sample / original-snapshot views; only
similarity-based Paper Discovery can include recent synced papers. The sidebar
and discovery page show the last successful sync time (not publication time).
If no valid sync exists, discovery falls back to the original index.

The fallback queries OpenAlex works with publication dates in a bounded 2026+
window, the same approved primary AI/CV subfields (1702/1707), article/review/
preprint types, and explicit non-retracted status. By default it scans three
days and caps the window at 3,000 works; an oversized window fails before
publishing. Use explicit `--from-date` and `--to-date` for a bounded manual
backfill. The 2020–2025 research corpus definition is not changed.

OpenAlex [documents](https://help.openalex.org/api/filtering/) that
`from_created_date`, `from_updated_date` and their `to_` counterparts require
Member+/Partner or older Premium/Institutional access. The free publication-date
fallback cannot reliably find works with old publication dates newly indexed
today, metadata updates outside the rolling window, merges or deletions. The
manifest distinguishes *newly observed IDs* from *observed metadata updates*;
it cannot certify which IDs are newly indexed globally. An in-window work may
have been published earlier than its sync timestamp. Counts from this mutable
store must not be interpreted as population publication trends.

Prerequisites: restore the original works LFS file and web data package, build
the original index, and set `OPENALEX_API_KEY` in ignored `.env`. No API key is
needed for web browsing. Run from the repository root:

```bash
openalex-sync-application --lookback-days 3 --max-records 3000
openalex-sync-application --lookback-days 3 --max-records 3000 --execute
openalex-sync-application --resume sync_YYYYMMDDTHHMMSSZ_XXXXXXXX --max-records 3000 --execute
```

The default command only previews its window/filter. `--execute` uses the
existing retry/rate-limit client and cursor pagination (100 records per page).
Each response body is persisted atomically under `runs/<run-id>/raw_pages/`
with a SHA-256 checkpoint. On resume every prior page's ordered Work IDs,
cursor and total count are probed again; a mismatch stops the run and preserves
the old raw evidence. This is a practical consistency probe, **not** an
OpenAlex snapshot guarantee: metadata or unseen pages can still change.
Uncheckpointed orphan pages are quarantined. No published application state is
changed until all records validate, the cumulative Parquet store is hashed,
and a complete TF-IDF index is built and verified. The atomic `state.json`
pointer selects the last working index. If the API or index build fails, the
web app keeps using the last validated index; inspect the incomplete manifest
and resume or start a new run after a membership mismatch. Do not edit a
completed run. A lock prevents concurrent local sync jobs.

On a persistent Ubuntu host, one simple daily schedule is cron (set the
absolute checkout path and Python environment to match your installation):

```cron
15 3 * * * cd /absolute/path/to/AI-Research-Trends && /absolute/path/to/AI-Research-Trends/.venv/bin/openalex-sync-application --lookback-days 3 --max-records 3000 --execute >> /absolute/path/to/sync.log 2>&1
```

Run manually first, check `data/application/openalex_sync/state.json` and the
run manifest, and monitor quota/disk. Cron needs a continuously available host
and secure local `.env`; GitHub Actions runners do not persist this ignored
store between executions. Current web-data and model artifacts also require
rights review before any public deployment. Rebuilding the TF-IDF index updates
corpus-wide IDF but does not retrain the 14-topic SVM; evaluate vocabulary and
human-reviewed performance drift before any separately approved model update.
