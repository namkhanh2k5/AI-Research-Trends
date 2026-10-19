# Data Collection and Sampling Strategy

## 1. Confirmed population estimand

Phase 1 fixes the population as the **defined AI/CV primary-subfield corpus**:

```text
from_publication_date:2020-01-01,
to_publication_date:2025-12-31,
primary_topic.subfield.id:1702|1707,
type:article|review|preprint,
is_retracted:false
```

The dates cover six complete calendar years. Subfields 1702 and 1707 are
Artificial Intelligence and Computer Vision and Pattern Recognition. Membership
is determined by the subfield of the work's single `primary_topic`; a secondary
AI topic does not place an otherwise out-of-frame work in the population.

This is not “all global AI research.” It excludes cross-disciplinary applications
whose primary contribution OpenAlex assigns outside 1702/1707. That exclusion is
intentional: the alternative “any AI method” boundary has no complete, stable
topic list and is vulnerable to incidental method mentions. All reports must use
the qualified corpus name above.

The final clause defines the **primary estimand**. A parallel aggregate removes
only `is_retracted:false` and is labeled the all-work sensitivity population.
Raw data are never altered. The configuration loader rejects changes to these
boundaries, and tests assert both exact aggregate filters.

## 2. Two separate data products

### A. Population statistics

Use OpenAlex aggregate responses for counts that the API can return completely.
The annual corpus series uses `group_by=publication_year`; each focused
native-topic series adds only `topics.id:<verified IDs>` to either the primary
non-retracted or all-work filter.
Store the response bytes, parameters, retrieval time, count, and SHA-256 hash.

These counts are the source for publication volume and growth. A topic-balanced
detailed sample would intentionally alter inclusion probabilities and therefore
must never estimate publication distributions without correct design weights.

### B. Detailed research dataset

Use a deterministic server-side sample of work records for missingness,
collaboration, impact, NLP, and later modeling. It is not a census. Its manifest
records the seed, exact filter, requested/raw/unique counts, page hashes, and a
completion flag. Canonical Work ID is the unit of analysis and deduplication key.

## 3. Two non-equivalent analytical layers

### Layer A — OpenAlex-native taxonomy

OpenAlex organizes topics under Domain → Field → Subfield → Topic. `primary_topic`
is one inferred topic per work and defines the population boundary. The `topics`
array contains up to three inferred memberships and therefore overlaps.

Configured native lenses use only `topics.id`: NLP (T10181/T10028), computer
vision (T10036), reinforcement learning (T10462), explainable AI (T12026), and
Multimodal Machine Learning Applications (T11714). Each mapping is partial and
model-inferred. Native counts can overlap and cannot be summed.

### Layer B — custom emerging technologies

Large Language Models, Multimodal AI, and Retrieval-Augmented Generation are
project labels applied to normalized title plus reconstructed abstract using the
versioned regular-expression rule groups in `config/topics.yaml`. A category is
the OR of its rule groups; every expression in one `all_of` group must match.

These labels do not inherit OpenAlex topics. In particular:

- NLP topics are not renamed “LLM”;
- T11714 remains a separate vision-language-centered native topic and is not
  equated with the broader custom Multimodal AI rule;
- no dedicated RAG OpenAlex topic is claimed; T10028 is too broad to proxy RAG.

Native and custom counts must appear in separate tables, legends, or panels with
their method stated. Differences can reflect measurement, not only science.

## 4. Custom-rule audit protocol

For each custom label, sort works by canonical Work ID and use a fixed seed to draw
both rule-positive and rule-negative audit candidates. A reviewer assigns
`relevant`, `ambiguous`, or `false positive` to positives and `true negative`,
`ambiguous`, or `false negative` to negatives. Record IDs and reasons.

The original positive audit diagnoses precision problems. The follow-up frame adds
ten random negatives per category, but such a small low-prevalence sample still
cannot establish recall and is not a gold standard. Before inferential category
analysis, expand the stratified audit, use two reviewers where feasible, report
agreement, and freeze the configuration hash. Malformed abstract indexes are
quarantined from custom labels with their reason; native labels and raw records
remain unchanged.

## 5. Sampling protocol after the gate

### Pilot (1,000–2,000)

Request one deterministic OpenAlex server-side sample across the fixed frame.
Do not balance categories. Retrieve every requested page, reject invalid IDs, and
deduplicate by canonical Work ID.

### Intermediate and target

A single OpenAlex sample is capped at 10,000. The 12,000-work plan uses publication-
year strata and allocates sample sizes proportional to validated primary population
counts via Hamilton's largest-remainder method. It retains `stratum_N`, `stratum_n`,
nominal inclusion probability `n/N`, and nominal `sampling_weight=N/n`.

| Year | Population N | Allocated n | Nominal weight N/n |
|---:|---:|---:|---:|
| 2020 | 125,483 | 1,606 | 78.1339 |
| 2021 | 128,891 | 1,650 | 78.1158 |
| 2022 | 126,183 | 1,615 | 78.1319 |
| 2023 | 145,709 | 1,865 | 78.1282 |
| 2024 | 178,696 | 2,288 | 78.1014 |
| 2025 | 232,487 | 2,976 | 78.1206 |

