# Pre-change repository inventory (2026-11-05)

This inventory was recorded against a fresh `main` clone at
`d0633de786756d74ae64861e7f98d621e5989f9c`, before changing existing files.
It is an artifact-retention decision record, not a new scientific experiment.

| Class | Examples and reason |
| --- | --- |
| A — essential | Original 12,000-work collection, eight processed tables, population and sampling manifests, Phase 4 verified outputs, frozen ML bundle, 2024 development evidence, 2025 test gate, web-data package, source and tests. Removal would break the published study or its verification. |
| B — canonical | `data/analysis/phase4_stratified_20261019T155909Z_v3/`, `data/analysis/phase6b_topic_validation_20261028_v3/`, `data/processed/ml_topic_classification/finalization_p2_20261101_v3/`, `models/finalization_p3/topic_placement_v2/`. |
| C — verified duplicate content | The 16 non-manifest files in `phase6_topic_pilot_20261028_v12/` and `phase6a_reproduction_20261028_phase6b/` compare byte-identically; their **manifests differ**, reflecting separate run identities. This is not permission to erase either run. |
| D — historical | Phase 6A pilot/reproduction, the Phase 6B metadata run, earlier predeclared protocols and handoff reports. They document distinct scientific decisions and must stay traceable even when no longer primary entry points. |
| E — obsolete | No artifact classified as safe to delete on filename or age alone. Candidates require consumer and manifest checks first. |
| F — uncertain | Any run directory or protocol cited in another manifest, test, command or immutable report. Retain at its current path until the dependency is resolved. |

Baseline: 1,125 tracked files; 28 top-level documentation Markdown files;
59 report Markdown files; 767 tracked `data/` files; 35 Git LFS paths;
21 versioned `data/analysis/` run directories. The Phase 6 family has five
scientifically distinct analysis directories. A physical move can preserve a
file hash while breaking a manifest-relative path or frozen source-hash check.

The existing cleanup policy in `docs/REPOSITORY_CLEANUP.md` already removed
older superseded runs. The integrated split manifest hashes
`docs/FINALIZATION_P2_INTEGRATION_PROTOCOL.md`; the Phase 4 manifest hashes
`docs/PHASE4_STATISTICAL_ANALYSIS_PLAN.md`. Both documents must remain
byte-unchanged at their documented paths. Original run manifests and numerical
outputs must not be rewritten merely to simplify naming.

Planned safe changes: replace fragmented *navigation* with canonical guides and
a unified Phase 6 report, consolidate only unprotected overlapping narrative,
test repository links and artifact resolution, and retain protected data/run
paths with an explicit mapping. Do not inspect 2025 labels, retrain, recollect,
or imply that published 2025 data are independently sealed.
