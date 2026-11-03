# Model bundle and Topic Brief integration

`TopicPlacementService` loads `models/finalization_p3/topic_placement_v2/`, a local immutable bundle produced from the checksum-verified closed/open development runs. Its manifest records source integrated/web/catalogue hashes, model and configuration SHA-256 values, inference-code SHA-256, model version, and that human validation is pending and 2025 is sealed. The model binary is Git-ignored; it is **not** a deployable artifact on GitHub. Only load bundles created by this project from trusted local files: checksum checks do not make arbitrary pickle/joblib inputs safe.

The service requires a nonblank title and an abstract of at least 50 characters/8 words. It cleans each input with the training text rule, ranks the 14 catalogue topics using the selected Linear SVM's maximum decision margins, and returns top-k topic ID/name/rank/score. The margin is **not a probability**. The frozen threshold distinguishes `confident_suggestion` from `needs_user_confirmation` and `no_confident_match`; **every** state has `requires_user_confirmation=true`, and `automatic_placement=false`. The observed 2024 outside false-acceptance of 0.2166 makes this conservative product policy necessary.

`explore_research_draft` can preview a model-suggested Topic Brief or use an explicitly selected catalogue topic. It attaches Phase 2 `ResearchData` publication trends (full approved population), citation/OA context and briefs (original 12,000-work detailed sample). Targeted training expansion never enters these research-landscape statistics. The service does not call OpenAlex and does not mutate verified analytical outputs. Missing or invalid topic briefs must surface as unavailable/error rather than an invented summary.

The local end-to-end smoke used actual 2024 development records: an in-catalogue record returned `confident_suggestion` with a brief; an outside-catalogue record returned `no_confident_match` without a brief; 582 records fell between the frozen floor and threshold, and one returned `needs_user_confirmation`. Manual topic selection returned `selection_source=manual`; a too-short abstract raised `ValueError`; an unavailable topic brief raised `KeyError`. These are behavior checks, **not** independent human correctness ratings.

Rebuild locally after verifying source data:

```bash
openalex-package-topic-model package \
  --closed-run data/analysis/finalization_p3_models_20261101_v1 \
  --open-run data/analysis/finalization_p3_open_set_20261101_v1 \
  --output-dir models/finalization_p3/topic_placement_rebuild_v1
```

CLI smoke input must be real user-provided draft text; do not place private drafts in shell history or Git. Application code should call `TopicPlacementService(...).explore_research_draft(...)` directly, display `warnings` and model version, and require a visible manual confirmation before using a selected topic. The Phase 4 website itself is not implemented here.
