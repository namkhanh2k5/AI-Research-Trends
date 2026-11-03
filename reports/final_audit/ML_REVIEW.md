# Machine-learning artifact and inference audit

Evidence was read from local `data/analysis/finalization_p3_models_20261101_v1/results.json`, `per_class.csv`, `manifest.json`, `data/analysis/finalization_p3_open_set_20261101_v1/results.json`, integrated split manifest and `models/finalization_p3/topic_placement_v2/`. `openalex-verify-final-ml` passed the 14-file closed-set run and 23-file open-set run; bundle loader verified its manifest before trusted deserialization. The saved `model.joblib` is 5,422,999 bytes, SHA-256 `b066ba80ab0768052f585fa1ed2e6b56c24f46c511508b3394580452e40bb788`, matching the selected expanded Linear SVM artifact. Frozen config, catalogue and inference-code hashes matched the bundle manifest. The loader produced TF-IDF (word 1–2 grams, `min_df=2`, `max_features=50000`, `sublinear_tf=True`) → `LinearSVC(C=1,random_state=20261028)`. Predictors are only cleaned title+abstract; OpenAlex topic IDs/scores, citation, year, Work ID and OA are not passed as predictors. TF-IDF is fit inside train folds, with three-fold `StratifiedGroupKFold` by version group.

Training selected-topic support (sum = 3,355), from verified published `reports/finalization_p2/topic_year_train.csv`:

| Topic | Train | 2024 selected validation | Topic | Train | 2024 selected validation |
|---|---:|---:|---|---:|---:|
| T10028 | 232 | 84 | T10036 | 373 | 143 |
| T10052 | 231 | 45 | T10100 | 232 | 34 |
| T10181 | 216 | 36 | T10201 | 219 | 24 |
| T10331 | 227 | 22 | T10462 | 237 | 45 |
| T10664 | 224 | 58 | T10775 | 224 | 53 |
| T10812 | 219 | 21 | T11307 | 232 | 42 |
| T11689 | 249 | 39 | T12026 | 240 | 35 |

Five classes remain below the 225-row planning heuristic. Validation supports of 21–45 for many classes limit per-class precision. Weakest SVM per-class F1 included T10181 `.7042` (n36), T10028 `.8000` (n84), T10331 `.8182` (n22); the actual `per_class.csv` has all 14 results.

| Method | Training/data | 2024 in-catalogue n | Macro-F1 | Accuracy | Limitation |
|---|---|---:|---:|---:|---|
| Majority | no text learner | 681 | .0248 | .2100 | imbalance baseline |
| Official-description TF-IDF | descriptions, no supervised fit | 681 | .5522 | .5742 | lexical baseline |
| ComplementNB | expanded historical | 681 | .8580 | .8532 | silver labels |
| Logistic Regression | expanded historical | 681 | .8580 | .8649 | silver labels |
| Linear SVM original only | 1,717 selected train | 681 | .8506 | .8546 | different train set |
| Linear SVM expanded | 3,355 selected train | 681 | **.8808** | **.8796** | selected on same 2024 development cohort |

1,638 of the 3,355 selected training papers are targeted expansion. Fixed-hyperparameter C=1 ablation `.8501→.8808` is cleaner than retuned `.8506→.8808`; paired 500-resample macro-F1 difference CI `[.0084,.0527]` compares models on the same 681 papers, not uncertainty in OpenAlex truth or population sampling. Expansion helps this historical training/development setup, not necessarily 2025 or every class. The learning curve is not monotonic; some individual predictions worsened.

Open-set development cohort: 738 calibration (273 in catalogue), 1,105 evaluation (408 in, 697 out), group-separated. Selected raw SVM threshold `−0.22227267687798036`, lower confirmation floor `−0.516798309254057`. Evaluation: 339/408 in accepted (83.09%), 151/697 outside falsely accepted (21.66%), AUROC `.891876`, 313/1,105 correct accepted placement (28.33%). The ≤20% calibration target failed on this evaluation set. Exploratory explicit-OTHER LR had 17.50% outside false acceptance and AUROC `.9473`, but post hoc replacement with it would misuse development results. Model family selection used 2024 closed-set results before the 2024 open-set evaluation; therefore the latter is not a fully independent external estimate even though its threshold calibration/evaluation groups are disjoint. No 2025 final metric exists.

**Real inference probes, synthetic non-test text only:** medical image segmentation → confident T10052, NLP translation → confident T10181, robot RL → confident T10462, explainability → confident T12026, GAN → confident T10775, mixed-domain draft → confident T10052 with competing T10181, quantum physics → needs confirmation T10100, botany → no-confident-match T10036, unusual topological math → no-confident-match T10201, short abstract → validation error, empty title → validation error. All successful responses had `automatic_placement=false`; service top-three/rank/margins were returned. We did **not** independently label any prompt, so semantic correctness is NOT VERIFIED. Manual `ResearchData.get_topic_brief('T10028')` worked without the model. The browser UI confirmation failed separately due a data-contract key mismatch.

The bundle is the evaluated expanded SVM, not a model retrained on 2024 or 2025. Checksum matching is byte integrity, not safe loading of arbitrary untrusted pickle files. Human semantic ratings are absent. 2025 remains SEALED.
