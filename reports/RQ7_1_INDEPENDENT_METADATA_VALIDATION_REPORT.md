# RQ7.1 — Independent metadata validation and scale-up gate

## Executive decision

**NO-GO for immediate full 12,000-work Crossref expansion; CONDITIONAL GO only for bounded, source-reviewed publisher enrichment.** Original RQ1–RQ6 scientific outputs and the frozen classifier remain unchanged. The final human correctness gate is **PENDING_HUMAN_REVIEW**.

## Verified baseline and design

The existing RQ7 verifier passed: 1,500 canonical works, 30 OpenAlex batches, 1,387 Crossref tasks, nine Parquet tables, 1,427 checksummed artifacts. Source-level SHA inventory contains 14 files. The fixed-seed private sample has 100 unique works, with primary groups 30 publisher, 30 license, 20 conflict and 20 Crossref 404; secondary overlap is preserved. It is diagnostic, not population-representative. [Sampling details](experiments/RQ7_METADATA_VALIDATION_SAMPLING.md).

## Publisher and license

Publisher coverage increased by 167 works. **1/30** selected recovered values have an AI-performed source-backed check; **0/30** have human adjudication. The one-case Wilson interval is uninformative and cannot support a full-cohort accuracy claim. [Publisher audit](experiments/RQ7_PUBLISHER_CORRECTNESS_AUDIT.md).

License metadata appeared in 277 formerly missing records; 277 have syntactically valid stored URLs, 0 show a conservatively recognized CC licence identifier, and 270 carry content-version metadata. A bounded ten-URL HEAD check got 2 direct 2xx responses. These do not establish unrestricted reuse rights or OA status. [License audit](experiments/RQ7_LICENSE_SEMANTICS_AUDIT.md).

## Conflicts and DOI agency

All 2,597 original provider-field differences were reclassified without discarding rows: taxonomy 944, date-definition 314, normalization 47, schema/coverage 525, potential semantic 712, unresolved 55. Potential does not mean proven error. Snapshot drift (36 works) is separate. [Conflict audit](experiments/RQ7_CONFLICT_RECLASSIFICATION.md).

Of 20 selected stored Crossref 404 cases, the DOI Foundation identified 19 as DataCite registrations; one remains unresolved with `DOI does not exist` status. No DOI syntax problem was observed in this sample. [DOI audit](experiments/RQ7_CROSSREF_404_AUDIT.md).

## Evidence quality, cost and downstream value

New direct external HTTP attempts: 20 DOI Foundation GET plus 10 allowlisted license-policy HEAD = **30**; no new OpenAlex or Crossref requests. Separately logged browser activity: 11 bounded publisher searches, 2 DOI documentation searches and 3 attempted DOI opens. Browser backend HTTP counts are not observable. Human publisher accuracy, legal license applicability, and full-cohort 404 agency distribution are **NOT VERIFIED**. Source responses and review sheets stay local/Git-ignored. Full-scale request/storage estimates are scenarios, not guarantees. [Validated quality](experiments/RQ7_VALIDATED_DATA_QUALITY.md); [scale decision](experiments/RQ7_12000_WORK_SCALE_UP_DECISION.md).

## Exit-134 diagnostic

The prior chained Python shutdown abort is not evidence of data corruption. Two standalone `PYTHONFAULTHANDLER=1` verifier runs exited 0 and returned PASS. Python 3.12.3; pandas 2.3.3; PyArrow 21.0.0; requests 2.34.2; NumPy 2.5.4. Status: **NOT REPRODUCED — ROOT CAUSE UNKNOWN**. Diagnostic file SHA-256: `9cb176d8759ed3be9b681f0869c48ae305e9280417e926d1eceda61e4bdc1145`. Do not claim a root cause.

## Preservation and validation

Read-only checks: original Phase 2 raw (123 pages/12,000 unique works), Phase 3 (29 checks/eight tables), Phase 4 (18 checks/64 outputs), prior venue experiment (654 output hashes/seven figures), and final ML bundle (14 files; **2025 FINAL TEST SEALED**) all returned PASS. No source artifact was rewritten. Full offline test command: `.venv/bin/python -m pytest -q -ra -o addopts=''` — **270 passed, 9 skipped, 0 failed**. `pip check`: No broken requirements found. Execution evidence is private at `data/analysis/rq7_quality_validation/rq7_1_20261104_v2/validation_execution.json` (SHA-256 `e2909c4cc1aeec0b7e96e8c6803f21364ddb9a342d28f66e8ed20a04864d4c13`). These verifiers do not substitute for human metadata validation.

## Research outcome

The original analytical dataset remains the official basis for RQ1–RQ6. This experiment demonstrates the distinction between metadata coverage and validated quality. Any subsequent publisher enrichment requires a real official-source/manual sample review. Do not treat Crossref license arrays as rights grants. No broad data collection, model retraining, or sealed-test access occurred.
