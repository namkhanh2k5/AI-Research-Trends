# AI-assisted scope audit of the frozen 14-topic catalogue

This is a blind, qualitative assessment of the **unchanged** OpenAlex Catalogue B, not a revision to its labels. Source: `config/phase6b_catalogue.yaml` (SHA-256 `e4b34974e2f8a6b563f29ab69ab86675de78ee9fcfbcb1f0258e7fcbd01fdda9`) and its official-topic metadata snapshot (SHA-256 `024f9f13db713534fcc662ff95f477299c8cf939ca200565b2e88e13371ddd86`). The record-level scope decisions are private in `data/analysis/ai_assisted_validation/ai_assisted_20261104_v2/topic/frozen/`.

| Official OpenAlex topic | Parent subfield | AI scope assessment | Boundary and main overlap |
|---|---:|---|---|
| [T10028 — Topic Modeling](https://api.openalex.org/topics/T10028) | 1702 | AMBIGUOUS_SCOPE | Despite its name, the official description spans much of NLP; overlaps T10181 and sentiment T10664. |
| [T10036 — Advanced Neural Network Applications](https://api.openalex.org/topics/T10036) | 1707 | OVERLAPPING | Broad CV recognition/detection/segmentation; overlaps T10052, T10331, T10775 and T10812. |
| [T10052 — Medical Image Segmentation Techniques](https://api.openalex.org/topics/T10052) | 1707 | MOSTLY_CLEAR | Medical image *segmentation*, not every medical image classifier; overlaps broad CV T10036. |
| [T10100 — Metaheuristic Optimization Algorithms Research](https://api.openalex.org/topics/T10100) | 1702 | NEEDS_EXPERT_REVIEW | Nature-inspired optimization is cross-domain; an AI/CV scope expert should decide whether all its applications belong. |
| [T10181 — Natural Language Processing Techniques](https://api.openalex.org/topics/T10181) | 1702 | OVERLAPPING | Translation, parsing and language models; overlaps broad NLP T10028 and sentiment T10664. |
| [T10201 — Speech Recognition and Synthesis](https://api.openalex.org/topics/T10201) | 1702 | CLEARLY_DEFINED | Speech recognition/synthesis is coherent, with some language-model overlap. |
| [T10331 — Video Surveillance and Tracking Methods](https://api.openalex.org/topics/T10331) | 1707 | OVERLAPPING | Tracking and re-identification; overlaps action recognition T10812 and broad CV T10036. |
| [T10462 — Reinforcement Learning in Robotics](https://api.openalex.org/topics/T10462) | 1702 | OVERLAPPING | Name implies robotics, while official description includes general RL algorithms; general policy-learning cases are borderline. |
| [T10664 — Sentiment Analysis and Opinion Mining](https://api.openalex.org/topics/T10664) | 1702 | MOSTLY_CLEAR | Opinion/emotion text mining; overlaps general NLP text classification. |
| [T10775 — Generative Adversarial Networks and Image Synthesis](https://api.openalex.org/topics/T10775) | 1707 | OVERLAPPING | GAN-centric name; diffusion-based image generation is adjacent but not explicitly guaranteed in scope. |
| [T10812 — Human Pose and Action Recognition](https://api.openalex.org/topics/T10812) | 1707 | MOSTLY_CLEAR | Human pose/action from images or video; overlaps surveillance T10331. |
| [T11307 — Domain Adaptation and Few-Shot Learning](https://api.openalex.org/topics/T11307) | 1702 | OVERLAPPING | Cross-domain method applied across visual and language tasks; overlaps T10036 applications. |
| [T11689 — Adversarial Robustness in Machine Learning](https://api.openalex.org/topics/T11689) | 1702 | MOSTLY_CLEAR | Adversarial attacks/defenses; poisoning and LLM jailbreaks are adjacent but not identical. |
| [T12026 — Explainable Artificial Intelligence (XAI)](https://api.openalex.org/topics/T12026) | 1702 | MOSTLY_CLEAR | Interpretability/attribution can accompany any application-specific topic. |

Counts: one CLEARLY_DEFINED, five MOSTLY_CLEAR, six OVERLAPPING, one AMBIGUOUS_SCOPE, one NEEDS_EXPERT_REVIEW. This is an AI semantic assessment of definitions, **not** independent domain-expert consensus. OpenAlex topic descriptions and machine-generated memberships are not a human gold standard. The named topic may be narrower or broader than its current official description. The frozen catalogue remains intact; two genuine independent scope reviewers are still required.
