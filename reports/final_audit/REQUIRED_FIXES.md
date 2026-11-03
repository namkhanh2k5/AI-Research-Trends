# Prioritized, evidence-backed defects — no fixes applied

Severity: **P0 BLOCKER** prevents a correct live demo or creates critical integrity/leakage/secret risk; **P1 HIGH** materially weakens scientific submission or a major workflow; **P2 MEDIUM** incomplete UX/visualization/formatting; **P3 LOW** lower-priority assurance/polish. Effort is relative (S≈hours, M≈1–3 days, L≈several days) and is not a deadline commitment.

| ID / severity | File / approximate location | Expected → actual; evidence | Impact / proposed later fix | Effort; blocks |
|---|---|---|---|---|
| AUD-01 **P0** | `dashboard/app.py:132`; `src/ai_research_trends/analysis/web_queries.py:get_topics` | Prediction should lead to manual topic choice; real Chrome after “Suggest topics” shows `KeyError: 'topic_name'` because catalogue uses `official_name`. Screenshot `data/analysis/final_audit_screenshots/05_classify_prediction_desktop.png`. | Core assisted-placement/confirmation demo impossible. Align contract and add full click-through regression with real package. | S; course demo **yes**, public deployment yes. |
| AUD-02 **P1** | `dashboard/app.py:119-139` | Prediction should be tied to current draft; old status remains after title edit (browser observation JSON). Confirmation could misrepresent an older draft once AUD-01 fixed. | Clear suggestion/confirmation on input fingerprint changes and navigation; test edit/confirm sequence. | S–M; credible assisted-use demo **yes**. |
| AUD-03 **P1** | `deliverables/report/FINAL_ACADEMIC_REPORT.md`, §2–§9; PDF 11 pages | Serious report should develop methods/evidence; current eleven chapters plus appendices/references fit 11 pages, with RQ5/RQ6 and testing each short. Rendered pages/heading lengths inspected. | Expand substantive data collection, preprocessing, statistics, ML algorithms/tuning/error/open-set and web/testing sections; regenerate/inspect. Do not invent results. | L; formal course submission **yes**; no verified page minimum. |
| AUD-04 **P1** | `docs/DEPLOYMENT_GUIDE.md`, `docs/MODEL_AND_DATA_ARTIFACTS.md` | Reviewer should restore approved artifacts reproducibly; clean clone lacks ignored web data/model and guide says “rebuild or securely transfer” without tested complete recipe. | Document authorized, checksum-checked artifact generation/distribution and rights review; test clean-clone handoff. | M–L; public/reviewer deployment yes, local demo with artifacts no. |
| AUD-05 **P2** | `dashboard/app.py:175` | Report links should open actual documents; `reports/FINALIZATION_P4_ACADEMIC_REPORT.md` absent, both browser hrefs returned Streamlit HTML shell. | Link to resolvable GitHub/source or approved static/download route; browser-link test. | S; submission evidence access, not source statistics. |
| AUD-06 **P2** | `dashboard/app.py:165-175` | “Model Evaluation” should show actual metrics; only prose/config/warning appears. | Add sourced model-comparison, classwise F1/confusion, ablation and open-set panels with 2024 development labels. | M; examiner-facing completeness. |
| AUD-07 **P2** | `dashboard/app.py:102-116` | Topic Brief should use available context; UI omits `sample_year_counts`, `sample_citation_median`, `sample_oa_counts`, `related_native_topics`, `representative_rule` and representative cited count. | Display selected fields with population/sample distinction and non-quality caution; avoid crowding. | M; feature completeness. |
| AUD-08 **P2** | `dashboard/app.py:58-87` | RQ5/RQ6 should be discoverable; no dedicated explanation/figure despite rich reports. | Add concise, sourced feasibility/label-ambiguity panels or direct functional report links. | M; research communication. |
| AUD-09 **P2** | `dashboard/app.py:155-162` | Search should explain zero results and link DOI; Chrome showed count zero only; DOI is plain metadata text. | Add explicit empty state and validated DOI link where present; test pagination/filter combinations. | S; UX only. |
| AUD-10 **P2** | `deliverables/presentation/FINAL_PRESENTATION.pptx/.pdf`, `DEMO_SCRIPT.md` | Slides/demo should show the real site and complete actions; deck has no site screenshot, scripted confirmation fails. | After fixing AUD-01, capture real screenshots and rehearse timed end-to-end demo. | M; presentation quality/demo reliability. |
| AUD-11 **P2** | `deliverables/generate.py:31-80` | Formal document should have cover/TOC/page numbers/captions; generator has none and PDF visual sampling confirms absence. | Add front matter, page fields, caption/table controls, figure numbering, hyperlink/bibliography styles; inspect every rendered page. | M; formal submission formatting. |
| AUD-12 **P3** | `.github/workflows/ci.yml` | CI should make its scope explicit; currently offline checks pass but local artifact/browser assurance is separate. | Keep private artifacts out of CI; add safe source-contract tests and optional protected local/browser workflow. | M; neither current source integrity nor local demo blocked. |

## Independent review of seven reported concerns

| Concern | Classification | Evidence |
|---|---|---|
| A. Academic report too brief | **CONFIRMED** | 11-page PDF for 11 chapters; chapter review identifies missing depth, no instructor-specific minimum claimed. |
| B. Topic Brief UI underdeveloped | **CONFIRMED** | Five useful JSON fields plus representative citation context unused in `show_brief`. |
| C. Methodology page superficial | **CONFIRMED** | No model comparison, classwise F1, confusion, expansion or open-set result widgets. |
| D. RQ5/RQ6 poorly represented on site | **CONFIRMED** | Source reports substantial; site only generic silver-label/open-set caution, no dedicated RQ5/RQ6 evidence. |
| E. Broken Methodology link | **CONFIRMED** | Missing academic Markdown target; browser hrefs return Streamlit HTML shell rather than report content. |
| F. Missing prior visual QA | **CONFIRMED at start** | Prior Phase4 testing report explicitly said browser/manual audit not done. **This audit now adds real Chrome screenshots**; remaining confirmed-topic state blocked. |
| G. Clean clone cannot run full site | **CONFIRMED** | Web/model artifacts Git-ignored; guide gives conceptual transfer/rebuild, no public artifact source or verified clean-clone restore. Offline install/tests still possible. |

## Patch order for a future authorized implementation

1. Repair AUD-01, AUD-02 and AUD-05 as a small UI contract/navigation patch; run full Chrome click-through on desktop/mobile and update demo evidence.
2. Expand report science (AUD-03), then formal layout (AUD-11), preserving all verified numbers and figures.
3. Add selective RQ/ML panels and Topic Brief context (AUD-06–08) with strict population/sample labels; improve Paper Explorer empty/link state (AUD-09).
4. Rehearse deck/demo and add actual site screenshots (AUD-10).
5. Document/rehearse an authorized artifact restoration path and rights decision (AUD-04), then optionally strengthen CI contract checks (AUD-12).

Do **not** open the 2025 test to resolve any of these UX/report issues. Obtain real human semantic review separately before claims of final topic-label validity. Re-audit after fixes; do not merge stacked PRs as a final release while AUD-01 and AUD-03 remain.
