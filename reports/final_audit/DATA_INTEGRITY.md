# Data integrity — local, read-only audit

No OpenAlex calls, retraining or mutations of the original collection occurred. Original snapshot: `2026-10-19T15:59:09Z`–`16:03:40Z`; query uses exact annual date boundaries, `type:article|review|preprint`, `primary_topic.subfield.id:1702|1707`, `is_retracted:false`. The aggregate artifact has 937,493 primary/non-retracted and 942,825 all-work sensitivity records. Annual primary counts: 125,506; 128,893; 126,189; 145,735; 178,694; 232,476. This is a defined OpenAlex AI/CV corpus, not global AI output.

`openalex-verify-collection` passed all 123 page hashes, 12,000 canonical unique IDs, exact filters, plan strata 1,607/1,650/1,615/1,865/2,287/2,976, and both JSONL hashes (`b8734cd3da2cba8c2c9ff8a9742d46d62585e55604f18630274f6bb8fbc178af`). Raw: `data/raw/openalex_stratified/stratified_20261019T155909Z/`; interim: matching path under `data/interim/`. Phase 3 source manifest hash `c6fc71e6eee2fc3131df3cdfe2f300dc719ed3b6196be1be852a45519a08aa6e`; plan `f18ecdc621e5e697ae0c3cbe277d5729f40592299f6c2af95cabeab96e9a7593`; population `e84015be2e14756301130dc982b437097449986ae45c9ece4ed8007bb87e36d3`.

Eight Parquet outputs, each checksum checked by `openalex-validate-processed` (29 PASS checks):

| Table | Rows | Columns | Grain | Bytes | SHA-256 prefix |
|---|---:|---:|---|---:|---|
| works | 12,000 | 49 | Work ID | 5,762,302 | `9318c456d916` |
| work_topics | 36,000 | 8 | Work/topic | 342,377 | `e65356b899f3` |
| authorships | 46,249 | 6 | Work/authorship index | 921,766 | `ba8bee6e7da8` |
| work_institutions | 18,717 | 6 | Work/institution ID | 264,917 | `d4fd9e1375b5` |
| work_countries | 11,786 | 3 | Work/country | 74,681 | `6e4c8b1bf27b` |
| references | 289,110 | 3 | Directed citing/referenced IDs | 1,617,252 | `1c0f306225e6` |
| category_membership | 4,790 | 5 | Work/layer/category | 33,595 | `438bf85a8858` |
| population_year_counts | 72 | 6 | Series/year | 3,675 | `ae723a94efa0` |

Full hashes and source/input provenance are in `data/processed/openalex_stratified/stratified_20261019T155909Z/manifest.json`. Arrow schemas were read directly. `works` has canonical ID, DOI/title/abstract/date/year/type/language/citations/FWCI/OA/primary taxonomy/sample stratum/nominal weight/retrieval time, then age/citation/affiliation/category features. Topic bridge has eight topic/hierarchy/score fields; authorships has six position/identity fields; institution six identity/geography fields; country three including provenance; references three including in-sample flag; category five with analytical layer/rule/version; population six with series/year/count/query hash. Key null counts in `works`: title 2, DOI 1,019, abstract 2,558, FWCI 2,678, language 586, international flag 4,030, institutional flag 3,573. Author ID null 4,568 authorship positions; institution type null 1, country code null 388 institution rows. Missing affiliation is not zero collaboration; all 2,678 preprints lack FWCI.

Exact Arrow column-name schemas at audit time (types/nullability remain machine-readable in each Parquet footer and `docs/DATA_DICTIONARY.md`):

- `works`: `work_id, doi, title, abstract, publication_date, publication_year, work_type, language, cited_by_count, fwci, is_retracted, is_oa, oa_status, primary_topic_id, primary_subfield_id, primary_field_id, primary_domain_id, sample_stratum, sampling_weight, collection_run_id, retrieved_at_utc, publication_age_years, log1p_citations, zero_citation_flag, has_fwci, has_oa_metadata, has_abstract, title_length, abstract_word_count, has_usable_text, reference_list_status, referenced_works_count_reported, authorship_count, identified_author_count, unique_institution_count, unique_country_count, has_institution_affiliation, has_country_affiliation, institution_affiliation_complete, country_affiliation_complete, institutional_collaboration, international_collaboration, native_category_count, custom_category_count, has_native_category, has_custom_category, llm_text_match, multimodal_text_match, rag_text_match`.
- `work_topics`: `work_id, topic_id, topic_name, topic_rank, topic_score, subfield_id, field_id, domain_id`.
- `authorships`: `work_id, author_id, author_name, author_position, is_corresponding, authorship_index`.
- `work_institutions`: `work_id, institution_id, institution_name, institution_type, country_code, is_corresponding_institution`.
- `work_countries`: `work_id, country_code, country_provenance`.
- `references`: `citing_work_id, referenced_work_id, referenced_in_sample`.
- `category_membership`: `work_id, analytical_layer, category, matched_rule_or_topic_ids, classification_version`.
- `population_year_counts`: `series, year, work_count, definition, retrieved_at_utc, query_hash`.

Targeted expansion verifier passed 80 pages, 2,515 raw/unique Works, raw SHA `cc946d6970cbfbafcfe58b236699f2f27772545865f68b5b693872f87ef87126`, interim SHA `cd60da68c9d53ffe181e2f4ca847bbad21baf1952e840aa8537e0b1ae67533a3`. Its 1,947 text-usable records are *provisional*; integrated train has 5,055 original plus 1,947 expansion. The uniform ≥30-word abstract floor, representative selection and version-group rules reduce original provisional topic counts (e.g. 1,746 → 1,717 selected-topic original train). Integrator takes 14,515 source rows into 14,470 transitive groups using exact Work ID, normalized DOI and sufficiently long normalized title. It selects one representative, isolates cross-period groups with `test > validation > train`, excludes lower-period and near-title risks, and masks 2025 labels in general development tables. One cross-period high-similarity near-title pair remains a documented heuristic risk, not proof of complete deduplication. Its verifier passed eight output hashes against an independent rerun. 2025 sealed label content was not opened.

Phase 4 analysis verifier passed 18 checks, all 64 output files, and byte-identical rerun hashes. RQ6 verifier passed 14-topic/8-CSV/5-figure publication. Web-data verifier passed 22 outputs, 12,000-paper index and 14 Topic Briefs. No failed data-integrity check was observed. These checks establish artifact integrity relative to manifests, not OpenAlex completeness, probabilistic sampling, semantic label truth or rights for public distribution.

Reproduce with `.venv/bin/openalex-verify-collection data/raw/openalex_stratified/stratified_20261019T155909Z/manifest.json`; `.venv/bin/openalex-validate-processed --output-dir data/processed/openalex_stratified/stratified_20261019T155909Z --plan data/metadata/phase2_sampling_plan.json --population data/metadata/population_counts_pre_phase2.json`; `.venv/bin/openalex-verify-ml-expansion data/raw/openalex_ml_expansion/ml_expansion_20261101T052506Z/manifest.json`; `.venv/bin/openalex-verify-integrated-topics data/processed/ml_topic_classification/finalization_p2_20261101_v3 --compare-dir data/processed/ml_topic_classification/finalization_p2_20261101_v3_rerun`; `.venv/bin/openalex-validate-phase4 data/analysis/phase4_stratified_20261019T155909Z_v3 --compare-dir data/analysis/phase4_stratified_20261019T155909Z_v3_rerun`.
