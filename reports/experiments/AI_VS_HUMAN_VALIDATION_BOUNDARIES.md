# Evidence boundaries: AI, providers, official sources and human review

| Evidence level | What this experiment actually establishes | What it does **not** establish |
|---|---|---|
| AUTOMATED_SYNTAX_CHECK | DOI/URL shape, response status, unique IDs and SHA-256 integrity. | Publisher identity or topic semantics. |
| AI_SEMANTIC_ASSESSMENT | One assistant's reasoned topic choices for 140 blind papers and fourteen topic-scope notes. | Calibrated accuracy, independent human agreement, or OpenAlex error rates. |
| PROVIDER_AGREEMENT | Crossref/OpenAlex values and DOI redirects can be compared. | Independent correctness when upstream data are shared. |
| OFFICIAL_SOURCE_BACKED | Nine of thirty selected publisher cases have matching publisher-maintained article/journal/company evidence; one also has an independent directory. | Publisher correctness of the other 21 cases or all 167 recovered values. |
| HUMAN_ADJUDICATED | **Nothing yet**; no genuine reviewer ratings have been received. | Any human semantic validation or publisher adjudication claim. |
| NOT_VERIFIED | Truth of unreviewed topic decisions and unresolved publisher cases remains unknown. | A negative finding or proven error. |

The assistant is one AI assessor, not two independent human raters. Repeated prompts to the same model would not solve this independence problem. The exact backend model/version was not exposed, so even AI-assessment reproducibility is limited to the frozen inputs, outputs, protocol notes and hashes; stochastic re-inference cannot be claimed bit-for-bit reproducible.

The reviewer-specific `reviewer_a` and `reviewer_b` packages were not prefilled or modified. AI record-level judgments are in a separate Git-ignored directory and must not be shown to raters before they independently submit their sheets. The restricted answer keys and model predictions were not consulted before freezing decisions. The 2025 final-test labels were not opened; `allow_final_test_execution: false` remains in the frozen protocol.

Future strong academic claims require: two authorized humans independently completing both blind sheets; validation of their 40/100 response counts; disagreement adjudication under a documented protocol; only then a protected key join; and independent human confirmation of publisher cases that remain unresolved or are proposed for downstream use. `HUMAN_TOPIC_VALIDATION = PENDING` and `HUMAN_PUBLISHER_ADJUDICATION = PENDING` until that happens.
