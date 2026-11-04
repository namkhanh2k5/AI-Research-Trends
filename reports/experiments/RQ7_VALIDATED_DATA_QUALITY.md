# RQ7.1 validated data-quality layer

The original A/B/C three-stage metrics are unchanged: raw OpenAlex, cleaned OpenAlex and integrated OpenAlex+Crossref for the same 1,500 works. New **D — validated-enrichment evidence** is an audit layer, not a replacement work table.

| Measure | Observed |
|---|---:|
| Publisher fields added, coverage gain | 167 |
| Publisher additions with AI source-backed correctness | 1 |
| Publisher additions without source-backed check | 166 |
| Human-adjudicated publisher additions | 0 |
| License fields added, metadata coverage gain | 277 |
| License additions with syntactically valid URLs | 277 |
| License additions with verified reuse rights | 0 |
| License additions with unresolved rights | 277 |
| Venue-name additions | 2 |
| ISSN additions | 3 |

The one source-backed publisher check is AI-performed, not a human adjudication and not a representative accuracy estimate. Zero verified reuse-rights findings means **no rights assessment has been completed**, not that licenses are invalid. Provider agreement and URL syntax are insufficient for verified quality gain. Group A/B recovery is nonrepresentative of the whole original corpus; Group B was deliberately selected for metadata gaps. Publication counts, citations, OA analysis, classifier and website are unchanged. [Coverage figure](../figures/rq7_validation/01_coverage_vs_verified.png).
