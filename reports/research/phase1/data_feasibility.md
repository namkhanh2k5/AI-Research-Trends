# Data Feasibility Report

**Assessment date:** 2026-10-19 UTC

**Phase:** pre-Phase 2 review; no 12,000-work collection performed

**Source:** OpenAlex REST API and the completed 1,000-work pilot

## Confirmed frame and live population results

The estimand is the **defined AI/CV primary-subfield corpus**, not all global AI
research. It contains articles, reviews, and preprints published from 2020-01-01
through 2025-12-31 whose OpenAlex `primary_topic.subfield.id` is 1702 or 1707.
Primary estimands exclude known retractions; parallel all-work counts are
sensitivity data.

The exact primary parameters validated at `2026-10-19T07:41:41Z` were:

```json
{
  "filter": "from_publication_date:2020-01-01,to_publication_date:2025-12-31,primary_topic.subfield.id:1702|1707,type:article|review|preprint,is_retracted:false",
  "group_by": "publication_year"
}
```

The primary response reported **937,449** works. Removing only the retraction
filter produced **942,782** works, a difference of 5,333.

| Year | Primary non-retracted | All works | Difference |
|---:|---:|---:|---:|
| 2020 | 125,483 | 125,868 | 385 |
| 2021 | 128,891 | 129,604 | 713 |
| 2022 | 126,183 | 127,946 | 1,763 |
| 2023 | 145,709 | 147,631 | 1,922 |
| 2024 | 178,696 | 179,144 | 448 |
| 2025 | 232,487 | 232,589 | 102 |

Raw responses and SHA-256 hashes are in
`aggregates_20261019T074133Z`. Its manifest is complete for all 12 expected
queries. OpenAlex can backfill and reclassify records, so these are time-stamped
results, not immutable external facts.

## Native topic aggregates

Each query used both population variants plus the displayed `topics.id` clause
and `group_by=publication_year`. These are overlapping OpenAlex-native topic
lenses, not custom text labels.

| Native lens | Added clause | Primary non-retracted | All works |
|---|---|---:|---:|
| NLP | `topics.id:T10181\|T10028` | 92,385 | 92,799 |
| Computer Vision | `topics.id:T10036` | 142,145 | 142,825 |
| Reinforcement Learning | `topics.id:T10462` | 30,562 | 30,594 |
| Explainable AI | `topics.id:T12026` | 18,714 | 18,726 |
| Multimodal ML Applications | `topics.id:T11714` | 32,490 | 32,541 |

All responses passed exact-year, duplicate-key, count-type, and `meta.count`
validation. Counts overlap and cannot be summed. LLM, broad Multimodal AI, and RAG
are custom title/abstract constructs and are not represented as equivalent native
population aggregates.

## Pilot integrity and missingness

The historical `pilot_20261019T024131Z` used the all-work frame, `sample=1000`,
and `seed=20251019`. It contains 1,000 raw and 1,000 canonical unique records,
zero duplicates, and zero date/type/subfield boundary violations. Six records are
retracted. The retained pilot remains useful for feasibility and exclusion tests;
its retracted records do not belong in primary analysis denominators.

Overall missing/flagged values were: abstract 194 (19.4%), FWCI 234 (23.4%), no
usable nested institution 252 (25.2%), no country 253 (25.3%), DOI 90 (9.0%), and
language 52 (5.2%).

| Year | n | Abstract | FWCI | Institution | Country | Retracted |
|---:|---:|---:|---:|---:|---:|---:|
| 2020 | 151 | 39 (25.8%) | 25 (16.6%) | 50 (33.1%) | 50 (33.1%) | 0 |
| 2021 | 128 | 29 (22.7%) | 34 (26.6%) | 34 (26.6%) | 34 (26.6%) | 1 |
| 2022 | 131 | 25 (19.1%) | 24 (18.3%) | 28 (21.4%) | 28 (21.4%) | 2 |
| 2023 | 147 | 35 (23.8%) | 40 (27.2%) | 36 (24.5%) | 36 (24.5%) | 2 |
| 2024 | 175 | 20 (11.4%) | 39 (22.3%) | 28 (16.0%) | 28 (16.0%) | 1 |
| 2025 | 268 | 46 (17.2%) | 72 (26.9%) | 76 (28.4%) | 77 (28.7%) | 0 |

