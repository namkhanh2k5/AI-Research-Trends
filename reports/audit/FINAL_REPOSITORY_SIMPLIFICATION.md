# Final repository simplification audit — 2026-11-05

Starting point: fresh clone of `main` at `6bcd800c03be50b5792b3a7f9fa11b7f7e84ff2b`. This change is a layout and consumer-contract refactor, **not** a new OpenAlex collection, model fit, scientific analysis, or 2025 evaluation.

## Active dependency map

| Workstream | Canonical product | Consumer / verification |
|---|---|---|
| Data collection | `data/raw/openalex_stratified/stratified_20261019T155909Z/` and `data/metadata/` | `openalex-verify-collection` |
| Data processing | eight original tables in `data/processed/openalex_stratified/stratified_20261019T155909Z/`; separate integrated ML tables in `data/processed/ml_topic_classification/finalization_p2_20261101_v3/` | `openalex-validate-processed`, `openalex-verify-integrated-topics` |
| Research analysis | Phase 4, Phase 5 and Phase 6 versioned runs in `data/analysis/` | their original manifests and read-only verifiers |
| Machine learning | `models/topic_placement_v2/` | frozen `TopicPlacementService`; original model manifest and binary hashes |
| Web application | `data/artifacts/web/topic_explorer/`; rebuildable `data/artifacts/web/paper_discovery/` | `config/application.yaml`, `ResearchData`, `PaperDiscovery`, Streamlit |

Population aggregates, the original 12,000-work analytical sample, targeted ML expansion and the integrated ML dataset are separate entities. No table grain or schema was changed; no expansion work was added to a population denominator. The Phase 5 citation-recommendation feasibility result and the 14-topic catalogue were not changed.

## Artifact decisions and migration

The verified 22-file Topic Explorer package moved byte-for-byte from its run-named `data/analysis/finalization_p2_web_data_20261101_v3/` path to `data/artifacts/web/topic_explorer/`. The three-file frozen model bundle moved byte-for-byte from `models/finalization_p3/topic_placement_v2/` to `models/topic_placement_v2/`. Each old path is a narrow symbolic link to its canonical target. These links are required by historical command examples and by the **hash-frozen** `final_inference.py` CLI default; the frozen inference module and model manifest were not edited. The new `config/application.yaml` is the authoritative location contract used by the active web service and Paper Discovery builder. Overrides remain available through the existing environment variables.

The five-topic pilot catalogue, historical collection plan and proposed integration schema moved to `config/historical/` without changing their bytes. Their former paths are symbolic links because historical documents/manifests refer to them. `config/topics.yaml`, the frozen 14-topic catalogue, its metadata CSV and the frozen evaluation protocol remain in their existing locations. No YAML content was merged into the frozen catalogue or used to change scientific settings.

Eight exact duplicate payloads (1,526,412 bytes in total) were byte-compared before replacement by relative links to their canonical copies: seven Phase 1 published aggregate summaries now reuse the gap/quality/label-drift files, and the Phase 5 reassessment eligibility CSV reuses the identical pilot CSV. The old published-summary manifest retains the original SHA-256 values and all seven link targets still match. Reviewer A/B blind sheets remain physically separate despite identical bytes because reviewer-package isolation is a scientific contract. Phase 4-to-web CSV copies remain in the independently verifiable web package; linking them to Phase 4 would make the deployed package less self-contained. The incomplete first topic-population run, distinct model experiments and historical manifests were retained as evidence, not discarded as apparent duplicates.

| Deduplicated file(s) | Grain / identity | Data rows before and after | Schema change |
|---|---|---:|---|
| P1 `data_gap.csv`, `topic_support.csv` | one selected topic | 14 each | none |
| P1 `by_year.csv`, `by_type.csv`, `by_language.csv` | year, type, language respectively | 4, 3, 27 | none |
| P1 `label_drift_transitions.csv` | old/new primary-topic pair | 48 | none |
| P1 `label_drift_summary.json` | one aggregate object | one object | none |
| Phase 5 `query_eligibility.csv` | one original-sample Work ID | 12,000 | none |

The old and canonical files were compared byte-for-byte, so column names, null encodings, row ordering and numerical aggregates are identical. The links do not imply that the P1 published package and source audits are the same *study stage*; their separate manifests remain intact.

No intermediate experiment was silently eliminated. The current data tree still contains versioned historical P1/P2/P3 runs; these are not active web defaults. A larger migration would require an explicit historical-path manifest and regeneration/consumer audit, and is not justified by a mere directory-count reduction.

## Before and after

