# Data Dictionary (Planned Phase 3 Model)

Raw OpenAlex objects remain unchanged. Phase 3 will produce Parquet tables with
the following grain. Nullable fields are never filled with invented values.

## `works.parquet` — one row per canonical work

| Column | Type | Meaning |
|---|---|---|
| `work_id` | string, PK | Canonical `https://openalex.org/W...` |
| `doi` | string? | OpenAlex-selected canonical DOI |
| `title` | string? | Work title |
| `abstract` | string? | Reconstructed from `abstract_inverted_index` |
| `publication_date` | date? | OpenAlex publication date |
| `publication_year` | int? | Publication year |
| `work_type` | string | OpenAlex work type |
| `language` | string? | Detected metadata language |
| `cited_by_count` | int | Raw observed citations at retrieval |
| `fwci` | float? | Field-weighted citation impact |
| `is_oa` | bool? | Whether a free-to-read full text exists |
| `oa_status` | string? | diamond/gold/green/hybrid/bronze/closed |
| `primary_topic_id` | string? | Highest-ranked topic |
| `primary_subfield_id` | string? | Primary topic's subfield |
| `primary_field_id` | string? | Primary topic's field |
| `primary_domain_id` | string? | Primary topic's domain |
| `sample_stratum` | string | Sampling stratum/run identifier |
| `sampling_weight` | float | Inverse inclusion weight; 1 only when justified |
| `retrieved_at_utc` | timestamp | Source retrieval timestamp |

## `work_topics.parquet` — one row per unique work/topic

`work_id`, `topic_id`, `topic_name`, `topic_rank`, `topic_score`, `subfield_id`,
`field_id`, and `domain_id`. Topic score is the classifier's probability the topic
is the main topic; it is not paper quality.

## `authorships.parquet` — one row per work/authorship position

`work_id`, `author_id`, `author_name`, `author_position`, `is_corresponding`, and
the source authorship index. Repeated authorship records are quality flags.

## `work_institutions.parquet` — one row per unique work/institution

`work_id`, `institution_id`, `institution_name`, `institution_type`,
`country_code`, `is_corresponding_institution`. This bridge prevents authors at
the same institution from multiplying paper counts.

## `work_countries.parquet` — one row per unique work/country

`work_id`, ISO-2 `country_code`, and provenance from the authorship/institution
link. Country is affiliation geography, not author nationality.

## `references.parquet` — one row per unique directed citation edge

`citing_work_id`, `referenced_work_id`. Missing/unmatched references are not
interpreted as no bibliography.

## `category_membership.parquet` — one row per work/category match

`work_id`, `analytical_layer`, `category`, `matched_rule_or_topic_ids`, and
classifier/config version. `analytical_layer` is either `openalex_native` or
`custom_emerging`; the layers are never collapsed into an unlabeled union.
Multiple overlapping rows per work are expected.

## `population_year_counts.parquet`

`series`, `year`, `work_count`, `definition`, `retrieved_at_utc`, `query_hash`.
Focused series overlap; `work_count` is an API count of unique work entities for
that query, not a sum of detailed-sample rows.
