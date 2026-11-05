# Phase 6B expanded-topic protocol

Status: **prospective for Phase 6B model fitting, exploratory relative to Phase 6A**. The Phase 6A five-class model and its 2024 results were already known. This protocol was written before fitting the expanded model or inspecting its 2024 predictions. No 2025 class counts or model outcomes were used.

## Data, unit, and split

- Use the unchanged verified Phase 3 AI/CV sample, one canonical work per row. Labels are OpenAlex-generated **silver** primary topics, never human ground truth.
- Require nonblank title and reconstructed abstract. Normalize Unicode/whitespace but retain scientific terms. Include all source languages with text; audit language separately, without claiming multilingual validity.
- Group versions by canonical DOI and normalized title, independently of labels. Keep the earliest year/Work ID per group. Audit additional near-duplicates using bounded title blocking and abstract similarity; run a sensitivity analysis if cross-year candidates are found. No unrestricted all-pairs search.
- Train: 2020–2023. Development/validation: 2024. Final test: 2025, sealed until the final protocol, model, catalogue and threshold are frozen. The published all-topic audit already contains descriptive 2025 counts; **selection code must ignore them**.

## Catalogues and semantic scope

Catalogue A is the exact five Phase 6A primary topics: `T10036`, `T10664`, `T10028`, `T10052`, `T10462`.

Catalogue B uses **at least 70** eligible 2020–2023 works and **at least 20** eligible 2024 works per class, after text/version filtering. This is a course-project feasibility rule, not a universal standard. A topic must chiefly denote an AI/CV method, model or research task; merely applying AI to an unrelated domain or belonging to OpenAlex subfield 1702/1707 is insufficient. The provisional 14-ID catalogue, to be confirmed against official descriptions before fitting, is:

`T10036`, `T10664`, `T10028`, `T10052`, `T10462`, `T10775`, `T10181`, `T11307`, `T11689`, `T12026`, `T10201`, `T10331`, `T10812`, `T10100`.

The nine additions respectively cover GAN/image synthesis, NLP techniques, domain adaptation/few-shot learning, adversarial robustness, XAI, speech recognition/synthesis, video tracking, human pose/action recognition and metaheuristic optimization. `T10100` needs particular semantic review because metaheuristics can occur outside AI. T10036 and T10028 are broad and may overlap narrower classes. All topic descriptions must be taken from verified OpenAlex metadata, not invented. This is a single-researcher provisional catalogue; independent human approval is pending.

Among the 20 numerically eligible IDs, exclude quantum information/cryptography (`T10020`), quantum-computing architecture (`T10682`) and solar/photovoltaic research (`T11276`) as not primarily AI/CV methods. Leave privacy technologies (`T10764`), AI in cancer detection (`T10862`) and augmented-reality applications (`T10888`) outside the provisional catalogue because their descriptions may span broad application domains. Record each decision, official name/description, support, overlap concern and reviewer status in the scope table. No addition/removal based on model score. Catalogue C (grouped labels) will not be attempted unless B proves unusable; it would require a separate prospective mapping and cannot be compared as the same task.

## Model development and denominators

For each catalogue evaluate majority, verified-description TF-IDF cosine, ComplementNB, Logistic Regression and LinearSVC on the **same 2024 in-catalogue records**. Title+abstract are the only predictive inputs. Fit vectorizers only within 2020–2023 training. Use word unigram/bigram TF-IDF, `min_df=2`, at most 50,000 features, sublinear TF, and a fixed random seed. Modest 3-fold stratified training-only CV chooses model C from `[0.3, 1, 3]` for Logistic/SVM and alpha from `[0.5, 1, 2]` for NB using macro-F1; tie-break to the smaller parameter. Do not tune on 2025. Report accuracy, macro/weighted F1, per-class metrics, confusion matrix, top-3 where scores permit, bootstrap intervals, fit/inference time, and SVM-vs-Logistic paired difference. Metrics for A and B describe **different label universes** and are not directly comparable without their coverage denominators.

## Open-set development

2024 is split by stable hash of version group into a calibration set (~40%) and disjoint evaluation set (~60%), stratified by in/out-catalogue and primary topic where support permits. Use the 2020–2023-trained SVM's **maximum raw decision score** as the primary rejection score; it is not a probability. Choose the largest-acceptance threshold on calibration that has at most 20% out-of-catalogue false acceptance. Freeze it, then report in/out acceptance, AUROC, accepted precision and accuracy, selective risk and end-to-end correct placement on the disjoint 2024 evaluation set. Logistic maximum probability is a secondary diagnostic, not silently substituted if SVM fails. No score can be described as calibrated probability without calibration evidence.

## Final-test rule

Only if Catalogue B meets the separately documented technical gates, freeze topic IDs, preprocessing, duplicate policy, selected model family/parameters, threshold procedure, metrics, data hashes and final command in `docs/PHASE6B_FROZEN_FINAL_EVALUATION_PROTOCOL.md`. Then retrain on permitted 2020–2024 development data and evaluate 2025 **once**. If a gate fails, keep 2025 sealed. Human validation is separate and required for semantic claims regardless of technical results.
