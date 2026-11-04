# Independent RQ7 review handoff

- Branch: `experiment/dual-source-etl-pilot-rq7`; source parent: `5af0729329f77bd58445ce289f1daddd56f9cfdb`.
- Local run: `data/analysis/dual_source_etl_pilot/dual_source_rq7_20261104_v1`. Selected/canonical Work IDs: 1,500. Group A/B: 1,200/300.
- OpenAlex attempts/batches/aliases: 37/30/7.
- Crossref fresh attempts/cache hits/200/404/exact parsed matches: 1,303/84/947/440/944.
- Local manifests: `plan.json`, `collection_manifest.json`, `processing_manifest.json`, `evaluation.json`; verifier: PASS.
- Redacted connection evidence: `connection_preflight.json`; SHA-256 `287e6ee6e6e60a28f5c222725f5745d04c933f7e430e6d33c5f53b9f953ed322`.
- Canonical schema: `work_id, doi, doi_status, title, abstract, abstract_status, publication_date, publication_year, work_type, primary_topic_id, primary_subfield_id, publisher, venue_name, source_id, issns, invalid_issns, license, cited_by_count, fwci, is_oa, oa_status, is_retracted, authorship_count, reference_count, openalex_current_work_id, current_frame_member, group, match_status, crossref_retraction_evidence, quality_warnings, publisher_source, venue_name_source, issns_source, license_source, crossref_author_count, crossref_reference_count, crossref_funder_count, crossref_abstract_available, crossref_orcid_available, crossref_affiliation_available, snapshot_drift_fields`.
- SHA-256 verified: 1,427 stored artifacts. Source frame, old raw snapshot and prior cache hashes are in local manifests.
- Offline validation: 249 passed, 9 skipped, 0 failed; pip check: No broken requirements found. Deterministic Parquet rerun: 9 of 9 Parquet SHA-256 hashes identical across two runs with the same inputs. Local validation-evidence SHA-256: 914eea7b3f80459eec5f14e097565456c797d66b8a701d89f35b64db51f250c2.
- Environment diagnostic: One chained verifier invocation printed PASS then aborted during Python interpreter shutdown (exit 134); a standalone rerun exited 0 and passed. This is not treated as a data-integrity failure, but the environment-level cause was not established.
- Data-product inventory:

| Table | Rows | Columns | Bytes | SHA-256 |
|---|---:|---:|---:|---|
| `canonical_works.parquet` | 1,500 | 41 | 1,132,997 | `eacc05b0bbbc8a88df11665d7444654860430e0e77f9cc73caea323a29afaab9` |
| `provider_records.parquet` | 2,444 | 11 | 143,401 | `e346d185420c3eba2df3f7a8e89886bf47e611eab2d323a5f252c8ae703ab3a9` |
| `provider_links.parquet` | 1,500 | 6 | 138,598 | `c5bd0678ce66f18cc998bdf683fb2b29f10c6b94967e82368ccc98f7b1723689` |
| `field_provenance.parquet` | 15,000 | 5 | 27,445 | `4bbf5e74c167fc3bc812321a44cf58df93d3b5edcacf7f2c987b462770fb51bf` |
| `metadata_conflicts.parquet` | 2,597 | 6 | 101,297 | `7310cb43dfb6bb803d171af5cb55135c4df9bbb8a16ac500cee7ee9c75b5b05f` |
| `duplicate_audit.parquet` | 36 | 3 | 3,271 | `03b096696e2120643dd1d8e9f03c3e83da42cd4438a2f400ca0d34a8065339ce` |
| `missingness_report.parquet` | 1,500 | 10 | 24,059 | `95a378bdfbea03aa8c9845c710d70740f1a69efcce18598f2453b2deeb6217d0` |
| `retraction_status_audit.parquet` | 1,500 | 4 | 19,160 | `3aa1c63300cb44eca9b342fe98ecfd15f3031421a26310038c6df5290ca7cbb5` |
| `data_quality_summary.parquet` | 3 | 13 | 8,071 | `a92f1bda81e74baf08ddec5f90033ab44575b998867217dff44d99affc65c0fa` |
- Reproduction: `openalex-dual-source verify --run data/analysis/dual_source_etl_pilot/dual_source_rq7_20261104_v1`; `openalex-report-dual-source --run data/analysis/dual_source_etl_pilot/dual_source_rq7_20261104_v1`. Collection is immutable once complete.
- Independent correctness check: NOT VERIFIED. Provider agreement is not ground truth. Never open sealed 2025 labels.
