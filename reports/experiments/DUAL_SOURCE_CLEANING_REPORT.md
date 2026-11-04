# Dual-source cleaning — observed RQ7 pilot

Three stages use the same 1,500 Work IDs. No missing bibliometric values were imputed. OpenAlex inverted-index abstracts were reconstructed; Crossref markup is sanitized only for comparison and is not published.

| Metric | Raw OpenAlex | Cleaned OpenAlex | Integrated | Integrated − cleaned |
|---|---:|---:|---:|---:|
| valid_doi | 1,387 | 1,387 | 1,387 | +0 |
| abstract | 1,214 | 1,214 | 1,214 | +0 |
| publisher | 1,254 | 1,254 | 1,421 | +167 |
| venue_name | 1,438 | 1,438 | 1,440 | +2 |
| issns | 1,327 | 1,327 | 1,330 | +3 |
| publication_date | 1,500 | 1,500 | 1,500 | +0 |
| license | 613 | 613 | 890 | +277 |
| invalid_doi | 0 | 0 | 0 | +0 |
| duplicate_work_ids | 0 | 0 | 0 | +0 |
| duplicate_dois | 0 | 0 | 0 | +0 |
| Work-level raw/provenance evidence | 1,500 | 1,500 | 1,500 | 0 |
| Cross-provider differences | N/A | N/A | see conflict audit | N/A |

Exact DOI matching is mandatory. Crossref 404 means not found in this registry at this snapshot, not an invalid DOI. The 3 DOI-mismatched HTTP 200 responses remain raw evidence but are quarantined from canonical field merging; `provider_links.quarantine_reason` records the decision. Different publication years can reflect online versus print dates and are preserved as conflicts, not automatically fixed. Crossref `container-title` fills a missing *venue name* but does not establish a stable venue identity. OpenAlex remains the frame authority; a Crossref retraction relation does not silently alter original corpus membership.

Observed field-level disagreements: 2,597; snapshot-drifted works: 36; duplicate/shared-DOI and drift audit rows: 36. Provider type labels use different taxonomies and account for 944 differences; these are **not** 944 proven work-type errors. Invalid ISSN values observed: OpenAlex 0; Crossref 0. Malformed OpenAlex abstract indexes: 0, flagged without inventing text. Current OpenAlex records outside the original frame definition: 15; non-disjoint reasons: {'date_outside_2020_2024': 1, 'type_outside_article_review_preprint': 12, 'primary_subfield_outside_1702_1707': 2, 'new_retraction_flag': 0}. Current retraction flags: 0. These are flagged for review, not silently removed. Raw provider evidence remains immutable in the local run directory.
