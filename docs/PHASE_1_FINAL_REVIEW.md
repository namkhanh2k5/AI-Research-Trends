# Phase 1 Final Review

> Historical Phase 1 gate. The follow-up fixes, new live counts, sampling design,
> and current readiness decision are in
> [`reports/PRE_PHASE2_REVIEW.md`](../reports/PRE_PHASE2_REVIEW.md).

**Review date:** 2026-10-19 UTC

**Decision:** Ready for Phase 2 with stated controls; Phase 2 collection not started

## Confirmed corpus definition

The population estimand is the **defined AI/CV primary-subfield corpus**, not all
global AI research:

- publication date: 2020-01-01 through 2025-12-31 (complete calendar years);
- work type: article, review, or preprint;
- primary topic subfield: 1702 Artificial Intelligence or 1707 Computer Vision
  and Pattern Recognition;
- unit: one unique canonical OpenAlex Work ID.

The configuration loader enforces these values. Both aggregate and detailed-pilot
commands use the same filter builder. Applied-AI works whose primary topic lies
outside the two subfields are out of scope and must not be implied by conclusions.

## Validated aggregate counts and parameters

Live revalidation completed at `2026-10-19T03:06:51Z`. The population request was:

```json
{
  "filter": "from_publication_date:2020-01-01,to_publication_date:2025-12-31,primary_topic.subfield.id:1702|1707,type:article|review|preprint",
  "group_by": "publication_year"
}
```

It returned 942,782 works: 125,868 (2020), 129,604 (2021), 127,946
(2022), 147,631 (2023), 179,144 (2024), and 232,589 (2025).

Every native-topic request used the exact filter above with one appended clause
and `group_by=publication_year`:

| Series | Appended filter | Six-year count |
|---|---|---:|
| NLP | `topics.id:T10181\|T10028` | 92,799 |
| Computer Vision | `topics.id:T10036` | 142,825 |
| Reinforcement Learning | `topics.id:T10462` | 30,594 |
| Explainable AI | `topics.id:T12026` | 18,726 |
| Multimodal ML Applications | `topics.id:T11714` | 32,541 |

These overlapping native counts cannot be summed. Raw evidence and hashes are in
`data/raw/openalex_aggregates/aggregates_20261019T030648Z`; the derived manifest is
`data/metadata/population_counts_v2.json` (both intentionally Git-ignored).

## Topic/category mapping decisions

All six configured native IDs passed direct live validation of ID, display name,
description, and hierarchy. The native layer uses only `topics.id`. It contains a
broad NLP composite, partial computer-vision and RL mappings, a close XAI match,
and the vision-language-centered T11714 multimodal topic.

LLM, broader Multimodal AI, and RAG form a separate custom layer based only on
documented title/abstract rule groups. NLP is not relabeled as LLM, T11714 is not
equated with broad Multimodal AI, and no dedicated RAG topic is claimed.

In the 1,000-work pilot, custom rules matched 53 LLM, 15 Multimodal AI, and 4 RAG
works. A deterministic audit reviewed 10, 10, and all 4 respectively: LLM had
9 relevant/1 ambiguous/0 false; Multimodal AI 9/1/0; RAG 2/1/1. The RAG false
positive was a segmentation paper that mentioned only downstream relevance to
RAG. These small single-reviewer results are diagnostics, not validated precision
or recall estimates.

## Data-quality findings

The pilot contains 1,000 raw and 1,000 unique records, no duplicate IDs, and no
corpus-boundary violations. Overall missingness is 19.4% for abstracts, 23.4% for
FWCI, 25.2% for usable institutions, and 25.3% for countries. All 234 sampled
preprints lack FWCI, versus none of 765 articles. Institution/country missingness
is about 38% for preprints and 21% for articles. Emerging-category FWCI missingness
ranges from 50.0% to 73.3%.

Six works are marked retracted. They remain in raw/canonical storage but will be
excluded from primary estimates, counted explicitly, and included in a sensitivity
analysis. Complete stratifications by year, type, and both category layers are in
`reports/data_feasibility.md` and `data/metadata/pilot_profile_v2.json`.

## Package and validation review

All importable code now resides below `src/ai_research_trends/`; obsolete
top-level `src/crawling` compatibility modules were removed. All five console
scripts point to the canonical package and their `--help` commands succeed. The
data-quality notebook was re-executed from the repository root with zero error
outputs. Editable installation succeeds and `pip check` reports no broken
requirements.

Final offline test result: **19 passed in 0.80 seconds**. Tests cover exact
population-filter construction and drift rejection, aggregate query inheritance,
overlapping two-layer categories, primary-topic corpus membership, missing nested
affiliations, retraction handling, API parameters/retries/pagination, topic parsing
and validation, raw preservation/deduplication, null metadata, and abstract
reconstruction.

## Remaining limitations

- The primary-subfield boundary omits applied AI assigned elsewhere.
- OpenAlex topics are inferred and can change; retrieval time is part of the result.
- Native topic mappings are partial and overlapping.
- Custom rules have only a small single-reviewer positive-match audit; recall is
  unknown, and RAG centrality is especially fragile.
- Missing abstracts can suppress custom matches; missing affiliations can remove
  collaboration nodes/edges; FWCI complete cases exclude every sampled preprint.
- The pilot has only one review and small custom-category denominators.
- Citation metrics measure database-recorded impact, not scientific quality.

## Phase 2 readiness

The project is methodologically ready to implement Phase 2 collection because the
corpus, classification layers, provenance rules, quality flags, and tests are now
fixed. Before any 12,000-work pull, add the proportional year-stratified allocator,
sampling weights, checkpoint/resume behavior, and a verified API key. Expand the
manual category audit before inferential category comparisons. No full Phase 2
collection was performed during this review.
