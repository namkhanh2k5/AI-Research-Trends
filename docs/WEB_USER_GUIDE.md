# Web user guide

Start the local app with `streamlit run dashboard/app.py --server.address 127.0.0.1`, then open the printed localhost URL. The verified web-data package is required; the model is optional for all pages except classification.

1. **Home:** read the scope and headline counts. Publication counts come from population aggregates; detailed sample size is a different metric.
2. **Research Landscape:** switch RQ1–RQ4 tabs. RQ1 is a complete defined-population count. RQ2–RQ4 are original-sample summaries; no causal or quality claim is supported.
3. **Topic Explorer:** select a native OpenAlex topic, inspect official description, topic-level population trend and recent original-sample papers. Browse this page even without a model bundle.
4. **Classify My Research:** provide a nonblank title and ≥50-character/8-word abstract, click “Suggest topics”, review top three and status. Scores are SVM margins, not probabilities. Select and confirm a topic **yourself**. A suggestion is never assigned automatically; absent/short text is rejected. Input is not persisted to OpenAlex.
5. **Paper Explorer:** filter the 12,000 original sampled works by literal title keyword, native topic membership, year, type or OA; sort and paginate. Results are not a comprehensive OpenAlex search or a quality ranking.
6. **Methodology & Model Evaluation:** read dataset scope, 2024 development status, human-review status and sealed 2025 caveat.

The optional blind review UI is separate: `AI_TRENDS_REVIEWER=reviewer_a streamlit run dashboard/reviewer.py --server.address 127.0.0.1`. Give each real reviewer only their own package and output folder. Never expose the reviewer process publicly; never share restricted answer keys during annotation. A saved rating sheet may be incomplete. Export and run the existing `openalex-human-review validate-ratings` command when all examples are rated; completed sheets still require provenance and real independent sign-off before any semantic conclusion.
