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
counts, checksums, and completeness state. The Phase 2 collector checkpoints each
validated page, resumes only when plan/config/seed/page settings match, rejects
unsafe resume paths, and preserves a failed manifest. API keys are never written
to manifests.

## 8. Counting safeguards

Canonicalize IDs to `https://openalex.org/W...`. Deduplicate topic, institution,
and country memberships within each work before creating bridge tables. Count
works with `nunique(work_id)` after joins. Never infer paper totals from exploded
authorship/topic rows, and never sum overlapping category counts.
