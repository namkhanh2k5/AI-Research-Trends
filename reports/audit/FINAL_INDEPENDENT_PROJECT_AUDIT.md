# Independent project audit — 2026-11-01

**Scope:** local evidence at `3a75abc76129d3063c5c79ab38dd6e085057d26a`, branch `feature/finalization-p4-complete-delivery`. This is an audit, not a new scientific result or a repair. No source, collected data, model, Git history, human response or 2025 sealed label was changed or opened. Supporting evidence is linked below. The disposable browser screenshots cited in this historical audit were removed in a later repository cleanup; their paths below are historical references, not current files.

## Executive decision

The original collection, eight analytical tables, targeted expansion, integrated splits, Phase 4 statistics, verified model bundle and local web-data package pass their available integrity verifiers. The research is substantial and generally careful about population versus sample, observational inference and silver labels. **The completed product is not yet ready for an unqualified course submission or its scripted live demo.** A real Chrome run of “Suggest topics” raises `KeyError: 'topic_name'` before the user can confirm a suggestion. The Methodology page's report links do not deliver the documents. The 11-page academic PDF is a condensed draft, not a developed thesis-style report. Human semantic validation is pending and the 2025 final test remains sealed.

No P0 data-corruption, leakage or secret-exposure defect was observed. One P0 **core-demo blocker** was reproduced. This distinction matters: the verified scientific artifacts remain usable; the UI promise is currently broken.

## Repository and evidence boundary

