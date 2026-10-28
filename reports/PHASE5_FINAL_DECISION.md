# Phase 5 final feasibility decision — **NO-GO** for citation-aware discovery as the main ML task

Date: 2026-10-28. This is a decision about the proposed *undergraduate-course main ML component*, not a judgment that RQ5 reference analysis is useless. Phases 1–4 and the exploratory [RQ5 report](PHASE5_REFERENCE_EDA_REPORT.md) remain valid. No supervised citation recommender, website, extra historical crawl or Phase 1–4 reprocessing was started.

## 1. Is the proposed task feasible with our data?

**Not as the main 3–4-model supervised task.** The 5,141 eligible sampled queries establish enough query text, but historical candidate IDs are sparse and most of the full pool remains without date metadata. Using every historically available citing work improves 2023 median ID overlap only from 10.0% to 12.1% at the preselected ≥2-citer threshold; even ≥1 gives 23.7%. A bounded 1,000-ID, historically selected metadata subset yielded 973 records, but only 7.13% of all 2023 observed reference edges are known exact-date nonfuture overlaps in that subset. The simple fusion baseline recovers a mean 2.53% of observed references at 20 recommendations across all 909 queries. This is not credible evidence for a broad user-facing related-work finder.

| Measurement | Original Phase 5 audit | Expanded historical-citer reassessment | Bounded metadata/retrieval diagnostic |
|---|---:|---:|---:|
| 2023 eligible evaluation queries | 909 | 909 | 909 |
| Permitted historical citing works | 2,372 eligible queries | 3,444 edge-bearing sampled works | Same 3,444; selection uses only their frequencies |
| Candidate IDs, ≥2 distinct historical citers | 8,183 | 12,019 | 1,000 selected IDs; 973 retrieved (not the full ≥2 pool) |
| Median 2023 reference-ID overlap, ≥2 pool | 10.0% | **12.1%** | Not directly comparable: selected subset median date-valid overlap 3.70% |
| 2023 zero ID-overlap queries, ≥2 pool | 23.2% | **19.0%** | 341/909 have no date-valid positive in the selected subset |
| Observed 2023 reference edges in ≥2 pool | 5,442/37,980 | 6,347/37,980 | 2,708/37,980 exact-date nonfuture edges in the separately selected subset |
| Mean end-to-end Recall@20 | Not evaluated | Not evaluated | 2.53% for fusion on 959 date-eligible candidates |

The 40% median-ID-overlap benchmark was provisional. The decision rests on the complete pattern: modest gain from removing an unnecessary citer-eligibility restriction, a very broad long-tail reference universe, unresolved temporal coverage, and low end-to-end recovery in a bounded diagnostic. The original and expanded ID-overlap figures are not model scores. The selected-subset date-valid and retrieval figures have a different candidate universe and should not be read as a decrease caused by enrichment.

## 2. Strongest evidence and 3. main risks

The expanded 2020–2022 graph contains 127,802 distinct edges from 3,444 citing works, yet its ≥2 pool of 12,019 IDs overlaps only 6,347 of the 37,980 held-out 2023 reference edges; 19.0% of queries have zero overlap. The larger ≥1 pool has 98,201 IDs but still only 23.7% median overlap. Five fixed-seed subsamples show continued growth, not a proven plateau: at ≥2, median overlap progresses 4.4%, 7.7%, 10.0%, 12.1% at 25/50/75/100% of observed historical citers. The last observed increment is small relative to the gap, but no reliable beyond-sample extrapolation is available. [Full distributions and later-year cutoffs](PHASE5_COVERAGE_REASSESSMENT.md).

The targeted API check found 27/1,000 unavailable IDs (HTTP 404), 972/973 exact dates, and 16 currently post-2022 publication years among returned candidates that had appeared in 2020–2022 reference lists. For 2023 evaluation overlaps inside the retrieved subset, 64 edges are future-dated and five have unknown dates. Of the 6,347 overlapping ≥2-pool edges, **3,578 remain unenriched**; temporal validity of the whole pool is therefore not established. OpenAlex can revise metadata, citation edges and IDs. The fixed-seed Phase 2 sample is not a verified probability sample of the full citation graph. OpenAlex references are not human relevance judgments; uncited papers are unobserved rather than confirmed irrelevant. No historical source snapshot, human evaluation, deduplication of all cited versions, or application study exists.

## 4. Is further collection justified?

