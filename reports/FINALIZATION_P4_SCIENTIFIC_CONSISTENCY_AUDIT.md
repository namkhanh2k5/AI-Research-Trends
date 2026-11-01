# Finalization Phase 4 — scientific consistency audit

| Boundary | Checked presentation and app behavior | Remaining caution |
|---|---|---|
| Defined population vs sample | Home/RQ1 use complete OpenAlex aggregate; RQ2–RQ4 and Paper Explorer label original 12,000-work sample. | The API sample lacks verified inclusion probabilities. |
| Targeted ML expansion | No expanded records in research landscape or paper index; used only for historical training. | Training counts cannot estimate topic prevalence. |
| RQ3 | Academic report states unadjusted binary β=−0.330 and adjusted Gold β=+0.463 CI [+0.396,+0.531], Green β=+0.178 CI [+0.087,+0.269]; all on log1p outcome. | Association is not causal; Green has 2,506/3,559 preprints, all sampled preprints lack FWCI. |
| ML evaluation | 681 in-catalogue 2024 development records, SVM macro-F1 0.8808; open-set outside false acceptance 21.66%. | 2025 SEALED, no final-test metric or human semantic accuracy. |
| Inference | Top-three suggestion, score described as SVM margin, user confirmation required. | Out-of-catalogue drafts may be falsely accepted. |
| Human review | Two blind packages verified, local reviewer UI created. | Zero completed genuine independent ratings; HUMAN SEMANTIC VALIDATION PENDING. |
| Final test | Frozen config still `allow_final_test_execution: false`; registry absent and code now prevents a second local attempt under another output path after authorization. | Local registry cannot prevent runs in another clone or after deliberate deletion; governance required. |

The academic report and presentation do **not** present 2024 development results as 2025 final metrics. Topic and paper counts are drawn from verified local artifacts or previous checksum-verified reports. No original Phase 2–4 scientific data or output files were changed by this task. The 2025 test was not opened. The academic PDF is 11 substantive pages, below the suggested 25–40-page range; it contains all eleven required chapters but should receive supervisor formatting review before formal submission. No instructor template was found in this repository.
