# Repository reorganization and verification (2026-11-05)

Fresh clone: `main` at `d0633de786756d74ae64861e7f98d621e5989f9c`.
No prior checkout was reused. The [pre-change inventory](REORGANIZATION_INVENTORY.md)
records artifact classes and protected paths. No collection, model fitting,
scientific recomputation, 2025-label inspection or history rewrite occurred.

## What changed

| Measure | Before | After | Decision |
| --- | ---: | ---: | --- |
| Tracked files | 1,125 | 1,120 | 16 redundant narrative files removed; 11 guides/tests/mapping files added; published Phase 6 files moved without changing content |
| Top-level `docs/*.md` | 28 | 23 | Nine duplicate/obsolete guides merged into four current guides; protected and preregistered protocols retained |
| `reports/**/*.md` | 59 | 56 | Seven historical handoff/PR wrappers removed; inventory, index, unified Phase 6 report and this report added |
| Tracked `data/` paths | 767 | 767 | No data file or numerical result changed or removed |
| Tracked data logical size after LFS restoration | 635,181,520 bytes | 635,181,520 bytes | Zero data-size reduction; provenance takes priority |
| Git LFS paths | 35 | 35 | No LFS pointer or binary changed |
| Versioned `data/analysis/` run dirs | 21 | 21 | Original run identities and manifest-relative paths preserved |
| Proven duplicate run outputs removed | 0 | 0 | Sixteen pilot/reproduction output pairs have equal SHA-256, but separate manifests; deleting one breaks independent verification |
| CLI entry points removed | 0 | 0 | Existing reproducibility commands remain available |

The current navigation is [README](../../README.md) →
[project overview](../../docs/PROJECT_OVERVIEW.md),
[research methodology](../../docs/RESEARCH_METHODOLOGY.md),
[web application](../../docs/WEB_APPLICATION.md),
[reproducibility](../../docs/REPRODUCIBILITY.md), and
[report index](../README.md). The original pre-analysis research questions,
Phase 4 statistical plan, final integration protocol, Phase 6 selection and
human-review protocols remain because they document decisions before results
or are directly hashed in manifests. The Phase 1 proposal and review, duplicate
feasibility pointer, repeated setup/architecture/web/discovery/limitations
guides were consolidated; their historical versions remain in Git history.
The seven removed handoffs and PR-description wrappers repeated findings now
available in final stage reports. The final reports, analytical tables, scope
tables, model manifests and research figures were not deleted.

## Phase 6 physical consolidation

The *published aggregate* directories moved from `reports/phase6a/` to
`reports/phase6/pilot/`, from `reports/phase6b/` to
`reports/phase6/validation/`, and the original PNG to
`reports/phase6/figures/`. Every moved aggregate CSV and the PNG still matches
the corresponding source run's declared SHA-256. The Phase 6 synthesis and
[artifact map](../phase6/artifact_map.json) distinguish five identities:
pilot v12, independent pilot reproduction, topic metadata, canonical
fourteen-topic validation v3 and later integrated RQ6. No experiment was
renamed or represented as if all stages were executed together.

All five Phase 6-related `data/analysis/` directories were retained in their
original locations. Pilot v12 and its reproduction have 16 byte-identical
non-manifest files (tested by SHA-256) but **different** manifests. Neither
whole-run directory is redundant scientific evidence; the source files already
share Git blob content where identical. The canonical 6B manifest still hashes
to `8adeee71c0b37d3e5b85d06360d2d471b72618daf1a4427b023570664bac9c79`.
No original manifest or frozen model bundle was rewritten.

## Fresh-clone verification

The first fresh-clone attempt exposed historical absolute paths in the Phase 2
and Phase 3 verifiers. Their read-only resolution now accepts only the expected
current-checkout path and the original SHA-256. The retired original interim
JSONL is absent from LFS; the original raw JSONL has the **same recorded hash**.
Both verifiers report `verified_identical_raw_fallback` only if that exact raw
content and its manifests pass. A present corrupted interim file still fails.
This confirms byte-equivalent processing input, **not** independent restoration
of the interim file. New negative tests cover wrong paths, mismatched hashes and
tampering.