**No large extra historical crawl is justified now.** A modest additional collection might increase coverage—the observed curve does not prove saturation—but the current data do not justify the cost or course-schedule risk of a broad rescue crawl. Metadata enrichment solves missing attributes for already selected IDs, not missing historical pool membership. We stopped at 1,000 selected API IDs, below the 3,000-ID investigation cap, because the result was sufficient to decide. [OpenAlex's current authentication/rate documentation](https://help.openalex.org/api/authentication/) describes rate-limit headers and a programmatic `/rate-limit` endpoint; the project used the existing bearer-key client and never recorded the key. Singleton lookups are listed as free in the [official cost examples](https://help.openalex.org/access/example-costs/). Any future graph expansion should be a separately approved, pre-registered experiment with yield/cost criteria, not an attempt to force the original task past a benchmark.

## 5. Can the full supervised component realistically be completed here?

Not for this citation-recovery design without disproportionate new graph collection, metadata validation and relevance evaluation. Although 568/909 queries have at least one date-valid reference in the bounded metadata subset and fusion hits one observed reference for 398/909, its mean end-to-end Recall@20 is only 2.53% and the candidate subset is deliberately incomplete. Conditional Recall@20 of 34.97% is computed only on the 568 covered queries and cannot substitute for end-to-end usefulness. Building four supervised rankers on this proxy would shift effort away from the project's stronger data-engineering and statistical goals without solving the candidate ceiling.

## 6. Switch direction: audited alternatives

Both alternatives can reuse the immutable Phase 2 raw records and Phase 3 work text. The counts below were measured from the local 12,000-work dataset, not assumed from OpenAlex globally.

| Alternative | Local label/text audit | Main scientific and engineering risks | Course fit |
|---|---|---|---|
| A. Scope-fit journal discovery | Primary-location source ID exists for 11,574/12,000 works; 8,584 have source type `journal`. Among journal works with title and abstract, 6,648 papers span **2,986** journal IDs; **2,118** labels are singletons. Only **29** journals have ≥20 such papers, covering **1,355** works. All 2,986 observed journal IDs have a display name in this local subset. | Publication venue is not a ground-truth “best-fit” journal; extreme long tail and class imbalance make meaningful multiclass evaluation difficult. A useful catalogue needs stable source metadata, scope descriptions and probably much more labelled data. Preprints/repositories must be excluded or treated separately. | Possible only after severe narrowing or new data; weak immediate choice. |
| B. Research-topic classification | 9,440 works have both title and abstract; all 12,000 have a primary OpenAlex topic. The 9,440 text-complete works span **106** primary-topic IDs; **89** IDs have ≥20 papers, covering **9,281** works. Largest class: **676**; top ten classes: **3,192**. Existing five native subarea memberships cover 3,683 distinct works but overlap. | OpenAlex topics are algorithmically assigned, so training on them can merely imitate OpenAlex; primary topic is single-label but not human ground truth. Multi-membership and unlabelled-as-negative errors must be avoided. An independently adjudicated evaluation set is needed to support semantic claims. | More practical; directly connects to RQ1 and permits a bounded text-classification comparison if label audit passes. |

**Recommendation: switch the main ML direction to a narrowly scoped primary-topic text-classification study, conditional on a label-quality audit.** Preselect a manageable subset of sufficiently supported topics using training-side counts, retain other topics as “outside the selected task” rather than fabricated negatives, and manually adjudicate a small held-out sample before calling model outputs accurate research-topic predictions. A later controlled task could compare TF-IDF + majority baseline, Naive Bayes, logistic regression and linear SVM on query-disjoint/time-aware splits. Do not train these models in this feasibility task. Journal discovery remains a possible future idea but is less defensible with current class support.

## 7. Next concrete development task

Write a **topic-label audit protocol and a reproducible candidate-label table** from the existing verified Parquet data; choose 8–15 supported primary topics, inspect class/year/type balance, and obtain an independently reviewed held-out annotation sample. Define the task's success metric and leakage-safe split *before* fitting models. If the annotation audit finds unusable labels, narrow to a descriptive classification exercise rather than claim an external topic ground truth.

Validation and Git delivery are documented in the repository history and the final task handoff. No result here claims coverage of all global AI research or that a citation predicts scientific quality.

## Reproducibility checks

The first audit's read-only verifier passed (three Phase 3 source-table hashes, 25 output artifacts, three published reports, four original published figures). The reassessment manifest verified 5/5 outputs, and independent reruns matched all five CSV/PNG hashes. The enrichment verifier passed 1,000/1,000 selected-ID responses and raw hashes, including 27 recorded 404 responses. The retrieval diagnostic verified 3/3 CSV hashes; independent runs matched all three deterministic CSV outputs. Hardware-dependent latency is stored in the manifest rather than a deterministic result table. Offline `pytest -q -ra` collected 127 tests: 126 passed, one opt-in live test skipped. The same live test passed separately with the configured key. `pip check` found no broken requirements; the three new console-script `--help` commands executed after reinstalling the editable package. Local generated data and the API key remain Git-ignored.
