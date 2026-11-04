# Multi-Source Venue Discovery Experiment — Final Decision

## Executive summary

**RQ7: CONDITIONAL GO** for bounded provenance/publisher enrichment, but not broad Crossref harvesting to repair venue identity. **RQ8: CONDITIONAL GO only for an explicitly limited journal-focused *research* prototype; NO-GO for broad journal/conference recommendation.** This experiment does not change RQ1–RQ6, the frozen classifier, website, or the sealed 2025 test.

The historical local data already have 8,178 journal-type source records and only 30 conference-type source records. Crossref recovered only 1 additional stable venue identity in the 502-record selected cohort, while reducing missing publisher from 280 to 211. In 2024 development, 592 historically supported venues yield an oracle candidate coverage of 35.4%. The best simple baseline (venue TF-IDF profiles) reaches Recall@5 = 12.3%, versus 4.9% popularity, with no conference evaluation target.

## Evidence and decision

1. **Local data:** 11,539 historical source records, 11,506 unique IDs, 3,970 hosting source IDs. Repositories are not journal/conference labels.
2. **Bounded new collection:** 500 Crossref DOI lookups, 30 OpenAlex Source singletons, one OpenAlex retraction sample request and 100 Crossref retraction DOI lookups. One mismatched Crossref DOI quarantined. No DBLP or full-corpus crawl.
3. **Cleaning:** DOI/ISSN/source IDs normalized; 33 repeated Work IDs deterministically resolved for paper links with full row-level audit. 39 provider-year differences retained, not silently overwritten. Canonical IDs use stable identifiers, not names alone.
4. **Retractions:** 39/100 have explicit Crossref `update-to` retraction evidence; absence for the rest is unknown status, not a contradiction or accuracy score.
5. **Retrieval:** temporal train 2020–23 (7,002 eligible works), 2024 development (1,843 queries); common 592-venue pool; no true query venue/topic leakage. The existing frozen classifier routes 806 queries. Results are development-only, and human venue-suitability validation is NOT VERIFIED.
6. **Scaling:** full-corpus work metadata and especially DOI-by-DOI Crossref enrichment have significant request/storage/time cost for little demonstrated venue-ID gain. See cost report; no broad crawl is authorized.

**Next smallest step:** obtain a bounded independent human relevance assessment of journal shortlists for a predeclared journal-only query set, then decide whether targeted journal-history expansion is worthwhile. Do not modify the final website or treat this pilot as an accepted venue recommender.

## Validation and preservation

`.venv/bin/python -m pytest -q -ra -o addopts=''`: **231 passed, 9 skipped, 0 failed**. `python -m pip check`: No broken requirements found. Read-only source verifiers passed for the original 12,000-work Phase 2 collection, the 2,515-record targeted expansion, integrated Phase 2 tables, 64 Phase 4 outputs, and 14 closed-set plus 23 open-set ML output files. The frozen model bundle was loaded with checksum checks. **2025 FINAL TEST: SEALED**, neither opened nor evaluated. Browser tests and the opt-in live sampling test are among the skips; this is an experiment, not a website test.

## Supporting reports

- [Local inventory](experiments/VENUE_DATA_INVENTORY.md)
- [API collection and provenance](experiments/MULTI_SOURCE_COLLECTION_REPORT.md)
- [Retraction audit](experiments/RETRACTION_QUALITY_AUDIT.md)
- [RQ7 integration](experiments/RQ7_MULTI_SOURCE_DATA_INTEGRATION.md)
- [RQ8 retrieval](experiments/RQ8_VENUE_DISCOVERY_FEASIBILITY.md)
- [Cost estimate](experiments/FULL_CORPUS_COLLECTION_COST_ESTIMATE.md)

Original Phase 2/3 evidence remains checksum-verifiable. Record-level experiment files, API bodies, query text and model index stay Git-ignored. A successful code test is not independent correctness validation.
