# Phase 3 Data Dictionary

These are the implemented Parquet schemas for the verified Phase 2 sample. All
identifiers are canonical OpenAlex URLs unless stated otherwise. Source JSONL is
unchanged. Each table has a stable Arrow schema; `?` means nullable. An absent
metadata value is `null`, never a guessed value. The [Phase 3 report](../reports/PHASE3_DATA_QUALITY_REPORT.md)
contains the observed row counts and checksums.

## `works.parquet`

Grain and primary key: exactly one row per `work_id`. All bridge tables below
reference this key. The data are a sample, not full population counts.

| Columns | Arrow type | Meaning and nullability |
|---|---|---|
| `work_id` | string | Required canonical `https://openalex.org/W…` |
| `doi`, `title`, `abstract`, `language` | string? | Nullable; DOI normalized to `https://doi.org/…`; abstract reconstructed from inverted index; original Unicode/case retained |
| `publication_date`, `publication_year`, `work_type` | date32, int16, string | Required; exact date within 2020–2025, year matches date; article/review/preprint only |
| `cited_by_count`, `fwci` | int64, float64? | Nonnegative observed citation count including zero; nullable, nonnegative OpenAlex FWCI |
| `is_retracted` | bool | Required false in the primary sample |
| `is_oa`, `oa_status` | bool?, string? | Nullable binary/category OA; observed statuses diamond, gold, green, hybrid, bronze, closed; checked for logical consistency |
| `primary_topic_id`, `primary_subfield_id`, `primary_field_id`, `primary_domain_id` | string? | Nullable native primary-topic hierarchy; primary subfield is required to be 1702 or 1707 by the corpus predicate |
| `sample_stratum`, `sampling_weight`, `collection_run_id`, `retrieved_at_utc` | string, float64, string, timestamp[us, UTC] | Required source and plan provenance. `sampling_weight` is **nominal** `N_h/n_h`, not a guaranteed inverse inclusion probability |
| `publication_age_years` | float64 | `(collection completion time − publication date).days / 365.2425`, using one observation time for the whole sample |
| `log1p_citations`, `zero_citation_flag`, `has_fwci` | float64, bool, bool | `ln(1 + cited_by_count)`; exact observed-zero flag; FWCI presence |
| `has_oa_metadata`, `has_abstract`, `title_length`, `abstract_word_count`, `has_usable_text` | bool, bool, int32, int32, bool | Coverage and descriptive text features; no text imputation or destructive lowercasing |
| `reference_list_status`, `referenced_works_count_reported` | string, int32? | Source list status (`missing`, `empty`, `present`) and nullable OpenAlex reported count. Missing is not zero |
| `authorship_count`, `identified_author_count` | int32 | Number of authorship positions and unique nonnull author IDs |
| `unique_institution_count`, `unique_country_count` | int32 | Unique identified affiliation institutions and country codes; never number of authorships |
| `has_institution_affiliation`, `has_country_affiliation` | bool | At least one identified institution/country |
| `institution_affiliation_complete`, `country_affiliation_complete` | bool | Whether each authorship has the relevant affiliation information |
| `institutional_collaboration`, `international_collaboration` | bool? | True for at least two observed entities; False only if affiliation coverage is complete; otherwise null/unknown |
| `native_category_count`, `custom_category_count` | int16 | Number of overlapping category memberships in each independent classification layer |
| `has_native_category`, `has_custom_category`, `llm_text_match`, `multimodal_text_match`, `rag_text_match` | bool | Observed matching indicators, not authoritative relevance or validated negatives |

The primary-topic columns describe one topic per work; `work_topics` records all
reported topic memberships. Primary-topic study membership and overlapping
research categories must not be conflated.

## Relationship tables

| Table | Primary/composite key and grain | Columns | Notes |
|---|---|---|---|
| `work_topics.parquet` | (`work_id`, `topic_id`), one unique work/topic | `work_id` string, `topic_id` string, `topic_name` string?, `topic_rank` int16, `topic_score` float64?, `subfield_id` string?, `field_id` string?, `domain_id` string? | Rank is source order; topic score is classifier output, **not research quality**. |
| `authorships.parquet` | (`work_id`, `authorship_index`), one source authorship position | `work_id` string, `author_id` string?, `author_name` string?, `author_position` string?, `is_corresponding` bool?, `authorship_index` int32 | Missing ID remains null. Names are never used as identity keys. |
| `work_institutions.parquet` | (`work_id`, `institution_id`), one unique identified work/institution | `work_id` string, `institution_id` string, `institution_name` string?, `institution_type` string?, `country_code` string?, `is_corresponding_institution` bool | Repeated author affiliations collapse to one link. No invented IDs. |
| `work_countries.parquet` | (`work_id`, `country_code`), one unique work/affiliation country | `work_id` string, `country_code` ISO-2 string, `country_provenance` string | Country is affiliation geography, not nationality. Provenance distinguishes authorship and institution sources. |
| `references.parquet` | (`citing_work_id`, `referenced_work_id`), one unique directed edge | `citing_work_id` string, `referenced_work_id` string, `referenced_in_sample` bool | Referenced works outside the sample remain present; only citing ID is an FK to `works`. Malformed/duplicate edges are logged in `quality.json`. |
| `category_membership.parquet` | (`work_id`, `analytical_layer`, `category`), one match | `work_id` string, `analytical_layer` string, `category` string, `matched_rule_or_topic_ids` list<string>, `classification_version` string | `openalex_native` uses verified topic IDs; `custom_emerging` uses versioned title/abstract rule names. Memberships overlap. |

Each `work_id` in the first five bridge tables is a foreign key to `works`.
`references.citing_work_id` is such a key; `referenced_work_id` may be outside
the 12,000-work sample. Null author IDs are legal, but `authorship_index`
is always a source-position key. Invalid nonnull identifiers fail validation;
malformed abstract indexes and references are recorded in `quality.json`.

## `population_year_counts.parquet`

Grain/key: (`series`, `year`), not (`work_id`). Columns: `series` string,
`year` int16, `work_count` int64, `definition` string,
`retrieved_at_utc` timestamp[us, UTC], `query_hash` string. This table is
built only from the verified population aggregate artifact. It retains both
primary non-retracted and all-work sensitivity series and supported native-topic
series. Native-topic series overlap and cannot be summed as a partition.
No detailed-sample count is presented as a population LLM/RAG count.

## Classification and interpretation

The native layer currently includes NLP, computer vision, reinforcement
learning, explainable AI and multimodal ML applications, based on verified
OpenAlex topic IDs in `config/topics.yaml`. The custom layer contains LLM,
Multimodal AI and RAG title/abstract rules from that same versioned config.
Rules are selective and may miss relevant work, especially without abstracts.
Neither layer is a mutually exclusive field taxonomy. Counts from the two
methods are not directly equivalent. Raw citations are age-dependent and do
not measure scientific quality. FWCI is nullable—every sampled preprint lacks
it—and must never be zero-imputed. OA–citation analyses are observational.
