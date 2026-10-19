# Data Collection and Sampling Strategy

## 1. Confirmed population estimand

Phase 1 fixes the population as the **defined AI/CV primary-subfield corpus**:

```text
from_publication_date:2020-01-01,
to_publication_date:2025-12-31,
primary_topic.subfield.id:1702|1707,
type:article|review|preprint
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

The configuration loader rejects changes to these four boundaries. The aggregate,
pilot, and later detailed collectors all call the same `build_study_filter`
function. Phase 1 tests assert the complete filter string and assert that every
native-category aggregate begins with it.

## 2. Two separate data products

### A. Population statistics

Use OpenAlex aggregate responses for counts that the API can return completely.
The Phase 1 annual corpus series uses `group_by=publication_year`; each focused
native-topic series adds only `topics.id:<verified IDs>` to the fixed filter.
Store the response bytes, parameters, retrieval time, count, and SHA-256 hash.

These counts are the source for publication volume and growth. A topic-balanced
detailed sample would intentionally alter inclusion probabilities and therefore
must never estimate publication distributions without correct design weights.

### B. Detailed research dataset

Use a deterministic probability sample of work records for missingness,
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

For each custom label, sort pilot matches by canonical Work ID and draw up to ten
with Python's `random.Random(20251019).sample`. A reviewer assigns `relevant`,
`ambiguous`, or `false positive` based on whether the technology is a substantive
object/method of the work rather than a passing motivation. Record IDs and reasons.

This small single-reviewer audit diagnoses precision problems; it cannot estimate
recall because unmatched works are not reviewed, and it is not a gold standard.
Before inferential category analysis, expand the audit, sample both matches and
non-matches, use two reviewers where feasible, report agreement, and freeze the
configuration hash.

## 5. Sampling protocol after the gate

### Pilot (1,000–2,000)

Request one deterministic OpenAlex server-side sample across the fixed frame.
Do not balance categories. Retrieve every requested page, reject invalid IDs, and
deduplicate by canonical Work ID.

### Intermediate and target

A single OpenAlex sample is capped at 10,000. For 12,000 and 25,000 targets, use
publication-year strata and allocate sample sizes proportional to complete annual
population counts via largest remainder. Use distinct fixed seeds and retain
`stratum_N`, `stratum_n`, inclusion probability, and `sampling_weight=N/n`.

Rare-category oversampling, if later needed for ML, must be a separate modeling
dataset or use defensible multi-frame inclusion probabilities. It cannot be mixed
into the prevalence sample and treated as representative.

## 6. Missingness, retractions, and analysis denominators

Profile abstract, FWCI, institution, and country missingness overall and by year,
work type, and both category layers. Text-derived categories are unobservable for
many works without abstracts unless the title itself matches. Missing affiliation
metadata can systematically remove collaboration nodes and edges. FWCI complete
cases can alter the work-type and year composition of impact comparisons.

Retractions remain in immutable raw data and the canonical work table with a flag.
They are excluded from primary trend, impact, OA, and collaboration estimates,
their counts are reported, and an include-retracted sensitivity result is planned.
No record is silently discarded.

## 7. API and provenance protocol

Phase 1 verified the works/topics endpoints, comma-separated AND filters,
pipe-separated OR values, `group_by`, a maximum `per_page` of 100, deterministic
`sample`/`seed`, bearer-key authentication, and cursor behavior against official
documentation and live responses. Current limits and prices can change and must
be checked again before scaled collection.

Official references: [filtering](https://help.openalex.org/api/filtering/),
[grouping](https://help.openalex.org/api/grouping/),
[paging](https://help.openalex.org/api/paging/),
[authentication](https://help.openalex.org/api/authentication/), and
[topics](https://help.openalex.org/data/topics/).

Keep exact raw response bytes unchanged. Every run gets a new UTC directory and a
manifest with endpoint, non-secret parameters, timestamps, status, rate-limit
headers, page/result counts, checksums, and completeness state. A failed run stays
marked incomplete. API keys are never written to manifests.

## 8. Counting safeguards

Canonicalize IDs to `https://openalex.org/W...`. Deduplicate topic, institution,
and country memberships within each work before creating bridge tables. Count
works with `nunique(work_id)` after joins. Never infer paper totals from exploded
authorship/topic rows, and never sum overlapping category counts.
