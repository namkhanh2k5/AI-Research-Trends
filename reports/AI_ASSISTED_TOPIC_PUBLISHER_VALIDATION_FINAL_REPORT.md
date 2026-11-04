# AI-assisted topic and publisher validation — bounded final experiment

## Executive summary and decision

**AI topic assessment: COMPLETE for the bounded blind sheets; human semantic validation: PENDING. Publisher validation: PARTIAL EVIDENCE — FURTHER REVIEW REQUIRED.** The assistant assessed all 14 frozen topic definitions, all 40 blind calibration papers, all 100 blind evaluation papers, and the original 30 RQ7.1 publisher-recovery cases. The final private run is `data/analysis/ai_assisted_validation/ai_assisted_20261104_v2/` (manifest SHA-256 `8e3001d0d3e8bd63b5a99b6aa43d24ca5f234d54cc346649028f1f147b64a608`). All record-level paper text, decisions and evidence URLs remain Git-ignored.

The topic decisions offer a prioritized *review workload*, not an independent estimate of OpenAlex label accuracy. Official publisher sources support nine selected cases; 21 remain unresolved. Neither result authorizes a replacement of the official 12,000-work analytical dataset.

## Inputs and isolation

The Catalogue B YAML and official-topic metadata SHA-256 checks passed (`e4b34974…fdda9` and `024f9f13…33d86`). The blind reviewer package checksum validator passed: two isolated reviewer folders; 40 calibration and 100 evaluation papers; 14 randomized options; no source-label/prediction columns and no copied restricted key. The original RQ7.1 run and its 30-case publisher sheet passed their read-only verifier. The blind-sheet generator in `topic_final_validation.py` takes its calibration/evaluation frames from the 2024 validation subset after first restricting development works to years ≤2024; thus its **code path excludes 2025** without inspecting sealed labels. The AI audit used a **separate** ignored directory, did not enter answers into reviewer folders, and did not open restricted answer keys, frozen-model predictions, or 2025 test labels. The 2025 protocol still says `allow_final_test_execution: false` and human review is pending.

The source-defined analytical corpus and the original 12,000-work sample have **not** changed. The 30 publisher cases were not redrawn to make verification easier. Full source hashes and output hashes are in the private manifests; the [reviewer handoff](AI_ASSISTED_VALIDATION_REVIEW_HANDOFF.md) gives verification commands.

## Fourteen-topic scope and paper judgments

The [scope report](experiments/AI_TOPIC_SCOPE_VALIDATION.md) records one clearly defined, five mostly clear, six overlapping, one ambiguously scoped, and one expert-review-needed topic. Especially important are the broad `T10028` “Topic Modeling” description, its overlap with `T10181` NLP; broad `T10036` CV versus narrower segmentation/tracking/action topics; robotics-oriented `T10462` versus generic RL; and GAN-named `T10775` versus diffusion generation. These are semantic *boundary* issues, not proof of wrong OpenAlex labels.

| Blind set | Total assessed | Catalogue choice | `NONE` | `UNCLEAR` | Plausible secondary topic |
|---|---:|---:|---:|---:|---:|
| Calibration | 40 | 20 | 20 | 0 | 12 |
| Evaluation | 100 | 46 | 52 | 2 | 22 |

Two corrections were made after full-abstract re-review, in a **new** v2 run while preserving the frozen v1 evidence. The [topic assessment report](experiments/AI_TOPIC_LABEL_ASSESSMENT.md) gives topic distribution, confidence categories and a failure taxonomy. A paper that uses an AI tool in another discipline is not automatically a contribution to a selected method topic; neither `NONE` nor `UNCLEAR` is a human-validated error label. A high-confidence AI choice is not calibrated correctness. With zero genuine reviewer submissions, semantic accuracy, precision/recall/F1, and human agreement are **NOT VERIFIED**.

## Publisher verification

Thirty DOI resolutions were attempted against the existing RQ7.1 cases. Source-backed decisions required publisher-maintained article/journal/company evidence, with aliases considered rather than assumed errors. The [publisher source report](experiments/AI_PUBLISHER_SOURCE_VALIDATION.md) details the evidence standard and limitations.

| Decision | Number |
|---|---:|
| Source-backed correct name | 6 |
| Source-backed acceptable alias | 3 |
| Source-backed incorrect | 0 |
| Ambiguous identity/relation | 12 |
| Insufficient evidence | 4 |
| Source access blocked | 5 |
| **Total** | **30** |

Among the *nine source-verifiable* cases, 9/9 are consistent, with a mechanical Wilson 95% interval [0.701, 1.000]. This is a selectively verified convenience subset, **not** an accuracy estimate for all 30 or for the 167 recovered publisher values. One positive case has additional independent directory evidence. Some DOI pages identify a preprint platform but not the legal publisher or parent; aggregator mirrors were not treated as official confirmation. Human publisher adjudication is 0/30.

## External activity and failure analysis

The dedicated DOI collector recorded 30 direct GET attempts, 74 observed HTTP transactions including redirects, and a configured cap of 120. Four exploratory direct GET attempts were separate; their redirect-level count is unavailable. Five browser-search calls submitted 20 queries; backend HTTP count is unavailable. No CAPTCHA or access-control bypass, full-text download, OpenAlex crawl, Crossref bulk fetch, model training or 2025 evaluation occurred. HTTP 403/404, bot verification, PDF-only metadata and platform/publisher distinctions explain unresolved cases. The exact overall underlying HTTP transaction count is **NOT VERIFIED**, so only the collector's bounded accounting is asserted.

## Reproducibility and test evidence

The private v1 and v2 runs are independently hashed; v2 records its v1 parent manifest and two corrections. A read-only `verify-run` passed with 14/40/100/30 and six frozen artifact hashes. Phase 2: 123 pages and 12,000 unique works verified; Phase 3: 29 checks/eight tables passed; Phase 4: 18 checks/64 outputs passed; RQ6: 14 topics/eight CSV/five PNG passed; RQ7: 1,500 works/1,427 hashes passed; RQ7.1: 14 source hashes/100-case sample passed. Human package validator passed with zero human ratings. Frozen model bundle: 3/3 files matched SHA-256; web package: 22/22 files matched SHA-256. These checks are read-only and do not imply independent scientific correctness.

Offline tests: `.venv/bin/python -m pytest -q -ra -o addopts=''` → **283 passed, 9 skipped, 0 failed** (browser and opt-in OpenAlex tests skipped). `.venv/bin/python -m pip check` → **No broken requirements found**. No test or verifier was allowed to read the 2025 label columns for this experiment.

## Final RQ7 decisions

| Proposed action | Gate | Evidence-based reason |
|---|---|---|
| Targeted, versioned publisher enrichment | **CONDITIONAL GO** | Nine official-source-consistent cases suggest potential value, but sample selection and 21 unresolved cases require human checking and a broader designed validation sample. |
| Broad Crossref enrichment | **NO-GO now** | Source identity, aliases, licences and conflicts are not validated at scale. |
| Full 12,000-work RQ7 ETL expansion | **NO-GO now** | The 30-case audit cannot justify its data quality or collection cost. |
| Replace original analytical dataset | **NO-GO** | RQ1–RQ6 must retain their approved population/sample provenance; targeted dual-source data are experimental. |

The smallest next task is to give the *unchanged* blind human packages to two independent people, keep this AI audit hidden until their sheets are frozen, and adjudicate selected unresolved publisher cases against official sources. Do not open the 2025 test or re-label the official corpus because of this AI experiment. The [evidence-level boundary statement](experiments/AI_VS_HUMAN_VALIDATION_BOUNDARIES.md) defines the permitted academic claims.
