# Dual-source OpenAlex + Crossref ETL pilot — final RQ7 report

**Verdict: CONDITIONAL GO.** This is a bounded data-engineering experiment, not a replacement for RQ1–RQ6 or the frozen topic classifier.

## Architecture and cohort

The original verified 2020–2024 OpenAlex analytical sample supplies 1,200 proportionally stratified general works and 300 disjoint DOI-bearing works with pre-specified metadata gaps. Newly retrieved OpenAlex metadata is the before/after baseline. Crossref is a secondary DOI-matched source. Current-versus-original OpenAlex differences are tracked separately as snapshot drift. The cohort is not a probability sample of the full originally defined AI/CV population.

## Collection and integration

30 verified OpenAlex batch responses, 1,387 Crossref DOI tasks, 84 verified cache hits, 944 exact DOI matches. Crossref 404: 440. OpenAlex ID aliases verified by singleton probes: 7. Canonical Work rows: 1,500.

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

## Scientific interpretation

Crossref can fill some missing deposited publisher, venue-name, ISSN and license fields, but does not prove their scientific correctness or resolve all venue identities. It does not repair OpenAlex population estimates or make targeted pilot proportions population representative. Online/print dates and work-type taxonomies can disagree; both provider values remain in conflict records. Abstracts are never published. The existing 100-work retraction audit remains separate from this originally non-retracted main cohort; 0 current OpenAlex retraction flags require separate interpretation.

## Downstream usability

Publisher/venue/ISSN additions can improve pilot descriptive subgroup metadata. No official RQ1–RQ6 result is recomputed; no frozen model is retrained; no 2025 sealed label or reviewer file was opened. The dual-source dataset is not automatically substituted into the web app.

## Evidence

Collection: [report](experiments/DUAL_SOURCE_COLLECTION_REPORT.md). Cleaning: [report](experiments/DUAL_SOURCE_CLEANING_REPORT.md). Integration: [report](experiments/DUAL_SOURCE_INTEGRATION_REPORT.md). Quality: [report](experiments/RQ7_DUAL_SOURCE_DATA_QUALITY.md). Scale-up: [decision](experiments/DUAL_SOURCE_SCALE_UP_DECISION.md). Local record-level evidence and SHA-256 manifests: `data/analysis/dual_source_etl_pilot/dual_source_rq7_20261104_v1`. Final offline tests: 249 passed, 9 skipped, 0 failed; pip check: No broken requirements found.
