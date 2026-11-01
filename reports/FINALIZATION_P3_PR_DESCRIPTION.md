## Summary

- Freeze a historical, group-aware 14-topic OpenAlex silver-label development protocol.
- Compare original-only versus targeted-expanded 2020–2023 training; train ComplementNB, Logistic Regression and Linear SVM with train-only CV.
- Evaluate matched 2024 closed-set and disjoint calibration/evaluation open-set cohorts; package an assisted, checksum-verified local SVM inference service linked to existing `ResearchData` Topic Briefs.
- Preserve the 2025 final test **sealed** pending two genuine independent human reviewers and a separate scope decision. No website, new OpenAlex crawl, or automated topic assignment is included.

## Experimental results

Original-sample 2024 closed-set validation: 681 in-catalogue works. Macro-F1: majority 0.0248; official-description matching 0.5522; expanded ComplementNB 0.8580; expanded Logistic Regression 0.8580; expanded Linear SVM **0.8808**. Original-only SVM was 0.8506; paired 500-draw difference interval for expanded minus original is [0.0084, 0.0527].

Original-sample 2024 open-set calibration: 738; disjoint evaluation: 1,105 (408 inside/697 outside). Selected SVM's in-catalogue acceptance 0.8309, outside false acceptance **0.2166**, AUROC 0.8919, end-to-end correct accepted placement 0.2833. The 20% calibration false-acceptance target did **not** hold on the development evaluation set. Human semantic validation: **pending**. 2025 final test: **sealed/not run**.

## Verification

Source integrated manifest and Phase 2 web-data checksums are verified before experiments. Closed/open run validators check local output hashes, source linkage and evaluation universes. The bounded original-vs-expanded evaluation uses the same original-sample 2024 papers. Offline `pytest -o addopts='' -q -ra`: **189 passed, 1 opt-in live test skipped**; `python -m pip check`: **No broken requirements found**. The closed/open verifiers checked 14/23 files, a second closed run reproduced all reported deterministic metric blocks, nine published figure hashes matched, and the six inference contract cases were exercised. Development model binaries and record-level predictions are Git-ignored.

## Artifacts

- [Main report](reports/FINALIZATION_P3_FINAL_ML_REPORT.md)
- [Expansion ablation](reports/FINALIZATION_P3_DATA_EXPANSION_ABLATION.md)
- [Model comparison](reports/FINALIZATION_P3_MODEL_COMPARISON.md)
- [Open-set evaluation](reports/FINALIZATION_P3_OPEN_SET_EVALUATION.md)
- [Inference integration](reports/FINALIZATION_P3_INFERENCE_INTEGRATION.md)
- [Reviewer handoff](reports/FINALIZATION_P3_PHASE4_HANDOFF.md)
- [Published development figures](reports/figures/finalization_p3/manifest.json)

## Risks and limitations

OpenAlex primary topics are generated silver labels; the catalogue covers only 14 topics. Targeted acquisition is not a population sample. Closed-set performance is not human semantic accuracy. The champion exceeds the calibration outside false-acceptance target on 2024 evaluation; all suggestions require user confirmation. No 2025 metrics exist. The GitHub branch does not carry the local model binary or raw text data; deployment requires a trusted artifact-distribution decision.

## Reviewer checklist

- Check protocol, version-group leakage protection, and original-only/expanded matched comparisons.
- Check the open-set threshold calibration/evaluation separation and false-acceptance disclosure.
- Check `TopicPlacementService` checksum validation, explicit confirmation and `ResearchData` source-scope separation.
- Check the 2025 gate rejects without genuine human-review approval; do not open test data as part of this PR.
- Review figures and aggregate reports without attempting to reconstruct unavailable Git-ignored local inputs from GitHub.

**Request:** Review this as a draft. Do not merge until the scientific and security limitations are accepted.
