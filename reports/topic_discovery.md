# Topic Discovery and Emerging-Technology Audit

**Discovery evidence:** 2026-10-19 UTC

**Direct topic revalidation:** 2026-10-19T03:06:48Z

**Endpoint:** `https://api.openalex.org/topics`

## Classification decision

The project now uses two non-equivalent layers:

1. **OpenAlex-native topic lenses** match verified IDs in each work's overlapping
   `topics` array. They retain OpenAlex names and are model-inferred.
2. **Custom emerging technologies** match versioned title/abstract rules. They are
   project measurements, not OpenAlex taxonomy nodes.

Counts from the layers are never merged into one ranking without a clear method
column and qualification. A difference between them may be a classification
effect rather than a scientific trend.

## Verified native selections

Direct singleton lookups validated all six configured IDs, display names,
descriptions, and Domain/Field/Subfield hierarchy values.

| Native lens | Verified topics | Decision and limitation |
|---|---|---|
| NLP | T10181 Natural Language Processing Techniques; T10028 Topic Modeling | Broad composite; T10028 is heterogeneous; not an LLM label |
| Computer Vision | T10036 Advanced Neural Network Applications | Deep-learning vision subset, narrower than subfield 1707 |
| Reinforcement Learning | T10462 Reinforcement Learning in Robotics | Robotics-oriented; not exhaustive of RL |
| Explainable AI | T12026 Explainable Artificial Intelligence (XAI) | Close match; assignment remains inferred |
| Multimodal ML Applications | T11714 Multimodal Machine Learning Applications | Mainly vision-language; not equivalent to custom Multimodal AI |

Search results were candidate evidence only. For example, “computer vision” also
returned an ergonomics topic through “computer vision syndrome,” demonstrating
why search rank is not membership proof.

## Custom rule proposals

Exact regular expressions and case settings are versioned in
`config/topics.yaml`. The operational proposals are:

- **LLM:** explicit “large language model(s),” case-sensitive `LLM`/`LLMs`,
  “foundation language model(s),” or named `ChatGPT`/GPT-3/GPT-4 variants.
  This is conservative and misses unnamed/new families; a mention may still be
  contextual rather than central.
- **Multimodal AI:** explicit multimodal AI/ML/model/learning/fusion/
  representation phrases, vision-language model(s), case-sensitive `VLM`/`VLMs`,
  or audio-visual learning/model/recognition/representation/fusion. This covers
  more than T11714 but may include incidental cross-modal discussion or an
  ambiguous acronym.
- **RAG:** explicit “retrieval-augmented generation” allowing space/common dash
  variants, or case-sensitive `RAG` only when retrieval/generation/LLM context is
  also present. There is **no dedicated selected OpenAlex RAG topic**. T10028
  mentions RAG in its keywords but is too broad to use as a RAG proxy.

## Reproducible pilot audit

Source: 1,000 unique works from `pilot_20261019T024131Z`. The audit sorted each
custom category's matches by canonical ID and used
`random.Random(20251019).sample(..., min(10, n))`. One reviewer labeled central or
substantive use as `relevant`, a meaningful but non-central mention as
`ambiguous`, and an incidental mention as `false positive`.

| Category | Pilot matches | Reviewed | Relevant | Ambiguous | False positive |
|---|---:|---:|---:|---:|---:|
| Large Language Models | 53 | 10 | 9 | 1 | 0 |
| Multimodal AI | 15 | 10 | 9 | 1 | 0 |
| Retrieval-Augmented Generation | 4 | 4 | 2 | 1 | 1 |

### Ambiguous and false-positive cases

| Work ID | Rule category | Judgment | Reason |
|---|---|---|---|
| W4414855245, *Spa-VLM: Stealthy Poisoning Attacks on RAG-based VLM* | LLM | Ambiguous | LLMs are comparison/context; the substantive target is a RAG-enabled vision-language model |
| W4408072316, *Beyond Words: The Evolution of Large Language Models...* | Multimodal AI | Ambiguous | Multimodal learning is one subordinate theme in a broad LLM review |
| W7117899060, *Unifying Knowledge in Agentic LLMs* | RAG | Ambiguous | RAG is one of several external-knowledge paradigms in a broader survey |
| W4415008298, *LLM-Enhanced Semantic Text Segmentation* | RAG | False positive | RAG appears only as a possible application of the segmentation findings; no RAG method is studied |

The other reviewed matches described direct model evaluation/application,
multimodal learning/VLM methods, or RAG systems/attacks and were labeled relevant.
This is a small diagnostic audit, not a precision estimate: there is one reviewer,
no confidence interval, and no negative sample with which to assess recall.

## Consequences for Phase 2

Keep a broad text-derived flag for discovery and add a stricter central-relevance
sensitivity flag (for example, title match or manual/learned relevance review)
before inferential trend comparisons. Expand the audit with negatives and a second
reviewer. Persist the config hash with extracted labels. Never convert the 53, 15,
or 4 pilot matches into population prevalence without the probability-sample
design and uncertainty, and never treat those counts as comparable to full native
API aggregates without qualification.