| Measure | Before | After |
|---|---:|---:|
| Tracked files | 1,095 | 1,103 |
| Physical second-level data directories | 22 | 22 |
| Top-level `data/analysis` run directories | 16 | 15 |
| Confirmed duplicate payload copies in this migration | 8 | 0 (links to canonical bytes) |
| Original analytical/ML canonical datasets | 2 distinct | 2 distinct, unchanged |
| Scientifically distinct intermediate/historical runs removed | 0 | 0 |
| Active root YAML regular files | 6 | 4 (plus 3 historical aliases) |
| Historical YAML regular files under `config/historical/` | 0 | 3 |
| Test modules | 34 | 35 |
| Installed `openalex-*` CLI entry points | 52 | 52 |
| Source Python modules | 89 | 89 |
| Root-level Markdown documents | 2 | 2 |
| Broken active web artifact links or paths found by tests | 0 | 0 |
| Offline tests | 253 passed, 4 skipped | 263 passed, 9 skipped with Playwright installed (browser opt-in disabled) |
| Real Chrome browser tests | not run in this clone | 7 passed |

Tests now live under `tests/unit/`, `tests/integration/` and `tests/browser/`; finalization-era names were replaced with functional ML/data names where appropriate. Two small overlapping topic-discovery/validation modules were combined without deleting assertions. The count rose because active-path and alias-integrity regression tests were added. The 52 historical CLI commands remain installed: removing them would make existing reproduction instructions fail without a replacement interface. Routine commands are grouped by five workstreams in the README; this is an intentional non-reduction, not a claim of CLI consolidation.

## Read-only verification and invariants

The following were run against the fresh clone after migration:

- `openalex-verify-collection`: PASS, 123 pages, 12,000 unique Work IDs; original raw SHA-256 `b8734cd3da2cba8c2c9ff8a9742d46d62585e55604f18630274f6bb8fbc178af`.
- `openalex-validate-processed`: PASS, 29 checks and all eight tables; original `works.parquet` hash `9318c456d916b8c9a35b0a3c86a829a92347083357693593e743abb0253264d4`.
- `openalex-validate-phase4`: PASS, 64 outputs. Original Phase 4 manifest hash `b7062e9bef99a477a3cb457661378584c1be667d84e04cbc110cada9ddbb96aa`.
- `openalex-verify-literature-audit`: PASS, 25 outputs, decision `REVISE` for the bounded citation-recommendation audit.
- `openalex-verify-phase6`, `openalex-verify-topic-run`, and `openalex-verify-rq6 --published-dir reports/finalization_p2`: PASS; 6 historical identities and 14 topic-support rows.
- `openalex-verify-integrated-topics`: PASS, 14,515 source rows, 14,470 canonical groups, 7,002 training and 1,843 development rows; 2,318 historical 2025 test rows checked only as a total. The former expansion interim file is unavailable in this clone and was reported as such; 15 retained inputs were verified.
- `openalex-verify-final-ml` on closed and open-set development runs: PASS, 14 and 23 files respectively.
- `openalex-build-web-data verify`: PASS, 22 outputs, 12,000 paper-index rows and 14 topic briefs. Manifest hash remained `a3378abf249b567cf34893cefa7d56d6291577a8e9c9ce5ec85a31640f13c15d`.
- Frozen model load/inference with the moved bundle: PASS; unchanged model SHA-256 `b066ba80ab0768052f585fa1ed2e6b56c24f46c511508b3394580452e40bb788`, same source-code compatibility check, manual confirmation still required.
- `openalex-paper-discovery build` and `verify`: PASS; rebuildable ignored index contains 11,558 original-sample works. This index is local generated output, not a tracked scientific artifact.
- `python -m pip check`: no broken requirements; `python -m compileall -q src dashboard deliverables tests`: PASS.
- Local Streamlit health on `127.0.0.1:8501`: `ok`; seven real Chrome tests passed, including navigation, inference, manual confirmation, stale-state reset, missing-model fallback, discovery and desktop overflow checks. These do not establish public deployment readiness.

The collection, processing, Phase 4, integrated ML, web and model manifest bytes all retained their previously recorded SHA-256 values. No altered source representation is claimed to retain the same hash; this migration changed only paths and links. Historical result manifests were not rewritten. The model's manifest says the 2025 test was sealed at model-build time; because test-label files were subsequently published in repository history, **the current public repository cannot claim an independently sealed 2025 final evaluation**.

## Remaining limitations

The repository still contains many historical, scientifically distinct analysis directories and 52 installed commands. Moving or deleting them merely to lower a count would break recorded paths or sacrifice reproduction evidence. The legacy aliases require filesystem symlink support; Ubuntu/Linux is verified, while Windows checkout behavior is not. The separate Paper Discovery index must be rebuilt after clone. Some private development aggregate files and the retired expansion interim file are absent from this fresh clone, so their independent restoration was **not verified**. Browser checks covered desktop, not a comprehensive mobile/responsive review. Neither data redistribution rights nor a public hosted deployment were established by this refactor.
