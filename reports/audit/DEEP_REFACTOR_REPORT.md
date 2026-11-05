# Deep structural refactor — measured migration audit

Source: fresh `main` clone at `c0677db68264a8d43a453eda58b057f4077ae710`, 2026-11-05. No OpenAlex collection, model training, scientific recomputation or history rewrite was performed. The source commit remains available for byte-for-byte historical comparison. The current migration is about physical checkout organization, not a claim that experiments were rerun.

## Physical changes

The five Phase 6 research-run roots were moved into one canonical `data/analysis/phase6/` tree: `pilot/`, `metadata/`, `validation/`, and `topic_analysis/`. The first pilot and independent reproduction have **16 identical output hashes**; one physical output set now serves both identities. Their two distinct original manifests remain byte-unchanged, the second under `provenance/pilot_reproduction_manifest.json`. A separate RQ6 publication package also had **13 byte-identical outputs** to integrated RQ6; its original manifest remains under `provenance/rq6_publication_v2_manifest.json`, while the duplicate data files were removed. The reader-facing copies under `reports/` remain because those make small aggregate tables and figures accessible on GitHub without opening private run records.

The authoritative [Phase 6 migration manifest](../../data/analysis/phase6/manifest.json) lists the original directory, immutable manifest SHA-256, canonical artifact directory and expected output count for six histories. `openalex-verify-phase6` checks all six manifest bytes and all declared output hashes (113 declared output checks, including 29 verified duplicate relationships). The old-to-new resolver is explicit; consumers still compare the **original expected SHA-256**. A path match alone is never accepted. Historical verification means checking retained evidence, not replaying a prior run.

| Original path | Canonical destination | Decision |
| --- | --- | --- |
| `data/analysis/phase6_topic_pilot_20261028_v12/` | `data/analysis/phase6/pilot/` | Moved unchanged; 16 outputs retained |
| `data/analysis/phase6a_reproduction_20261028_phase6b/` | `data/analysis/phase6/provenance/pilot_reproduction_manifest.json` plus shared `pilot/` outputs | Distinct manifest preserved; 16 duplicate paths removed |
| `data/analysis/phase6b_topic_metadata_20261028_v1/` | `data/analysis/phase6/metadata/` | 21 metadata files moved unchanged |
| `data/analysis/phase6b_topic_validation_20261028_v3/` | `data/analysis/phase6/validation/` | 34 outputs and manifest moved unchanged |
| `data/analysis/finalization_p2_rq6_20261101_v3/` | `data/analysis/phase6/topic_analysis/` | 13 outputs and manifest moved unchanged |
| `data/analysis/finalization_p2_publication_v2/` | `data/analysis/phase6/provenance/rq6_publication_v2_manifest.json` plus shared `topic_analysis/` outputs | Distinct publication manifest preserved; 13 duplicate paths removed |

The pilot/reproduction manifests differ in run version, timestamp and execution timing; they describe different execution histories despite byte-identical numerical and paper-level output files. The RQ6 publication manifest describes a different publication packaging history; its source-manifest SHA is not asserted to be the canonical integrated RQ6 manifest SHA. Only its thirteen declared published output hashes were shown identical to canonical RQ6 outputs. No five-class result was merged with a fourteen-class result, no 6B open-set estimate was substituted for final integrated ML, and the original sample, targeted training expansion and full-population aggregates remain distinct.

## Documentation and reports

The root `docs/` now holds eleven main documents. Ten historical protocols moved to `docs/protocols/`, the slide brief to `docs/presentation/`, and the prior cleanup policy to `docs/archive/`. The two manifest-hashed protocols (`FINALIZATION_P2_INTEGRATION_PROTOCOL.md`, `PHASE4_STATISTICAL_ANALYSIS_PLAN.md`) stayed at their exact original paths and bytes. A deterministic mechanical migration script rebased Markdown links; original pre-migration protocol bytes remain recoverable from the source commit. Current guides explain the canonical Phase 6 structure without requiring a reader to infer it from historical run names.

Root-level reports dropped to `README.md` only. Reports moved by research phase (`research/phase1`–`phase5` and existing `phase6/`), ML development (`machine_learning/`), application (`application/`) and historical audits (`audit/`). Finalization P1 expansion is grouped under `machine_learning/data_expansion`; P2 integration under `machine_learning/integration`; P3 model work under `machine_learning`; P4 web delivery under `application`. Published figures, CSV tables, JSON evidence and the RQ6 aggregate publication package remain at their existing public paths. Phase 5's three original report bytes remain in its immutable analysis run; the relocated GitHub-readable versions differ **only by rebased figure links**, which the validator checks deterministically. The Phase 4 report generator now emits links relative to its new report location; its generated output matched the committed report in the test suite.

