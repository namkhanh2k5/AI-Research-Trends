# Finalization Phase 4.1 — audit remediation and acceptance evidence

**Baseline:** independent read-only audit at `3a75abc76129d3063c5c79ab38dd6e085057d26a`, branch `feature/finalization-p4-complete-delivery`. This report concerns only the remediation branch `fix/finalization-p4-audit-remediation`. The original audit files in `reports/FINAL_INDEPENDENT_PROJECT_AUDIT.md` and `reports/final_audit/` are retained as a *pre-fix baseline*; their defect statements are not updated retroactively. The machine-readable [twelve-issue tracker](FINALIZATION_P4_1_AUDIT_ISSUES.json) contains root cause, affected source, regression and final status for **AUD-01 through AUD-12**.

**Current repository note:** Disposable browser/audit screenshots and the old one-off probe were removed after this historical report. Desktop/laptop Chrome tests remain opt-in; the two presentation images cited below remain tracked.

## Executive outcome

The P0 confirmation crash is repaired: real local Chrome followed **synthetic title/abstract → top-three suggestions → manual override → explicit confirmation → Topic Brief**, with no Streamlit exception. Changing either field invalidates suggestion and confirmation; reverting text does not resurrect stale state. The research site now surfaces RQ1–RQ6, a sourced model-comparison/open-set panel, richer Topic Briefs, an explicit Paper Explorer no-results state and working PDF download. The 11-page academic PDF was replaced by a **23-page A4 report** with separate cover/contents, numbered figures/tables, page numbers and substantially expanded methods, results and limitations; the presentation is **15 slides** with two genuine Chrome captures. No OpenAlex call, model training, scientific re-estimation or 2025 label access occurred.

## Traceability of the twelve original issues

| ID | Baseline severity | Final status | Verification / residual point |
|---|---|---|---|
| AUD-01 | P0 | FIXED AND VERIFIED | Chrome confirmation + Topic Brief; `official_name` contract. |
| AUD-02 | P1 | FIXED AND VERIFIED | Fingerprint invalidation; Chrome edit/revert/navigation and AppTest. |
| AUD-03 | P1 | FIXED AND VERIFIED | Substantive 23-page A4 report, RQ1–RQ6, ML, system, tests, appendices; all rendered pages inspected. No instructor-specific page/template requirement verified. |
| AUD-04 | P1 | PARTIALLY FIXED | Checksum-verified copy tested in separate clean local clone; authorized artifact supply and public rights remain external. |
| AUD-05 | P2 | FIXED AND VERIFIED | Chrome downloaded the actual `FINAL_ACADEMIC_REPORT.pdf`. |
| AUD-06 | P2 | FIXED AND VERIFIED | Source-checked model comparison, ablation, classwise F1, confusion and open-set development content. |
| AUD-07 | P2 | FIXED AND VERIFIED | Topic Brief includes sample-year/citation/OA/related-topic context, representative rule and provenance. |
| AUD-08 | P2 | FIXED AND VERIFIED | Separate RQ5 and RQ6 research panels with limitations and verified figures. |
| AUD-09 | P2 | FIXED AND VERIFIED | Year filtering and impossible keyword checked in Chrome; DOI URL validation, page reset and warning-free widget state verified. |
| AUD-10 | P2 | PARTIALLY FIXED | 15 slides and actual UI screenshots; scripted action types tested in Chrome, but no timed human rehearsal. |
| AUD-11 | P2 | FIXED AND VERIFIED | Cover, contents, A4, page field, captions and no split model table inspected in PDF. |
| AUD-12 | P3 | PARTIALLY FIXED | Offline CI checks restoration CLI; both PR #3 jobs succeeded. Chrome/local artifact checks remain deliberately opt-in. |

## Implementation and functional evidence

The first web patch changed `dashboard/app.py`, `src/ai_research_trends/web/service.py` and added aggregate-only `src/ai_research_trends/web/evidence.py` plus `reports/FINALIZATION_P4_RESEARCH_EVIDENCE.json`. The evidence contract records source SHA-256 for local Phase 3 closed/open-set results, Phase 5 pool comparison and published RQ6 support. Tests compare its values to the originals when locally available; no work-level abstract or sealed label is published. The Methodology page uses model names and denominators from this contract. “Gold vs closed” remains an **association on `ln(1+citations)`**, not a causal or raw-citation claim.

During the final browser run, Streamlit logged a `paper_page` warning because the number input had both an explicit default and a session-state value. A narrow follow-up patch initializes the key once and lets session state own the value. Paper Explorer Chrome regression and the complete eight-case browser suite passed again; the restarted server log contained no recurrence of this warning.

`deliverables/report/FINAL_ACADEMIC_REPORT.md` is the editable source; `deliverables/generate.py` regenerated DOCX/PDF and PPTX/slide PDF. The report now has 16 source-linked research/application figures and four numbered tables. A visual pass caught and fixed two concrete document issues: RQ-specific paragraphs initially sat under the following heading, and the model-comparison table split across pages. The final generator keeps the table together. The rendered PDF is A4, 23 pages, 1,837,261 bytes; the slide PDF has 15 pages, 1,055,585 bytes. LibreOffice conversion was actually executed; the PDFs are not placeholders. The 23-page count is below the task's approximate 25–35-page *goal* but above the audited 11-page baseline; no course-specific minimum or template was provided. It must be reviewed by the supervisor before formal submission.