| Check executed in fresh clone | Result |
| --- | --- |
| `python -m pip install -e ".[dev,web,deliverables]"`, `python -m pip check` | Installed; no broken requirements |
| `python -m compileall -q src dashboard deliverables tests` | PASS |
| `python -m pytest -q -ra -o addopts=''` | **251 passed, 3 skipped** (optional browser dependency, opt-in live API probe, absent private development aggregates) |
| `openalex-verify-collection .../manifest.json` | 123 pages; 12,000 unique Work IDs; raw/interim-equivalent SHA-256 `b8734cd3...178af` |
| `openalex-validate-processed ...` | 29 checks; eight tables; works 12,000, references 289,110; same-byte raw fallback disclosed |
| `openalex-validate-phase4 ...` | 18 analytical checks; all 64 outputs verified |
| `openalex-verify-literature-audit ...` | Phase 5: 25 outputs, 3 published reports and 4 figures verified |
| `openalex-verify-topic-run ...`, `openalex-verify-rq6 ...` | Phase 6B: 34 outputs; integrated RQ6: 8 CSV/5 PNG and published match |
| `openalex-verify-integrated-topics ...` | 14,515 source rows, 14,470 groups, 7,002 train, 1,843 2024 validation, 2,318 mechanical 2025 total; eight output files and 15 retained inputs verified; retired `expansion_interim` unavailable |
| `openalex-verify-final-ml` (closed and open runs) | 14 and 23 files verified; verifier's historical `SEALED` field is **not** a current independent seal |
| `openalex-build-web-data verify ...` | 22 outputs, 12,000 paper rows, 14 Topic Briefs |
| `openalex-paper-discovery build` then `verify --works ... --web-dir ...` | Rebuilt ignored index; 11,558 indexed, 9,075 full-text-searchable; three index hashes verified; CLI search returned real sample IDs |
| `openalex-package-topic-model infer ...` | Frozen bundle loaded; returned `confident_suggestion`, top-three ranks, raw-margin warning and required confirmation on a non-test draft |
| Local Streamlit server and `/_stcore/health` | Server started on `127.0.0.1:8509`; response `ok`. This is a smoke check, **not** manual visual/browser QA. |
| Canonical Markdown link and artifact-map regression tests | All README, docs, reports and deliverables relative links resolve; Phase 6 source/published hashes match |

One extra broken canonical link was found by the new regression test and fixed
(`MODEL_AND_DATA_ARTIFACTS.md` → consolidated web guide); planned old Phase 6
table/figure paths were also updated. Zero broken relative Markdown links remain
in the tested documentation tree. `git diff --check` passed. `git diff` shows
no changes to `data/`, `config/`, `models/` or the academic report; protected
protocol file bytes and Phase 4/6 manifest hashes are unchanged.

## Limits and delivery gate

The targeted ML expansion's original interim JSONL was retired and has a
**different** hash/structure from its raw JSONL. Thus
`openalex-verify-ml-expansion` cannot verify the complete historical run from
this clone (`Missing or moved final JSONL`); no unsafe fallback was added.
The integrated-data verifier explicitly reports that historical input as
unavailable while verifying retained inputs and all outputs. Restoring the
original interim through an approved source is required for full replay of
that acquisition stage. Browser automation was not run because Playwright is
not installed in the declared default extras; localhost health and offline
tests do not establish responsive UI quality. External rights review and
genuine human topic validation remain unresolved. Published 2025 labels and
answer keys invalidate an independent final-test claim in this snapshot.

This cleanup is complete at the source-and-artifact-navigation level, with
the explicit historical-input and browser-test limits above. CI must be
checked after the verified commit is pushed; this report does not preclaim its
outcome.
