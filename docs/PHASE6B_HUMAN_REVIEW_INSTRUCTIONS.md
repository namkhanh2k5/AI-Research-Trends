# Phase 6B independent topic-label review

Status: **prepared; no ratings collected**. This procedure is for a later, real human study. Do not fill reviewer fields with model or LLM predictions and call them human annotations.

The local run directory `data/analysis/phase6b_topic_validation_20261028_v3/` contains `blind_calibration.csv` (40 examples), `blind_evaluation.csv` (100 examples), and two separate `restricted_key_*.csv` files. These contain paper text/Work IDs and are Git-ignored. Do not publish answer keys, record-level predictions or unredacted reviewer sheets. Give each of **two independent, subject-aware reviewers** the same blind sheet without the keys, model predictions or OpenAlex primary labels. The topic options in each row are randomized; this order is not a ranking.

For every example, the reviewer should choose one `best_topic` from the displayed 14 `T...` IDs, or enter `NONE` when no offered topic describes the paper, or `UNCLEAR` when the text is insufficient or ambiguous. `second_plausible_topic`, `none_of_these`, `unclear_insufficient_information` and `reviewer_note` may be used to record ambiguity. Reviewers should use the supplied official descriptions and assess the *paper's research topic*, not whether a keyword appears. They should not consult the restricted key. Use the calibration sheet to clarify instructions; **do not train or tune the model on human review of the held-out evaluation sheet**.

Combine completed independent ratings in a private CSV with exactly `example_id,rater_id,best_topic` and one row per example/reviewer. The importer accepts short `T...` IDs, canonical OpenAlex topic URLs, `NONE` and `UNCLEAR`. After both reviewers complete every row, run:

```bash
openalex-analyze-topic-annotations \
  --run-dir data/analysis/phase6b_topic_validation_20261028_v3 \
  --sheet evaluation \
  --ratings /path/to/private/two_rater_ratings.csv \
  --output data/analysis/phase6b_topic_validation_20261028_v3/human_evaluation.json
```

The script refuses incomplete/duplicate ratings and overwrites. It reports raw agreement, Cohen's kappa including `NONE/UNCLEAR`, and the number of examples for which **both** reviewers accept the OpenAlex label or model prediction. Inspect disagreements qualitatively with adjudication notes, but retain both original independent ratings. The 100-example sheet is too small for reliable per-topic performance claims; report denominators and uncertainty. A reviewer may disagree with the 14-topic scope itself. Human agreement is not automatically a truth standard, but it is essential before any semantic-validity claim.

The [Phase 6B report](../reports/PHASE6B_FINAL_TOPIC_VALIDATION_REPORT.md) currently reports **no human statistics**. Do not edit it to claim human validation until ratings have actually been collected, imported and independently inspected.
