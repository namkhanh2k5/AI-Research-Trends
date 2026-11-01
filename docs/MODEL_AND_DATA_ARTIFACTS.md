# Model and data artifact contract

| Artifact | Local default | Git policy | Verification |
|---|---|---|---|
| Phase 2 web package | `data/analysis/finalization_p2_web_data_20261101_v3/` | ignored | `openalex-build-web-data verify ...` |
| Frozen SVM bundle | `models/finalization_p3/topic_placement_v2/` | ignored | `TopicPlacementService` manifest/hash check |
| Phase 3 experiment | `data/analysis/finalization_p3_models_20261101_v1/` | ignored | `openalex-verify-final-ml ...` |
| Blind human package | `data/analysis/finalization_p2_human_review_20261101_v1/` | ignored | `openalex-human-review verify ...` |
| Reviewer ratings | `data/analysis/finalization_p4_human_ratings/` | ignored/private | `openalex-human-review validate-ratings ...` |
| 2025 test/registry | Local sealed data/analysis paths | ignored/private | frozen gate; manual governance |

The paper index contains only original 12,000 sample works, not targeted expansion. The source manifest lists per-file SHA-256 and package creation time. The bundled SVM fits 2020–2023 integrated historical data and has no retraining on 2024 or 2025. Its margins and rejection threshold are frozen. A matching checksum proves byte integrity relative to the approved manifest; it does not grant rights to distribute abstracts or make untrusted pickle loading safe.

Public GitHub clones require authorized local regeneration or private transfer of these artifacts. Do not install the ignored model from an arbitrary remote. A public hosting decision is pending artifact-distribution review. See `docs/FINALIZATION_P2_WEB_DATA_CONTRACT.md` and the Phase 3 inference report for complete schemas and source hashes.
