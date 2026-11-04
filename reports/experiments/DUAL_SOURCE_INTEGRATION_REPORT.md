# Dual-source canonical integration — observed RQ7 pilot

Canonical grain: one row per selected original OpenAlex Work ID. The current OpenAlex ID is retained separately where an ID redirect occurred. Crossref records are linked only by exact normalized DOI.

| Provider linkage status | Works |
|---|---:|
| CROSSREF_NOT_FOUND | 440 |
| DOI_MISSING | 113 |
| EXACT_DOI_MATCH | 944 |
| IDENTIFIER_CONFLICT | 3 |

Canonical rows: 1,500; exact DOI matches: 944; field-level provenance rows: 15,000; conflict rows: 2,597. Nine Parquet outputs are in the local Git-ignored `processed/` directory. Their full schemas and hashes are in `processing_manifest.json`.

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

Precedence: OpenAlex owns identity, study period, work type, title, publication date, citations, FWCI, OA, primary topic and retraction status. Crossref fills only missing publisher, venue name, valid ISSN and license metadata. A recovered venue name is not a verified journal/conference identity. Conflicting provider values are retained in `metadata_conflicts.parquet`; they are not silently overwritten. A DOI match proves identifier linkage, not correctness of every field.
