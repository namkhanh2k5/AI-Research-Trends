# Phase 6B reviewer-safe aggregate evidence

These are byte-identical copies of selected small **aggregate** CSV outputs from the local completed `phase6b_topic_validation_20261028_v3` run. The local run manifest SHA-256 is `8adeee71c0b37d3e5b85d06360d2d471b72618daf1a4427b023570664bac9c79`; all 34 local outputs passed read-only hash checks. `summary.json` is a filtered, aggregate-only rendering of that verified manifest. No paper text, Work-ID-level predictions, answer keys, model binary, or sample data are published here.

| File(s) | Meaning |
|---|---|
| `scope_review.csv` | 20 candidate topics, verified names/descriptions, pre-2025 support and provisional scope decisions |
| `catalogue_a_linear_svm_per_class.csv`, `catalogue_a_linear_svm_confusion.csv` | Five-topic 2024 SVM classwise results |
| `catalogue_a_svm_ablation.csv`, `catalogue_a_svm_top_terms.csv` | Five-topic text-field and lexical-shortcut audits |
| `catalogue_b_linear_svm_per_class.csv`, `catalogue_b_linear_svm_confusion.csv` | Fourteen-topic 2024 SVM classwise results |
| `catalogue_b_coverage_*.csv` | Detailed-sample catalogue coverage by year, primary subfield, work type and language |
| `summary.json` | Model comparisons, uncertainty, open-set calibration/evaluation and provenance hashes |

Coverage and citation/metadata context here refer to a **sample**, not full-population prevalence. OpenAlex primary-topic labels are automated silver labels; human semantic review is pending. The [main report](../PHASE6B_FINAL_TOPIC_VALIDATION_REPORT.md) interprets the evidence and explains why the 2025 final test was not run.