The two tracked screenshot files are `deliverables/presentation/figures/home_chrome.png` (SHA-256 `c87f5aa1498ed43cfc46eaa1bb0a0cb02ecb271ef154f60db77746c9d110c244`) and `classify_confirmed_chrome.png` (SHA-256 `e276b40fba5e21cdc00c1fe670dc0fcd7dbd772139941e9507303c7377793823`). They were captured from the actual local application using a synthetic draft, not generated mockups or 2025 examples. The larger disposable browser-evidence collection was subsequently deleted. Historical viewport observations remain in this report, but its deleted screenshots are no longer independently inspectable from the current tree. Slide screenshots give layout evidence, not a substitute for a live demo or a usability study.

## Executed tests and scientific regression

On local Python 3.12 (virtual environment), the final offline command `.venv/bin/python -m pytest -q -ra -o addopts=''` passed **215 tests, 9 skipped**; eight skips were opt-in browser cases and one was live OpenAlex. `.venv/bin/python -m pip check` reported **no broken requirements**. The real Chrome suite, with `AI_TRENDS_RUN_BROWSER_TESTS=1`, passed **8/8** after the mobile navigation test was corrected to open/close Streamlit's responsive sidebar. The test also started a second Streamlit process with a deliberately missing model: classification showed an error while manual Topic Explorer stayed usable. A browser smoke check is not a human evaluation.

Read-only scientific verifiers all returned valid: original collection **123 pages, 12,000 unique IDs**, raw/interim JSONL SHA-256 `b8734cd3da2cba8c2c9ff8a9742d46d62585e55604f18630274f6bb8fbc178af`; eight processed tables **29 checks** (`works` 12,000; `references` 289,110); Phase 4 **18 checks/64 outputs**; ML expansion **80 pages/2,515 unique records**; integrated ML **14,515 source rows/14,470 groups/7,002 train/1,843 development/2,318 sealed-test count only**; RQ6 **14 topics/8 CSV/5 PNG**; web package **22 outputs/12,000 indexed papers/14 Topic Briefs**; closed-set model run **14 files** and open-set run **23 files**. Original model bundle manifest and web package SHA-256 were also checked by local restoration. Verified preserved development claims are macro-F1 **0.8808** on **681** in-catalogue 2024 works and outside false acceptance **21.66%** on the separate 2024 open-set evaluation. This did **not** run inference on, open labels from, or modify the 2025 final test; **2025 FINAL TEST: SEALED**. Human review package verification passed two blind packages (40 calibration + 100 evaluation items each); real semantic ratings are still pending.

## Deployment and CI boundaries

`openalex-restore-local-artifact` now copies only manifest-listed files from an approved local source, verifies SHA-256 and byte count before and after, defaults to dry run, and refuses existing destinations. Unit tests cover tampering and traversal. A separate `/tmp` clean local clone was given the authorized 22-file web package and 3-file model bundle; the cloned code loaded 14 topics, 12,000 indexed papers and `TopicPlacementService`. This proves a **local handoff with available authorized artifacts using the existing virtual environment**, not a fully independent install, public artifact distribution or rights clearance. A clean GitHub clone alone still cannot run the full site. The public CI workflow installs dependencies and runs offline tests/CLI contract, but has neither private packages nor Chrome E2E; do not equate CI green with full end-to-end certification. On Draft PR [#3](https://github.com/namkhanh2k5/AI-Research-Trends/pull/3), **both GitHub Actions `test` jobs completed SUCCESS** on 2026-11-02 UTC; this is the remote offline gate, not the local Chrome/artifact gate.

## Remaining risks and acceptance verdict

- **Technical gate:** PASS for the locally tested course demo: no P0 remains, core confirmation and stale-state cases passed in Chrome, Paper Explorer/Methodology/RQ tabs loaded, and model-missing behavior was safe. This does not establish cross-browser compatibility or accessibility conformance.
- **Academic gate:** READY FOR SUPERVISOR REVIEW, **not automatically formal submission**. Report/slide files are substantive and rendered; no verified instructor template/minimum length exists, and a timed human talk-through is pending.
- **Scientific gate:** PASS for preservation of prior results and truthful status only. OpenAlex topic labels remain silver, human semantic validity is unknown, the 2024 open-set false-acceptance target was missed, and the 2025 test remains sealed. No causal OA claim is made.
- **Local release gate:** READY FOR LOCAL COURSE DEMO on an approved machine with verified web/model artifacts. **Public deployment: NOT READY** until artifact rights, approved distribution, security and hosting are resolved.

The next concrete human steps are: supervisor checks the academic format/content against course requirements; two independent reviewers complete genuine blind semantic ratings; the team rehearses the 7–9-minute demo; deployment owners decide whether and how approved artifacts may be distributed. None of those steps authorizes opening the 2025 test without the frozen gate's explicit approval.
