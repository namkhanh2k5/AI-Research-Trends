# Model and data artifact contract

| Artifact | Local default | Git policy | Verification |
|---|---|---|---|
| Phase 2 web package | `data/analysis/finalization_p2_web_data_20261101_v3/` | tracked; Parquet in LFS | `openalex-build-web-data verify ...` |
| Frozen SVM bundle | `models/finalization_p3/topic_placement_v2/` | tracked; joblib in LFS | `TopicPlacementService` manifest/hash check |
| Paper-discovery text index | `data/analysis/paper_discovery_original_sample_v1/` | Git-ignored, rebuildable; no duplicate abstracts committed | `openalex-paper-discovery verify --works ... --web-dir ...` |
| Phase 3 experiment | `data/analysis/finalization_p3_models_20261101_v1/` | tracked; binary outputs in LFS | `openalex-verify-final-ml ...` |
| Blind human package | `data/analysis/finalization_p2_human_review_20261101_v1/` | tracked in public repository | `openalex-prepare-human-review verify ...` |
| Reviewer ratings | `data/analysis/finalization_p4_human_ratings/` | ignored/private | `openalex-prepare-human-review validate-ratings ...` |
| 2025 test/registry | Historical data/analysis paths | published historical state | independent seal no longer valid after publication |

The paper index contains only original 12,000 sample works, not targeted expansion. The source manifest lists per-file SHA-256 and package creation time. The bundled SVM fits 2020–2023 integrated historical data and has no retraining on 2024 or 2025. Its margins and rejection threshold are frozen. A matching checksum proves byte integrity relative to the approved manifest; it does not grant rights to distribute abstracts or make untrusted pickle loading safe.

Public GitHub clones can fetch retained artifacts with Git LFS. Verify their original manifests before use; do not load an arbitrary joblib. Publication does not establish rights to redistribute OpenAlex abstracts or run a public website. See `docs/FINALIZATION_P2_WEB_DATA_CONTRACT.md` and the Phase 3 inference report for complete schemas and source hashes.

For content-similarity discovery, fetch the retained original `works.parquet` LFS file and run `openalex-paper-discovery build` once. The package contains only display metadata, a sparse matrix, and a portable JSON vocabulary/IDF representation (no pickle); it records the canonical works and web-manifest SHA-256 values. It is separate from the frozen SVM and never changes its manifest. The index is not bundled on GitHub because the retained canonical works allow deterministic local reconstruction and avoids an extra binary copy of research text. See [the web application guide](WEB_APPLICATION.md).

## Checksum-verified local restoration (authorized files only)

The repository now includes `openalex-restore-local-artifact`, a **local copy** tool. It does not download or deserialize a model. Its default is a dry run; `--execute` verifies every manifest-listed SHA-256 and size, copies to a temporary sibling directory, verifies the copy, and renames it to a previously unused destination. An existing destination is refused. The source must be a trusted, separately supplied versioned package with its original manifest. The manifest itself should be authenticated against the approved source: for the current local snapshot the web manifest is `a3378abf249b567cf34893cefa7d56d6291577a8e9c9ce5ec85a31640f13c15d`; the model manifest is `fb78307f219c933e35151a905ca327e00a058ec4cca3c99f294d41b0ab93907d`.

From an authorized machine, first inspect the proposed sources, then use distinct empty paths inside the new clone:

```bash
openalex-restore-local-artifact web --source /authorized/web-package --destination data/analysis/finalization_p2_web_data_20261101_v3
openalex-restore-local-artifact model --source /authorized/model-bundle --destination models/finalization_p3/topic_placement_v2
# Review the printed manifest SHA-256 against the approved values above, then repeat with --execute.
openalex-restore-local-artifact web --source /authorized/web-package --destination data/analysis/finalization_p2_web_data_20261101_v3 --execute
openalex-restore-local-artifact model --source /authorized/model-bundle --destination models/finalization_p3/topic_placement_v2 --execute
openalex-build-web-data verify data/analysis/finalization_p2_web_data_20261101_v3
```

The model service performs its own frozen-bundle compatibility check before inference. Do not trust a manifest supplied by an unknown party merely because its internal file hashes match. This workflow was exercised on a separate `/tmp` destination with the actual 22-file web package and 3-file model bundle; the web verifier passed with 12,000 indexed works and 14 Topic Briefs. It is **not** a public artifact-distribution mechanism, and a clean clone without approved source packages still cannot run the full site.