| Work type | n | Abstract | FWCI | Institution | Country | Retracted |
|---|---:|---:|---:|---:|---:|---:|
| Article | 765 | 164 (21.4%) | 0 (0.0%) | 162 (21.2%) | 162 (21.2%) | 6 |
| Preprint | 234 | 30 (12.8%) | 234 (100.0%) | 89 (38.0%) | 90 (38.5%) | 0 |
| Review | 1 | 0 (0.0%) | 0 (0.0%) | 1 (100.0%) | 1 (100.0%) | 0 |

Every sampled preprint lacks FWCI while no sampled article does. FWCI complete-case
analysis would silently exclude all preprints. Affiliation missingness is also
higher for preprints, so collaboration networks will under-represent preprint-heavy
areas. Updated category-level profiling is retained in
`pilot_profile_pre_phase2.json`; its overlapping denominators must not be summed.

| Layer/category | n | Abstract | FWCI | Institution | Country | Retracted |
|---|---:|---:|---:|---:|---:|---:|
| Native NLP | 108 | 13 (12.0%) | 48 (44.4%) | 33 (30.6%) | 33 (30.6%) | 1 |
| Native Computer Vision | 135 | 37 (27.4%) | 33 (24.4%) | 30 (22.2%) | 30 (22.2%) | 1 |
| Native Reinforcement Learning | 47 | 3 (6.4%) | 27 (57.4%) | 7 (14.9%) | 7 (14.9%) | 0 |
| Native Explainable AI | 28 | 3 (10.7%) | 13 (46.4%) | 5 (17.9%) | 5 (17.9%) | 0 |
| Native Multimodal ML | 39 | 2 (5.1%) | 26 (66.7%) | 17 (43.6%) | 17 (43.6%) | 0 |
| Custom LLM | 55 | 3 (5.5%) | 34 (61.8%) | 22 (40.0%) | 22 (40.0%) | 0 |
| Custom Multimodal AI | 22 | 0 (0.0%) | 12 (54.5%) | 10 (45.5%) | 10 (45.5%) | 0 |
| Custom RAG | 4 | 0 (0.0%) | 2 (50.0%) | 1 (25.0%) | 1 (25.0%) | 0 |

## Retraction and custom-category handling

Raw records remain unchanged. New detailed samples apply `is_retracted:false` at
the API and validate it record by record. Primary trend, impact, OA, and
collaboration estimands use the 937,449-work frame; the 942,782-work aggregate is
the include-retracted sensitivity frame.

The initial custom-rule audit identified one ambiguous LLM match, one ambiguous
Multimodal match, and one false-positive plus one ambiguous RAG match. A follow-up
fixed-seed frame included 10 random negatives per category. It found one clear
Multimodal false negative and motivated a contextual `cross-modal`/`multi-modality`
rule. Revised pilot matches are 55 LLM, 22 Multimodal AI, and 4 RAG. This small
audit does not establish precision, recall, or exhaustive identification.

Malformed abstract inverted indexes are now quarantined from custom classification
with reasons while native labels and raw records remain available. The pilot had
zero such quarantines.

## Sampling and collection feasibility

Validated non-retracted annual counts support a 12,000-work proportional allocation
of 1,606, 1,650, 1,615, 1,865, 2,288, and 2,976 records for 2020 through 2025.
The plan records each `N`, `n`, nominal `n/N`, and nominal `N/n`. The collector
checkpoints every validated page, resumes compatible failed runs, preserves raw
responses, and requires an explicit `--execute` switch. The full crawl was not run.

A live 20-work, two-page repeated-seed probe passed on 2026-10-19: both repetitions
returned the same ordered unique IDs and complete pages. This does not verify
uniform inclusion or stability after OpenAlex updates, so probability language and
weights remain explicitly qualified as nominal.

## Feasibility decision

The repository is ready for a **controlled** Phase 2 collection. This is conditional
on configuring a verified API key, retaining the sampling caveat, monitoring the
first year stratum, keeping custom and native classifications separate, and carrying
missingness limitations into analysis. No full Phase 2 collection has started.