## Quantitative before/after

Counts are from Git index and current checkout after staging; tracked data bytes are logical checkout file sizes with LFS materialized, **not** historical Git storage. The baseline is the prior audited `main` commit above.

| Metric | Before | After | Difference |
| --- | ---: | ---: | ---: |
| Total tracked files | 1,120 | 1,095 | −25 |
| Root `docs/*.md` | 23 | 11 | −12 |
| Root `reports/*.md` | 44 | 1 | −43 |
| All report Markdown files | 56 | 57 | +1 (this audit) |
| Top-level `data/analysis/` directories | 21 | 16 | −5 |
| Top-level versioned analysis directories | 21 | 15 | −6 |
| Separate Phase 6-related run/publication roots | 6 | 1 | −5 |
| Extra tracked data paths with identical Git blob IDs | 49 | 20 | −29 |
| Tracked `data/` paths | 767 | 739 | −28 (29 removed, one canonical migration map added) |
| Tracked data logical bytes | 635,181,520 | 630,023,479 | −5,158,041 |
| Git LFS paths | 35 | 35 | 0 |
| Broken relative Markdown references in canonical test scope | 0 | 0 | 0 |
| Offline failing tests | 0 | 0 | 0 |

Git already deduplicates identical blobs within object storage, so deleting redundant tracked **paths** primarily improves layout and checkout footprint. It does not erase historical Git objects or guarantee an equivalent reduction in repository history size. The unchanged Git LFS objects are not claimed to have shrunk.

## Remaining data-directory decisions

Fifteen other versioned analysis roots remain deliberately separate. Phase 4 and Phase 5 are different research stages; Finalization P1 gap/quality/label-drift snapshots have different source and estimands; P2 human packages, topic-population versions and the web-data package have separate consumer contracts; P3 model/open-set/diagnostics have distinct frozen outputs. More identical-byte pairs exist (for example Phase 4 collaboration tables reused by web-data and several P1 published summaries), but those have active local application/publication consumers and were **not** removed on a hash match alone. The original 12,000-work collection, its eight processed tables, population aggregates, frozen model, web-data package and Paper Discovery index remain discoverable through `docs/MODEL_AND_DATA_ARTIFACTS.md` and `docs/REPRODUCIBILITY.md`. Future migration of those fifteen roots needs a consumer-by-consumer manifest and code audit; this report does not assert they are inherently immovable.

The active fourteen-topic catalogue remains `config/phase6b_catalogue.yaml`; `config/phase6_topic_catalogue.yaml` is historical five-topic pilot configuration, and `config/phase6b_topic_metadata.csv` is the frozen metadata source referenced by hashes. They were **not** renamed because integrated-data manifests and model/catalogue checks require their exact byte identities. CLI defaults for new pilot/validation runs now target new paths beneath `phase6/`, while the completed runs remain immutable.

## Verification and limits

Fresh-clone installation used `python -m pip install -e ".[dev,web,deliverables]"`; `pip check` and `compileall` passed. Offline tests: **253 passed, 4 skipped** (optional browser package, opt-in live OpenAlex probe, and two local-only aggregate/runtime checks). Phase 2 collection: 123 pages/12,000 IDs; Phase 3: 29 checks/eight tables; Phase 4: 18 checks/64 outputs; Phase 5: 25 outputs/three published reports/four figures; Phase 6: six historical manifests and all declared outputs; integrated topics: 14,515 rows/8 outputs; final closed/open model runs: 14/23 files; web-data: 22 outputs. A frozen-model inference returned a non-test `confident_suggestion` with top-three topics and confirmation required. Paper Discovery rebuilt from original works (11,558 indexed) and passed its read-only verifier. Streamlit started on localhost and returned `ok` from `/_stcore/health`; **browser-level/responsive UI was not tested**.

Two historical limitations remain. The targeted ML-expansion interim JSONL was retired and is not equivalent to its raw JSONL; integrated verification reports it unavailable rather than inventing a substitute. The P2 master manifest also names an absent historical integration rerun, so its full umbrella verification cannot pass in this clone even though the retained child outputs were independently checked. The historical 2025 test labels were published, so old manifest text saying `SEALED` is an earlier run status, **not** a current independently sealed-test claim. No CI result is claimed until the post-push workflow finishes.
