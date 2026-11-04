# RQ7.1 cross-provider conflict reclassification

Every original field-difference row is retained: **2,597/2,597 accounted for exactly once**. Counts below are field observations, not erroneous works. Distinct-work counts in different classes overlap and must not be summed.

| Primary class | Field differences | Distinct works |
|---|---:|---:|
| DATE_DEFINITION_DIFFERENCE | 314 | 243 |
| NORMALIZATION_DIFFERENCE | 47 | 47 |
| SCHEMA_INCOMPATIBILITY | 525 | 490 |
| SEMANTIC_METADATA_CONFLICT | 712 | 642 |
| TAXONOMY_DIFFERENCE | 944 | 944 |
| UNRESOLVED | 55 | 54 |

Rules: 944 work-type strings are provider taxonomy differences; 314 date/year differences may reflect online/print date definitions or drift; 360 license string/array differences and 165 ISSN-set overlaps are schema/coverage incompatibilities. Lexically equivalent strings are normalization differences. The **712** potential semantic disagreements require authoritative review and are **not** confirmed errors. 55 differences remain unresolved. Raw OpenAlex-versus-current OpenAlex snapshot drift affects **36** works separately, including **15** now outside the original frame; it is not added to the 2,597 cross-provider rows. The original conflict table remains unchanged.
