"""Explicit Arrow schemas and grains for the eight Phase 3 tables."""

from __future__ import annotations

import pyarrow as pa


S = pa.string()
I16 = pa.int16()
I32 = pa.int32()
I64 = pa.int64()
F64 = pa.float64()
B = pa.bool_()
DATE = pa.date32()
UTC = pa.timestamp("us", tz="UTC")
STRING_LIST = pa.list_(S)


SCHEMAS = {
    "works": pa.schema(
        [
            ("work_id", S), ("doi", S), ("title", S), ("abstract", S),
            ("publication_date", DATE), ("publication_year", I16),
            ("work_type", S), ("language", S), ("cited_by_count", I64),
            ("fwci", F64), ("is_retracted", B), ("is_oa", B), ("oa_status", S),
            ("primary_topic_id", S), ("primary_subfield_id", S),
            ("primary_field_id", S), ("primary_domain_id", S),
            ("sample_stratum", S), ("sampling_weight", F64),
            ("collection_run_id", S), ("retrieved_at_utc", UTC),
            ("publication_age_years", F64), ("log1p_citations", F64),
            ("zero_citation_flag", B), ("has_fwci", B),
            ("has_oa_metadata", B), ("has_abstract", B),
            ("title_length", I32), ("abstract_word_count", I32),
            ("has_usable_text", B), ("reference_list_status", S),
            ("referenced_works_count_reported", I32),
            ("authorship_count", I32), ("identified_author_count", I32),
            ("unique_institution_count", I32), ("unique_country_count", I32),
            ("has_institution_affiliation", B), ("has_country_affiliation", B),
            ("institution_affiliation_complete", B),
            ("country_affiliation_complete", B),
            ("institutional_collaboration", B),
            ("international_collaboration", B),
            ("native_category_count", I16), ("custom_category_count", I16),
            ("has_native_category", B), ("has_custom_category", B),
            ("llm_text_match", B), ("multimodal_text_match", B),
            ("rag_text_match", B),
        ]
    ),
    "work_topics": pa.schema(
        [
            ("work_id", S), ("topic_id", S), ("topic_name", S),
            ("topic_rank", I16), ("topic_score", F64),
            ("subfield_id", S), ("field_id", S), ("domain_id", S),
        ]
    ),
    "authorships": pa.schema(
        [
            ("work_id", S), ("author_id", S), ("author_name", S),
            ("author_position", S), ("is_corresponding", B),
            ("authorship_index", I32),
        ]
    ),
    "work_institutions": pa.schema(
        [
            ("work_id", S), ("institution_id", S),
            ("institution_name", S), ("institution_type", S),
            ("country_code", S), ("is_corresponding_institution", B),
        ]
    ),
    "work_countries": pa.schema(
        [("work_id", S), ("country_code", S), ("country_provenance", S)]
    ),
    "references": pa.schema(
        [("citing_work_id", S), ("referenced_work_id", S), ("referenced_in_sample", B)]
    ),
    "category_membership": pa.schema(
        [
            ("work_id", S), ("analytical_layer", S), ("category", S),
            ("matched_rule_or_topic_ids", STRING_LIST),
            ("classification_version", S),
        ]
    ),
    "population_year_counts": pa.schema(
        [
            ("series", S), ("year", I16), ("work_count", I64),
            ("definition", S), ("retrieved_at_utc", UTC), ("query_hash", S),
        ]
    ),
}

KEYS = {
    "works": ("work_id",),
    "work_topics": ("work_id", "topic_id"),
    "authorships": ("work_id", "authorship_index"),
    "work_institutions": ("work_id", "institution_id"),
    "work_countries": ("work_id", "country_code"),
    "references": ("citing_work_id", "referenced_work_id"),
    "category_membership": ("work_id", "analytical_layer", "category"),
    "population_year_counts": ("series", "year"),
}