`git status --short` was empty before audit; `git diff --check` was clean; `git rev-parse HEAD` matched the expected SHA. `origin` is `https://github.com/namkhanh2k5/AI-Research-Trends.git`. Four finalization branches form a linear ancestry: Phase 1 `708f804` → Phase 2 `c726efe` → Phase 3 `053bbc8` → Phase 4 `3a75abc`. PR [#1](https://github.com/namkhanh2k5/AI-Research-Trends/pull/1) is OPEN/DRAFT, Phase 3 against Phase 2; PR [#2](https://github.com/namkhanh2k5/AI-Research-Trends/pull/2) is OPEN/DRAFT, Phase 4 against Phase 3, with two successful **offline** checks. No merge or retarget was performed. Only audit reports are new untracked files; ignored screenshot evidence does not affect Git status.

The 305 tracked paths contain source, tests, documentation, published figures and final DOCX/PDF/PPTX. No `.env`, raw JSONL/Parquet or `.joblib` was tracked in the examined index; the largest tracked file observed was the intended 600,300-byte academic PDF, not a research dataset or model. A clean clone can install the Python package and run offline tests, but **cannot run the full research site** without privately regenerated/transferred, checksum-verified web data and model bundle. There is no hosted URL and no complete one-command artifact restoration from a public clone. See [deployment audit](../final_audit/DEPLOYMENT_AND_CI_REVIEW.md).

## Data pipeline result

| Dataset | Source | Raw/source count | Final usable count | Purpose | Integrity |
|---|---|---:|---:|---|---|
| Defined non-retracted AI/CV corpus | OpenAlex aggregate snapshot, `data/metadata/population_counts_pre_phase2.json` | 937,493 | 937,493 aggregate count | RQ1 denominator | Population artifact/plan filters and provenance checked; not individual Works |
| All-work sensitivity | Same aggregate artifact, retracted included | 942,825 | 942,825 aggregate count | Retraction sensitivity | Separate series retained |
| Original collection | `data/raw/openalex_stratified/stratified_20261019T155909Z/` | 12,000; 123 pages | 12,000 canonical IDs | Detailed original sample | Read-only verifier PASS; raw/interim SHA identical |
| Original preprocessing | `data/processed/openalex_stratified/stratified_20261019T155909Z/` | 12,000 Works | 12,000 work rows; 8 tables | RQ1–RQ5, website paper index | 29 validation checks PASS; eight file hashes checked |
| Targeted 2020–2023 expansion | `data/raw/openalex_ml_expansion/ml_expansion_20261101T052506Z/` | 2,515; 80 pages | 1,947 provisionally text-usable | ML training only | Expansion verifier PASS; provisional count is not the final integrated total |
| Integrated ML source | original + expansion | 14,515 rows | 14,470 transitive version groups | Identity/split audit | Eight output hashes match deterministic rerun |
| Integrated train | `data/processed/ml_topic_classification/finalization_p2_20261101_v3/` | original + expansion | 7,002 (5,055 original + 1,947 expansion) | Historical ML fitting | Verifier PASS; 3,355 in 14-topic catalogue |
| Development 2024 | original only | original 2024 stratum | 1,843 text-eligible; 681 in catalogue | Model development | Version groups isolated; no expansion |
| Sealed 2025 | original only | original 2025 stratum | 2,318 text-eligible | Reserved final test | **SEALED:** only manifest/hash/count mechanics checked; labels/predictions NOT INSPECTED |

The original population query is bounded to `2020-01-01`–`2025-12-31`, `article|review|preprint`, primary subfield `1702|1707`, and `is_retracted:false`. Annual original sample counts are 1,607 / 1,650 / 1,615 / 1,865 / 2,287 / 2,976. Phase 3 table rows: works 12,000; work_topics 36,000; authorships 46,249; work_institutions 18,717; work_countries 11,786; references 289,110; category_membership 4,790; population_year_counts 72. `works` has 49 columns. Missing original fields: title 2, DOI 1,019, abstract 2,558, FWCI 2,678, affiliation institution 2,902, country 2,949, language 586. No later phase altered the validated original checksums. Full schemas, file sizes, split rules and commands: [data integrity audit](../final_audit/DATA_INTEGRITY.md).

**Three analytical scopes remain distinct:** (A) complete OpenAlex aggregates for the defined population, (B) original 12,000-work detailed sample for bibliometrics and web search, (C) targeted 2,515-record 2020–2023 expansion for ML training only. The expansion is not used as population prevalence. Nominal sample weights are not certified inverse inclusion probabilities.

## RQ1–RQ6 consistency matrix

| RQ | Verified source and headline result | Statistical validity | Website / report / slides | Gap; severity |
|---|---|---|---|---|
| RQ1 publication | Full non-retracted population: 125,506 in 2020, 232,476 in 2025; 2025 YoY +30.10%; native-topic series overlap | Snapshot and taxonomy changes limit historical interpretation | Site trend present; report table/figure present; slide 3 present | Site does not show full native-topic comparative analysis; P2 |
| RQ2 impact | Original sample n=12,000, citation median 2, mean 11.24, P90 23, zero 37.75%; FWCI 9,322 observed | Age-citation ρ=.297; all 2,678 preprints lack FWCI; not paper quality | Site yearly median and summary; report figure; slide 4 | Site lacks detailed FWCI and subfield comparisons; P2 |
| RQ3 OA | Unadjusted binary β=−.330; adjusted six-status Gold β=.463 HC3 CI [.396,.531], Green β=.178 [.087,.269] | Conditional log1p associations, not causality; Green 2,506/3,559 preprints | Site OA descriptive only; report detailed; slide 5 correct | Adjusted model absent from website; P2 |
| RQ4 collaboration | 1,979 international among 7,970 known; 4,030 unknown; 126-country/1,031-edge sampled network | Affiliations are incomplete; co-affiliation is not direct collaboration/nationality | Site tables; report network; slide 6 | No actual network graphic on site; P2 |
| RQ5 reference network | 289,110 edges, 207,102 referenced IDs; historical ≥2 pool original median ID-overlap 10.0%, expanded all-edge pool 12.1%; bounded retrieval Recall@20 2.53% | Different historical citer eligibility explains 10.0 versus 12.1; neither is global retrieval performance | Report short paragraph; slide 7; site absent | RQ5 decision/method not accessible on website; P2 |
| RQ6 label reliability | 14 silver-label classes; train 3,355; validation 681; top-three overlap T10036/T11307 376; missing abstract varies by topic | Topic scores not quality/probabilities; no independent human semantic ratings | Report short paragraph; slide 8; site only generic caveat | Class support, overlap, ambiguity and human gate absent from site; P2/P1 for scientific claims if not qualified |

Detailed source crosswalk and interpretation: [scientific review](../final_audit/SCIENTIFIC_REVIEW.md). Neither website nor slides should be mistaken for the complete Phase 4/RQ6 statistical report.

## ML audit and real inference

The actual model artifacts and results were read and verified, not merely the Markdown summaries. On **the same 681 original-sample 2024 in-catalogue works**, macro-F1/accuracy were majority `.0248/.2100`, description matching `.5522/.5742`, expanded ComplementNB `.8580/.8532`, expanded LR `.8580/.8649`, expanded Linear SVM `.8808/.8796`; original-only SVM macro-F1 `.8506`. Fixed-C=1 SVM comparison is `.8501` → `.8808`; paired 500-resample difference CI `[.0084,.0527]`. This supports improvement against the same silver-label development set, not semantic truth, population prevalence or future generalization. See [ML review](../final_audit/ML_REVIEW.md) for all 14 class supports and artifact provenance.

Training uses only title + abstract, TF-IDF word 1–2 grams, `min_df=2`, `max_features=50000`, `sublinear_tf=True`; fit inside 3-fold `StratifiedGroupKFold` on train version groups. Selected `LinearSVC(C=1)` and threshold `−0.2222726769` match the locally verified bundle. The 2024 open-set evaluation is **development**: calibration 738, evaluation 1,105 (408 in/697 out); in acceptance 83.09%, outside false acceptance 21.66%, AUROC .8919, end-to-end correct placement 28.33%. Explicit-OTHER LR was exploratory (outside false acceptance 17.50%). Although threshold calibration is group-disjoint, 2024 model-family selection limits the independence of the 2024 open-set evaluation. The 2025 test was not run.

Eleven synthetic, non-test inputs were submitted to the **real local inference service**: clear domain drafts often returned `confident_suggestion`, quantum draft `needs_user_confirmation`, botanical/unusual math drafts `no_confident_match`; short/empty input was rejected. All returned `automatic_placement=false`. These probes verify statuses and mechanics, **not semantic correctness**. The deployed bundle hash matches the selected expanded Linear SVM model; the UI defect below prevents completing the promised user confirmation in Chrome.

## Website, visual and demo audit

The real Streamlit app started on `127.0.0.1:8501`. A real headless Google Chrome Playwright walkthrough at 1440×900, 1280×800, 768×1024 and 390×844 captured 11 UI screenshots. This was **browser rendering**, not just AppTest, but not human usability testing or manual assistive-technology evaluation. No document-level horizontal overflow was observed at those widths. RQ tabs, Topic Explorer and Paper Explorer rendered; service-level filter probes returned 1,607 year-2020, 1,040 T10028, 57 reviews and 1,890 gold-OA records. No-results showed `0 matching sampled works` but no explicit message. The actual prediction page raised `KeyError: 'topic_name'` at `dashboard/app.py:132` because `ResearchData.get_topics()` provides `official_name`; therefore the “confirmed” screenshot could not be taken, and the demo script's confirmation step fails. Changing input after a prediction left a stale suggestion visible. The Methodology links resolved to Streamlit HTML routes, not the report documents; the named academic Markdown target does not exist. See [web functional](../final_audit/WEB_FUNCTIONAL_REVIEW.md) and [visual audit](../final_audit/UI_RESPONSIVE_REVIEW.md).

The Topic Brief JSON contains `sample_year_counts`, `sample_citation_median`, `sample_oa_counts`, `related_native_topics` and `representative_rule`, none of which are surfaced in `show_brief`. Methodology displays no model comparison, confusion matrix, classwise F1, expansion ablation or open-set metrics. RQ5/RQ6 have no dedicated UI. The site uses only the original 12,000-paper index. The current local-only demo **is not reliable until the P0 UI defect is repaired and retested**.

## Academic, presentation and governance assessment

`deliverables/report/FINAL_ACADEMIC_REPORT.md/.docx/.pdf` exist; DOCX archive passed structural ZIP check; rendered PDF is **11 Letter pages**, with 11 main chapters plus appendices/references. Pages 1, 7 and 11 were visually inspected, alongside extracted full text. It has no separate title page, contents page or visible page numbers. The report is broadly numerically consistent and cautious about causal and silver-label claims, but methods, derivations, RQ5/RQ6, error analysis, web architecture and testing are compressed into short paragraphs. It needs substantive expansion before formal submission; no instructor-specific page minimum was supplied. The six external references were checked against official OpenAlex/scikit-learn pages and the source/publisher for Salton–Buckley; internal project reports are listed separately but with abbreviated bibliographic treatment. See [chapter review](../final_audit/ACADEMIC_REPORT_REVIEW.md).

`deliverables/presentation/FINAL_PRESENTATION.pptx/.pdf` exist and their ZIP/PDF structure was checked. The PDF has **12 slides**. Slides 1, 5 and 9 were visually inspected and the entire slide text extracted. RQ1–RQ6, model comparison and limitations are represented; numerical statements checked against source results. No actual website screenshot and no dedicated preprocessing diagram appear. The `DEMO_SCRIPT.md` proposes 5–7 minutes; the classification-confirmation action is currently impossible. See [presentation review](../final_audit/PRESENTATION_REVIEW.md).

Reviewer A/B blind packages (40 calibration, 100 evaluation each) passed package verification; no returned ratings were found or claimed, no answer keys were read. Frozen protocol has `allow_final_test_execution: false`, human review pending; project-level final-test registry absent. **2025 FINAL TEST: SEALED.** Only allowed count/hash/status mechanics were verified. CI checks installation, syntax, offline tests and tracking policy; it does not load local model/data, run a browser, verify deliverable content or certify rights. Local tests: Python 3.12.3; `.venv/bin/python -m pytest -q -ra -o addopts=''` → **205 passed, 1 skipped** (opt-in live OpenAlex); `.venv/bin/python -m pip check` → no broken requirements. No OpenAlex request or retraining was performed.

## Defects and priority

| ID | Severity | Source/evidence | Impact and required action | Submission/deployment |
|---|---|---|---|---|
| AUD-01 | **P0 BLOCKER** | `dashboard/app.py:132`, Chrome screenshot `05_classify_prediction_desktop.png` | `topic_name`/`official_name` contract mismatch crashes the confirmation flow; repair key and add browser/AppTest click-through; small effort | Blocks scripted course demo |
| AUD-02 | **P1 HIGH** | `dashboard/app.py:127-137`, browser observation | Suggestion/confirmation can persist after draft changes; bind state to input fingerprint and reset on edit; small–medium | Blocks trustworthy assisted-use demo after AUD-01 |
| AUD-03 | **P1 HIGH** | `deliverables/report/FINAL_ACADEMIC_REPORT.pdf`, 11 pages | Condensed report lacks depth/formatting expected of a serious undergraduate report; expand chapters and regenerate/inspect; large | Blocks formal submission quality; instructor rule unknown |
| AUD-04 | **P1 HIGH** | `docs/DEPLOYMENT_GUIDE.md`, ignored model/web package | Clean clone cannot run complete site; document reproducible authorized artifact restoration and rights; medium–large | Blocks public/reviewer deployment, not local data science |
| AUD-05 | **P2 MEDIUM** | `dashboard/app.py:175`, browser links | Both report links route to Streamlit shell; first target absent; link to real repository documents or serve approved files; small | Demo polish and evidence access |
| AUD-06 | **P2 MEDIUM** | `dashboard/app.py:165-175` | Methodology page lacks actual evaluation figures/metrics; add sourced development panels; medium | Weakens examiner-facing website |
| AUD-07 | **P2 MEDIUM** | `dashboard/app.py:102-116`, Topic Brief JSON | Five useful context fields not displayed; add scoped descriptive context; medium | Feature completeness |
| AUD-08 | **P2 MEDIUM** | `dashboard/app.py:58-87`, source RQ5/RQ6 reports | RQ5/RQ6 poorly represented; add bounded explanation/link to verified evidence; medium | Research communication |
| AUD-09 | **P2 MEDIUM** | `dashboard/app.py:155-162` | No explicit zero-results state or DOI hyperlink; add accessible message/link; small | UX |
| AUD-10 | **P2 MEDIUM** | `deliverables/presentation/FINAL_PRESENTATION.pdf`, demo script | No actual site screenshot; live demo script blocked by AUD-01; add verified screenshots after fix, rehearse; medium | Presentation reliability |
| AUD-11 | **P2 MEDIUM** | `deliverables/generate.py`, rendered academic PDF | Missing title/TOC/page numbers and thin captions/references; improve template after content expansion; medium | Formal formatting |
| AUD-12 | **P3 LOW** | CI workflow | No artifact/browser visual tests in CI (private artifacts intentionally absent); add safe contract tests and optional protected local checks; medium | Assurance, not current integrity failure |

All defects have fuller expected/actual/evidence/effort in [required fixes](../final_audit/REQUIRED_FIXES.md). No flaw was silently repaired.

## Separate readiness verdicts

| Area | Verdict | Reason |
|---|---|---|
| Data Science Research | **READY WITH LIMITATIONS** | Verified artifacts and careful scope; nonprobability sampling, source missingness and no human label validation remain. |
| ML Component | **REVISE** | Saved model matches development evaluation, but 21.66% out-of-catalogue false acceptance and no human/2025 evaluation; UI confirmation broken. |
| Website Functionality | **NEEDS FIXES** | Local site runs and browsing works; core classification confirmation crashes. |
| Academic Report | **NEEDS EXPANSION** | Eleven-page condensed draft with insufficient methodological depth and formal layout. |
| Presentation | **NEEDS POLISH** | Twelve readable slides, but no real UI screenshot and scripted confirmation fails. |
| Public Deployment | **BLOCKED** | Private artifacts/rights review and reliable release path absent; no public URL. |
| Overall Course Submission | **NOT READY** | Fix core demo and strengthen formal report before supervisor/examiner submission. |

**Merge recommendation:** do not merge the stacked PRs as a final-submission release yet. Preserve the verified science; make a narrow P0/P1 patch, rerun local browser and artifact tests, then re-review. Human annotation and the 2025 test are separate governed gates, not tasks to bypass for a demo.

## Reproduction and evidence

Read-only commands run: `git status --short`, `git branch --show-current`, `git rev-parse HEAD`, `git log --oneline -12`, `git remote -v`, `git diff --check`, `git ls-files`, `gh pr view 1/2 --json ...`; `.venv/bin/openalex-verify-collection .../manifest.json`; `.venv/bin/openalex-validate-processed --output-dir ... --plan ... --population ...`; `.venv/bin/openalex-verify-ml-expansion .../manifest.json`; `.venv/bin/openalex-verify-integrated-topics ... --compare-dir ...`; `.venv/bin/openalex-validate-phase4 ... --compare-dir ...`; `.venv/bin/openalex-verify-rq6 ... --published-dir reports/finalization_p2`; `.venv/bin/openalex-build-web-data verify ...`; `.venv/bin/openalex-verify-final-ml` on both Phase 3 run directories; `.venv/bin/openalex-prepare-human-review verify ...`; `pytest`, `pip check`, `pdfinfo`, `pdftotext`, `pdfimages`, `unzip -t`; real Chrome Playwright walkthrough via ignored `data/analysis/final_audit_screenshots/browser_probe.py`. Exact paths/outputs are in supporting files. HTTP health and browser rendering are not a public deployment test. Newly created audit reports are **untracked**; no product source was modified.
