# Venue Data Inventory — 2020–2024 only

Source: verified original Phase 2 raw JSONL and verified targeted expansion; 2025 sealed records/labels excluded. The inventory is **not** a population-prevalence estimate.

| Measure | Observed count |
|---|---:|
| Source records | 11,539 |
| Unique Work IDs | 11,506 |
| DOI-bearing records | 10,432 |
| Primary OpenAlex source | 11,093 |
| Any hosting source | 11,164 |
| Multiple hosting sources | 4,176 |
| Resolved journal-type source | 8,178 |
| Resolved conference-type source | 30 |
| Repository host (not a journal) | 6,712 |
| Ambiguous published locations | 11 |
| No eligible published venue | 3,320 |
| Distinct source IDs in any location | 3,970 |

The 11,539 source records consist of 9,024 original 2020–24 records and 2,515 targeted 2020–23 records. There are 33 duplicated Work IDs across origins; later paper–venue links select one deterministic record and retain a row-level audit. The original 12,000-work research sample is not redefined by this experiment.

## By publication year

| Year | Records | DOI | Primary source | Journal venue | Conference venue | Unmatched |
|---|---:|---:|---:|---:|---:|---:|
| 2020 | 2,165 | 1,649 | 1,962 | 1,409 | 15 | 741 |
| 2021 | 2,258 | 1,907 | 2,134 | 1,521 | 13 | 721 |
| 2022 | 2,235 | 2,178 | 2,193 | 1,653 | 0 | 578 |
| 2023 | 2,594 | 2,508 | 2,558 | 1,890 | 2 | 701 |
| 2024 | 2,287 | 2,190 | 2,246 | 1,705 | 0 | 579 |

## By work type

| Type | Records | Journal | Conference | Unmatched |
|---|---:|---:|---:|---:|
| article | 8,846 | 8,118 | 28 | 689 |
| preprint | 2,629 | 4 | 0 | 2,625 |
| review | 64 | 56 | 2 | 6 |

## Fourteen selected OpenAlex topics (descriptive)

| Topic ID | Records | Journal | Conference | Unmatched |
|---|---:|---:|---:|---:|
| T10036 | 648 | 465 | 4 | 179 |
| T10664 | 339 | 294 | 0 | 45 |
| T10028 | 394 | 185 | 3 | 206 |
| T10052 | 395 | 347 | 0 | 48 |
| T10462 | 325 | 135 | 2 | 188 |
| T10775 | 332 | 167 | 1 | 164 |
| T10181 | 319 | 183 | 0 | 135 |
| T11307 | 348 | 161 | 2 | 185 |
| T11689 | 347 | 146 | 2 | 199 |
| T12026 | 338 | 155 | 1 | 181 |
| T10201 | 302 | 187 | 0 | 115 |
| T10331 | 339 | 265 | 0 | 74 |
| T10812 | 340 | 262 | 0 | 77 |
| T10100 | 431 | 371 | 0 | 60 |


Topic-specific breakdowns are stored in `inventory_metrics.json` (local, Git-ignored); they are descriptive because the targeted expansion is topic-enriched. OpenAlex `locations` may contain repositories and published versions. We count one paper, not one paper per hosting location. A generic proceedings series is not automatically one annual conference.

**Answer:** substantial journal metadata already exist without further work crawling, but conference-series evidence is sparse. No current-venue suitability or acceptance inference follows from historical appearance.
