# Data Feasibility Report

**Assessment date:** 2026-10-19 UTC

**Phase:** 1 final review; no Phase 2 expansion performed

**Source:** OpenAlex REST API and the completed 1,000-work pilot

## Confirmed frame and live population result

The estimand is the **defined AI/CV primary-subfield corpus**, not all global AI
research. It contains articles, reviews, and preprints published in complete years
2020–2025 whose OpenAlex primary topic is in subfield 1702 or 1707.

The exact live request parameters revalidated at `2026-10-19T03:06:51Z` were:

```json
{
  "filter": "from_publication_date:2020-01-01,to_publication_date:2025-12-31,primary_topic.subfield.id:1702|1707,type:article|review|preprint",
  "group_by": "publication_year"
}
```

The response reported **942,782** unique works:

| Year | Works |
|---:|---:|
| 2020 | 125,868 |
| 2021 | 129,604 |
| 2022 | 127,946 |
| 2023 | 147,631 |
| 2024 | 179,144 |
| 2025 | 232,589 |

The raw response and SHA-256 are in aggregate run
`aggregates_20261019T030648Z`. OpenAlex can backfill and reclassify records, so
these are time-stamped results, not immutable external facts.

## Native topic aggregates

Each query below used the exact population filter above plus the shown
`topics.id` clause and `group_by=publication_year`. These are overlapping
OpenAlex-native topic lenses, not custom text labels.

| Native lens | Added clause | 2020–2025 works |
|---|---|---:|
| NLP | `topics.id:T10181\|T10028` | 92,799 |
| Computer Vision | `topics.id:T10036` | 142,825 |
| Reinforcement Learning | `topics.id:T10462` | 30,594 |
| Explainable AI | `topics.id:T12026` | 18,726 |
| Multimodal ML Applications | `topics.id:T11714` | 32,541 |

The API returned complete six-year groupings for these queries. The counts overlap
and cannot be summed. No LLM, broad Multimodal AI, or RAG population total is
reported as equivalent to this table: those are custom title/abstract constructs.
The earlier 3,013 exact-phrase RAG API result remains provenance evidence for one
search query, but it is not the audited custom classifier and is retired from the
native aggregate table.

## Pilot integrity

The expanded run `pilot_20261019T024131Z` used the same fixed population filter,
`sample=1000`, and `seed=20251019`. It produced 1,000 raw records, 1,000 canonical
unique IDs, zero duplicates, and zero corpus-boundary violations across ten raw
pages. Page bodies, record JSONL, timestamps, query parameters, and hashes were
preserved. The pilot is a sample, not a population census.

Overall missing/flagged values were: abstract 194 (19.4%), FWCI 234 (23.4%), no
usable nested institution 252 (25.2%), no country 253 (25.3%), DOI 90 (9.0%),
language 52 (5.2%), and retracted 6 (0.6%).

## Stratified missingness

Cells show `missing count (percent within row)`. Percentages are descriptive pilot
diagnostics and have sampling uncertainty.

| Year | n | Abstract | FWCI | Institution | Country |
|---:|---:|---:|---:|---:|---:|
| 2020 | 151 | 39 (25.8%) | 25 (16.6%) | 50 (33.1%) | 50 (33.1%) |
| 2021 | 128 | 29 (22.7%) | 34 (26.6%) | 34 (26.6%) | 34 (26.6%) |
| 2022 | 131 | 25 (19.1%) | 24 (18.3%) | 28 (21.4%) | 28 (21.4%) |
| 2023 | 147 | 35 (23.8%) | 40 (27.2%) | 36 (24.5%) | 36 (24.5%) |
| 2024 | 175 | 20 (11.4%) | 39 (22.3%) | 28 (16.0%) | 28 (16.0%) |
| 2025 | 268 | 46 (17.2%) | 72 (26.9%) | 76 (28.4%) | 77 (28.7%) |

| Work type | n | Abstract | FWCI | Institution | Country |
|---|---:|---:|---:|---:|---:|
| Article | 765 | 164 (21.4%) | 0 (0.0%) | 162 (21.2%) | 162 (21.2%) |
| Preprint | 234 | 30 (12.8%) | 234 (100.0%) | 89 (38.0%) | 90 (38.5%) |
| Review | 1 | 0 (0.0%) | 0 (0.0%) | 1 (100.0%) | 1 (100.0%) |

The pilot's FWCI missingness is entirely a work-type issue: every sampled
preprint lacks FWCI while no sampled article does. An FWCI complete-case analysis
would silently exclude all preprints and cannot be described as covering the
full corpus. Affiliation missingness is also much higher for preprints than
articles, so collaboration networks will under-represent preprint-heavy areas.

### By research category

| Layer and category | n | Abstract | FWCI | Institution | Country |
|---|---:|---:|---:|---:|---:|
| Native: NLP | 108 | 13 (12.0%) | 48 (44.4%) | 33 (30.6%) | 33 (30.6%) |
| Native: Computer Vision | 135 | 37 (27.4%) | 33 (24.4%) | 30 (22.2%) | 30 (22.2%) |
| Native: Reinforcement Learning | 47 | 3 (6.4%) | 27 (57.4%) | 7 (14.9%) | 7 (14.9%) |
| Native: Explainable AI | 28 | 3 (10.7%) | 13 (46.4%) | 5 (17.9%) | 5 (17.9%) |
| Native: Multimodal ML Applications | 39 | 2 (5.1%) | 26 (66.7%) | 17 (43.6%) | 17 (43.6%) |
| Custom: Large Language Models | 53 | 3 (5.7%) | 33 (62.3%) | 22 (41.5%) | 22 (41.5%) |
| Custom: Multimodal AI | 15 | 0 (0.0%) | 11 (73.3%) | 7 (46.7%) | 7 (46.7%) |
| Custom: RAG | 4 | 0 (0.0%) | 2 (50.0%) | 1 (25.0%) | 1 (25.0%) |

Category denominators overlap. Low abstract-missing rates among custom matches do
not demonstrate good text coverage: works lacking abstracts have fewer chances to
match unless their title contains a rule term. This is classification-dependent
missingness. The high FWCI and affiliation gaps in emerging categories are also
consistent with their recent/preprint-heavy composition and can bias impact and
network comparisons.

## Retraction handling

Six pilot works are explicitly retracted (one from 2021, two from 2022, two from
2023, one from 2024; all are articles). Raw and canonical tables retain them with
`is_retracted=true`. Primary trend, impact, OA, and collaboration estimates will
exclude them and state the denominator; an include-retracted sensitivity analysis
will be reported. This policy prevents deletion from erasing provenance while
avoiding known-retracted work in the main scientific-impact comparison.

## Category feasibility and audit

The separated rules matched 108/135/47/28/39 pilot works in the five native
lenses, and 53 LLM, 15 Multimodal AI, and 4 RAG works in the three custom labels.
A fixed-seed relevance audit found 9 relevant and 1 ambiguous among 10 LLM
matches; 9 relevant and 1 ambiguous among 10 Multimodal AI matches; and 2
relevant, 1 ambiguous, and 1 false positive among all 4 RAG matches. This is too
small for a defensible precision estimate and says nothing about recall. Details
are in `reports/topic_discovery.md`.

## Feasibility decision

The API, fixed frame, native taxonomy, raw-data provenance, and pilot mechanics
are ready for Phase 2. Readiness is conditional on treating custom labels as a
separate measurement layer, preserving sampling weights, and carrying the stated
retraction/missingness policies forward. Before the 12,000-work pull, configure a
verified API key and implement the planned proportional year-stratified,
checkpointed collector. No full Phase 2 collection has started.
