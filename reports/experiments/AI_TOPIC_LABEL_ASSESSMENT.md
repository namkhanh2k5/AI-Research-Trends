# Blind AI-assisted topic assessment (not human validation)

## Protocol and provenance

The assistant considered the frozen descriptions of 14 OpenAlex topics and the **title and complete abstract** in the existing blind sheets. It did not read the restricted OpenAlex answer keys or model predictions. Every paper received one best topic, `NONE`, or `UNCLEAR`, a qualitative confidence, an evidence rationale, and—where appropriate—a second plausible topic. `NONE` means none of the selected *fourteen* topics is a defensible fit, not that the paper is not AI research. `UNCLEAR` means the available bibliographic text is inadequate. Both statuses are judgments, not ground truth.

The first frozen pass was retained as `ai_assisted_20261104_v1`. Full-abstract re-review identified two needed corrections: one calibration paper whose NLP method was absent from the opening abstract excerpt, and one evaluation paper whose contribution was visual analytics around NLP rather than a selected NLP method. The corrected, still-blind final run is `data/analysis/ai_assisted_validation/ai_assisted_20261104_v2/`. Revision provenance and both frozen run hashes are private. The v2 manifest SHA-256 is `8e3001d0d3e8bd63b5a99b6aa43d24ca5f234d54cc346649028f1f147b64a608`.

Assessment provenance: `OpenAI ChatGPT Codex`; the exact backend model/version and sampling configuration were **not exposed to this environment**, so model-version reproducibility is limited. Prompt protocol version `ai-validation-v2-full-abstract-review`. Input and output SHA-256 values are in the ignored manifests; all 14/40/100 record-level decisions are Git-ignored. No independent human rater is represented by these files.

## Completion and uncertainty

| Measure | 40 calibration | 100 evaluation |
|---|---:|---:|
| Assessed exactly once | 40 | 100 |
| One selected catalogue topic | 20 | 46 |
| `NONE` | 20 | 52 |
| `UNCLEAR` | 0 | 2 |
| HIGH confidence | 15 | 55 |
| MEDIUM confidence | 22 | 32 |
| LOW confidence | 3 | 11 |
| INSUFFICIENT_EVIDENCE | 0 | 2 |
| Plausible secondary topic | 12 | 22 |
| Nonblank ambiguity/overlap note | 18 | 40 |

Qualitative confidence is **not a calibrated probability**. The blind package contains deliberately diverse/out-of-catalogue papers, so the `NONE` share is not topic prevalence in the OpenAlex AI/CV corpus.

### Evaluation-set assigned-topic distribution

| Choice | Count | Choice | Count |
|---|---:|---|---:|
| T10028 | 4 | T10036 | 12 |
| T10052 | 2 | T10100 | 2 |
| T10181 | 1 | T10201 | 0 |
| T10331 | 3 | T10462 | 4 |
| T10664 | 3 | T10775 | 2 |
| T10812 | 3 | T11307 | 2 |
| T11689 | 3 | T12026 | 5 |
| `NONE` | 52 | `UNCLEAR` | 2 |

The fourteen topics were all **assessed for scope**; the absence of T10201 among 100 paper choices does not show that the topic is invalid. Counts are AI decisions on this diagnostic sheet, not OpenAlex-labelled support.

## Qualitative failure taxonomy

1. **Out-of-catalogue subject matter:** quantum physics, classical cryptography, business studies and pedagogical robotics do not become members merely because an AI term appears.
2. **Broad/narrow catalogue collisions:** general NLP (T10028) versus NLP techniques (T10181) and sentiment (T10664); broad CV (T10036) versus medical segmentation (T10052), video surveillance (T10331), and human action (T10812).
3. **Method versus application:** a paper may apply an NLP tool or XAI explainer without contributing to that method cluster. Two full-abstract corrections demonstrate why title/keyword matching is insufficient.
4. **Adjacent technology not explicitly named:** diffusion image synthesis versus GAN-centric T10775; poisoning and jailbreaks versus adversarial-example-focused T11689; generic RL versus robotics-oriented T10462.
5. **Interdisciplinary and multilingual text:** biomedical CV, multimodal methods, Spanish/Chinese/Indonesian abstracts can support multiple readings. The assistant did not infer identity from translated title alone.
6. **Sparse metadata:** two evaluation records had too little scientific text for a defensible choice and were marked `UNCLEAR`.

These are taxonomy and evidence limitations, **not automatically OpenAlex errors**. For genuine human review, prioritize the 22 evaluation cases with secondary topics, 11 LOW-confidence cases, two `UNCLEAR` cases, cross-cutting XAI/RL, and the broad NLP/CV boundaries. Keep these AI decisions private until both reviewers submit their own independent sheets.

**AI decision coverage:** 40/40 calibration and 100/100 evaluation. **Human-validated semantic correctness:** `NOT VERIFIED`. No precision, recall, F1, Cohen's kappa, or human agreement is reported.
