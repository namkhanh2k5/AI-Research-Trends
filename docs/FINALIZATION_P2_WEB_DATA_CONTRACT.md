# Finalization Phase 2: website data contract

The future Research Topic Explorer consumes the versioned, verified local package at `data/analysis/finalization_p2_web_data_20261101_v3/`. This is **not** a public web server or a live OpenAlex endpoint. Instantiate `ResearchData(run_dir)` from `ai_research_trends.analysis.web_queries`; construction verifies the package manifest and all output checksums. Publication text is untrusted and must be escaped by a future frontend, never rendered as executable HTML.

The paper index and Topic Brief sample metrics contain **only the original 12,000-work analytical sample**. The targeted 2,515-work ML training expansion is excluded. Its selection was topic-targeted and must not contaminate research landscape summaries. Phase 4 publication trends are a separate full-corpus OpenAlex aggregate; their `series` and `source_scope` fields must be displayed.

| Function | Return structure | Statistical scope |
|---|---|---|
| `get_research_overview()` | JSON object with corpus definition, sample size and missingness | Explicit population/sample distinctions |
| `get_publication_trends(series=...)` | list of year/count/growth records | Verified Phase 4 population aggregate, with retrieval snapshot caveat |
| `get_topics()` | 14 short IDs and official names | Frozen Catalogue B |
| `get_topic_brief(topic_id)` | official metadata, sample primary/any-topic counts, sample citation/OA/year summaries, related-topic links, five recent representative sampled papers, separate verified primary-topic population counts and snapshot time, warnings | Sample metrics and the 2026-11-01 OpenAlex population-topic snapshot are separate |
| `search_papers(keyword, topic_id, year, work_type, oa_status, sort, page, page_size)` | `{scope,total,page,page_size,items}`; page starts at 1; max page size 100 | Original sample paper explorer; keyword is a literal case-insensitive title substring |
| `get_citation_summary()` | Phase 4 citation descriptives | Original sample; age-dependent citations |
| `get_oa_summary()` | Phase 4 OA descriptives | Original sample; observational, no causal claim |
| `get_collaboration_summary()` | Phase 4 work-level and co-affiliation tables | Original sample; affiliation geography, not nationality |

`search_papers` accepts native OpenAlex topic IDs and searches the paper's *any-topic* list, which differs from the Topic Brief's primary-topic count. Sorting is either `publication_date_desc` or `citations_desc`; a result is not a scientific-quality ranking. It returns DOI/metadata as retrieved, with missing values retained. The future frontend must show sample scope, coverage warnings, and source timestamps adjacent to each summary.

Model-inference integration belongs to Finalization Phase 3: its input is title and abstract, its output is calibrated/ranked topic placement with model/version provenance and an uncertainty option. Neither classifier weights nor prediction quality are asserted by this data contract. The sealed 2025 test labels are absent from this web package.

Build and verify from the repository root:

```bash
openalex-build-web-data build --topic-population-dir data/analysis/finalization_p2_topic_population_20261101_v2 --output-dir data/analysis/finalization_p2_web_data_20261101_v3
openalex-build-web-data verify data/analysis/finalization_p2_web_data_20261101_v3
```

The build refuses to overwrite a run. Change the versioned output directory for a rerun.
