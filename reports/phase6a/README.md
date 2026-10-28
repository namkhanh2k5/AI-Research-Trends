# Published Phase 6A aggregate audit tables

These are byte-identical copies of small aggregate outputs from the verified local run `data/analysis/phase6_topic_pilot_20261028_v11/`. The local run manifest hashes its 16 outputs; an independent v12 rerun matched all 16 output hashes. The published support chart has SHA-256 `aeb0ef4907ed1d40ae589fce5a9384ea0e4d777db7ffe5cc23c1166c56ad58b4`, also identical to the local source figure.

| File | SHA-256 |
|---|---|
| `topic_summary.csv` | `239447fc2f925b19dbcc16e516bdc9e5a37016e21d0adae1a57d8bd72fc3d3c6` |
| `topic_by_year.csv` | `20f84faabc3c453951c713b8327c18e436ae36073391c30d016a9077bc5f8d0b` |
| `topic_by_type.csv` | `75a007e68f173223c0e00e9ed8d9a7829aceba87a388a917161560ba9c54ee6c` |
| `topic_by_language.csv` | `0a192d9faf8b11d9633fd3015c089107f914fed1b8c52954f2cf59377b29c90b` |
| `top3_cooccurrence.csv` | `8771ea4dad522134dc67aab51a738f59cb6cc64b1203ed3f28e3626252759119` |
| `scope_review.csv` | `38ed7e4176b01ab59dc2fb5d5074822be05a15d914428810a6a0fabe4c20bb6b` |
| `per_class.csv` | `c2e75b3bcd784d3786577982a7fe105d8441c6e1c996cc9f5d6ce0e574c115ee` |
| `confusion_matrix.csv` | `405b7db3e14bedd45c8adc539fa5c3b2af4b076cf0d3236c61d55f163eab29f7` |

No paper-level text, Work IDs, prediction rows, blind annotation sheets, answer keys, fitted models or source Parquet files are published here. The topic-by-year audit includes descriptive 2025 source-label counts; the selection code uses only 2020–2023 training and 2024 validation support, never the 2025 counts.
