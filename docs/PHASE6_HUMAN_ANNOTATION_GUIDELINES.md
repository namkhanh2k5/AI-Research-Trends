# Phase 6A blind topic-label calibration protocol

Status: **prepared; no human ratings collected**. The local, Git-ignored run directory contains `blind_annotation_template.csv` and a separate `restricted_answer_key.csv`. The former contains 36 reproducibly sampled 2024 validation-period papers (fixed seed 20261028), anonymous IDs, titles, abstracts, the five provisional topic choices and their verified OpenAlex descriptions. It does **not** contain OpenAlex primary labels or model predictions. The answer key must not be shown to raters before they finish. Both files contain research-paper text or label-sensitive records and are not committed.

## Instructions for two independent reviewers

Read the title and abstract only. Choose one best catalogue topic if the paper's central research contribution fits it; alternatively select `None of these` or `Unclear / insufficient information`. Record a brief reason and, if useful, a second plausible topic. Do not infer the correct answer from a DOI, source, year, citation count or external OpenAlex search. The catalogue is limited and deliberately does not represent all AI/CV. The descriptions are OpenAlex-generated scope aids, not authoritative truth. Keep the sheet blinded until both independent passes are complete.

After independent annotation, adjudicate disagreements with a third reviewer or documented discussion. Only then join to `restricted_answer_key.csv` by anonymous example ID. Report raw agreement, classwise disagreement, the proportion of `None`/`Unclear`, and optionally Cohen's kappa with an explicit treatment of those categories. Do not pool adjudicated ratings with independent ratings when computing inter-rater agreement. Inspect whether OpenAlex scores or model errors correlate with human disagreement only after unblinding.

The calibration sample is small and conditional on 2024 in-catalogue papers; it cannot establish global label precision or open-set validity. A later independent evaluation set must include out-of-catalogue papers before any broad user-facing claim. **Human label validation pending.**