OpenAlex documents `sample` as random and `seed` as reproducible. A live 20-work,
two-page probe on 2026-10-19 returned the same IDs and order on immediate repeated
queries, with no duplicates or missing pages. This establishes only observed
repeatability for that probe—not uniform inclusion, independence, or stability
after OpenAlex changes. Probability and weight fields therefore remain explicitly
qualified as nominal.

Rare-category oversampling, if later needed for ML, must be a separate modeling
dataset or use defensible multi-frame inclusion probabilities. It cannot be mixed
into the prevalence sample and treated as representative.

## 6. Missingness, retractions, and analysis denominators

Profile abstract, FWCI, institution, and country missingness overall and by year,
work type, and both category layers. Text-derived categories are unobservable for
many works without abstracts unless the title itself matches. Missing affiliation
metadata can systematically remove collaboration nodes and edges. FWCI complete
cases can alter the work-type and year composition of impact comparisons.

Retractions remain in immutable raw data and any canonical all-work sensitivity
table with a flag. Primary trend denominators use the non-retracted aggregate;
primary detailed sampling applies the same exclusion at the API filter and validates
`is_retracted=false` record by record. All-work aggregate results quantify the
sensitivity population. No raw response is edited or silently discarded.

## 7. API and provenance protocol

Phase 1 verified the works/topics endpoints, comma-separated AND filters,
pipe-separated OR values, `is_retracted:false`, `group_by`, a maximum `per_page`
of 100, documented `sample`/`seed` behavior, bearer-key authentication, and paging
against official documentation and live responses. Current limits and behavior
can change and must be checked again before scaled collection.

Official references: [filtering](https://help.openalex.org/api/filtering/),
[grouping](https://help.openalex.org/api/grouping/),
[paging](https://help.openalex.org/api/paging/),
[authentication](https://help.openalex.org/api/authentication/), and
[topics](https://help.openalex.org/data/topics/).

Keep exact raw response bytes unchanged. Every run gets a new UTC directory and a
manifest with endpoint, non-secret parameters, timestamps, status, page/result
counts, checksums, and completeness state. Raw response and resume-probe bodies are
written to exclusive `.part` files, flushed, and atomically renamed. An interrupted
temporary or malformed orphan is quarantined with its path, bytes, SHA-256, reason,
and error before any replacement is fetched. The Phase 2 collector resumes only
when plan/config/seed/page settings match, rejects unsafe resume paths, preserves a
failed manifest, and refuses to resume a completed run. API keys are never written
to manifests.

Before mixing checkpointed and newly retrieved pages, the default `all` resume mode
re-fetches every checkpointed page and requires exact ordered Work-ID matches.
`sampled` checks the first and last checkpoint in each started stratum; `minimal`
checks the first. A recovered valid orphan is mandatory in every mode. Probe bodies
and attempt summaries are stored separately. Failure leaves the run incomplete and
preserves both versions. Checking one page per stratum does not establish sample
stability; checking all prior pages is stronger but still cannot guarantee unchanged
metadata fields, future source changes, or database-wide snapshot isolation.

On completion, SHA-256 values are recorded for both raw and interim JSONL outputs.
`openalex-verify-collection <manifest>` performs a read-only verification of every
page checksum and membership list, output checksum and ordered ID sequence, unique
record count, and completeness diagnostics.

The current 12,000-work implementation holds validated records and the canonical
ID set in memory before atomically writing final JSONL. This bounded design is
reasonable for the approved intermediate target, subject to runtime monitoring.
For materially larger collections, stream records to append-only staging storage
and use DuckDB or SQLite for disk-backed uniqueness/checkpoint state. Do not remove
the immutable page responses or completeness gate when adopting streaming.

### Completed Phase 2 acquisition, 2026-10-19 UTC

The refreshed approved non-retracted population was 937,493 works; the parallel
all-work sensitivity population was 942,825. A six-year proportional sample of
12,000 unique works was collected under
`data/raw/openalex_stratified/stratified_20261019T155909Z/`. All 123 pages and
both JSONL outputs passed `openalex-verify-collection`; the manifest is complete.
The nominal weights and year allocations come from the refreshed aggregate
artifact and are documented in
[`reports/PHASE2_COLLECTION_REPORT.md`](../reports/PHASE2_COLLECTION_REPORT.md).
These are observations at the recorded retrieval time, not stable OpenAlex totals.
Raw and derived data remain outside Git and require separate backup.

## 8. Counting safeguards

Canonicalize IDs to `https://openalex.org/W...`. Deduplicate topic, institution,
and country memberships within each work before creating bridge tables. Count
works with `nunique(work_id)` after joins. Never infer paper totals from exploded
authorship/topic rows, and never sum overlapping category counts.
