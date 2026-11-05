# Sealed 2025 final-test status

**SEALED — never evaluated in Phase 3.** The integrated data manifest lists a 2025 test split of 2,318 records, but this Phase 3 workflow did not load its rows, train on it, inspect its topic labels, tune a threshold against it, or generate predictions. There are therefore **no 2025 accuracy, macro-F1, open-set, or human-semantic results to report**.

The frozen configuration `config/finalization_p3_frozen_evaluation.yaml` has `allow_final_test_execution: false` and `human_review: pending_two_independent_real_raters`. `openalex-final-test` checks that flag, the scope-approval record, two distinct human sign-offs, completed real-rater files, and frozen model/protocol hashes **before** reading the sealed test. It writes an immutable new output directory for a valid one-time run and refuses to overwrite it. Offline regression tests assert that a disabled gate rejects a nonexistent test path without creating output.

Opening the test later requires an independent human scope-review decision and a separately reviewed change of the gate flag; editing the YAML alone is not evidence of genuine review. The 2024 development metrics in these reports must never be called final-test metrics.
