# RQ7 — Dual-source data-quality evaluation

The experiment compares raw current OpenAlex, normalized current OpenAlex, and OpenAlex+Crossref on **the same** selected 1,500 works. Group B is intentionally enriched for missingness and is not representative of the OpenAlex population.

## Combined cohort

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

## Group A — general evaluation (n=1,200)

| Metric | Raw OpenAlex | Cleaned OpenAlex | Integrated | Integrated − cleaned |
|---|---:|---:|---:|---:|
| valid_doi | 1,087 | 1,087 | 1,087 | +0 |
| abstract | 948 | 948 | 948 | +0 |
| publisher | 993 | 993 | 1,128 | +135 |
| venue_name | 1,157 | 1,157 | 1,157 | +0 |
| issns | 1,085 | 1,085 | 1,086 | +1 |
| publication_date | 1,200 | 1,200 | 1,200 | +0 |
| license | 510 | 510 | 782 | +272 |
| invalid_doi | 0 | 0 | 0 | +0 |
| duplicate_work_ids | 0 | 0 | 0 | +0 |
| duplicate_dois | 0 | 0 | 0 | +0 |
| Work-level raw/provenance evidence | 1,200 | 1,200 | 1,200 | 0 |
| Cross-provider differences | N/A | N/A | see conflict audit | N/A |

## Group B — targeted missingness (n=300)

| Metric | Raw OpenAlex | Cleaned OpenAlex | Integrated | Integrated − cleaned |
|---|---:|---:|---:|---:|
| valid_doi | 300 | 300 | 300 | +0 |
| abstract | 266 | 266 | 266 | +0 |
| publisher | 261 | 261 | 293 | +32 |
| venue_name | 281 | 281 | 283 | +2 |
| issns | 242 | 242 | 244 | +2 |
| publication_date | 300 | 300 | 300 | +0 |
| license | 103 | 103 | 108 | +5 |
| invalid_doi | 0 | 0 | 0 | +0 |
| duplicate_work_ids | 0 | 0 | 0 | +0 |
| duplicate_dois | 0 | 0 | 0 | +0 |
| Work-level raw/provenance evidence | 300 | 300 | 300 | 0 |
| Cross-provider differences | N/A | N/A | see conflict audit | N/A |

## Per-field recovery

| Field | Missing before | Crossref available | Valid additions | Deferred | Conflicts | Missing after |
|---|---:|---:|---:|---:|---:|---:|
| publisher | 246 | 944 | 167 | 0 | 571 | 79 |
| venue_name | 62 | 840 | 2 | 0 | 166 | 60 |
| issns | 173 | 832 | 3 | 0 | 166 | 170 |
| license | 887 | 637 | 277 | 0 | 360 | 610 |
| abstract | 286 | 465 | 0 | 20 | 60 | 286 |
| publication_date | 0 | 944 | 0 | 0 | 243 | 0 |

“Valid additions” means exact DOI linkage plus the field's basic parsing/identifier policy, **not** independent confirmation that a publisher, venue name or license is scientifically correct.

Matched Crossref records: 944; title/year/type/provider conflicts: 2,597 field-level rows. Provider agreement is **not** independent correctness proof. Independent manual correctness assessment: **NOT VERIFIED**. Missing Crossref retraction evidence does not establish non-retraction.

The 944 work-type string differences largely reflect different provider taxonomies, not proven cataloguing mistakes. Crossref license arrays and OpenAlex license strings are not directly equivalent; coverage counts mean *some provider metadata exists*, not that rights have been independently adjudicated. The original-sample frame remains authoritative; 15 fresh OpenAlex records no longer satisfy the original membership definition and are reported as snapshot drift rather than silently dropped. OpenAlex population prevalence and official RQ1–RQ6 estimates are unchanged.

Figures: [missingness](../figures/dual_source_etl/01_missingness_before_after.png), [match status](../figures/dual_source_etl/03_doi_match_status.png), [publisher recovery](../figures/dual_source_etl/04_publisher_recovery_year.png), [request efficiency](../figures/dual_source_etl/10_request_efficiency.png). Ten aggregate-only PNGs are available in `reports/figures/dual_source_etl/`.
