# Full-Corpus Collection Cost Estimate — NOT authorization to crawl

Observed local work raw size: 16,203 bytes/work (original 12,000-work run). Eight original Parquet tables: 752 bytes/work. Original 12,000-work collection duration: 271 seconds (timestamp difference, including rate limits and overhead). Crossref pilot: 0.595 seconds per HTTP request, 6,391 response bytes/request. Historical inventory DOI-bearing fraction: 90.4%, **not a full-population estimate**.

| Scenario | OpenAlex work pages (100/page) | Indicative list credits / USD | Raw work GiB | Phase-3 Parquet GiB | OpenAlex retrieval hours* | Crossref DOI requests† | Crossref serial days† |
|---|---:|---:|---:|---:|---:|---:|---:|
| Existing local | 0 | 0 / $0.00 | 0.00 | 0.00 | 0.00 | 0 | 0.0 |
| 20k new works | 200 | 200 / $0.02 | 0.30 | 0.01 | 0.13 | 18,081 | 0.1 |
| 50k new works | 500 | 500 / $0.05 | 0.75 | 0.04 | 0.31 | 45,203 | 0.3 |
| 100k new works | 1,000 | 1,000 / $0.10 | 1.51 | 0.07 | 0.63 | 90,406 | 0.6 |
| Full historical 937,493-work snapshot | 9,375 | 9,375 / $0.94 | 14.15 | 0.66 | 5.88 | 847,554 | 5.8 |


*Retrieval duration is a crude linear scaling of one 12,000-work run. It omits changing quota, retries, cursor behavior, server load, network and preprocessing. †Crossref numbers apply the nonrepresentative observed DOI fraction and sequential pilot rate; no full-coverage requirement is justified. Source metadata: this local inventory has 3,970 unique source IDs, of which 1,151 lack a publisher or known type; the 30-singleton pilot spanned 16.3 seconds between its first and last saved responses. A local-only scenario needs **0** new Source requests; exhaustive enrichment of *these already observed missing IDs* would need at most 1,151 singleton requests, before deduplication and failed lookups. For new work cohorts the unique missing-ID count is **not estimable reliably** by linear scaling because venue reuse is heavy-tailed. DBLP requests are zero in this pilot and excluded. Deduplication/integration and checksum throughput were not separately timed, so their large-scale durations are **NOT VERIFIED**; the local 11,539-record full-source inventory plus existing verifiers took 33.815 seconds on this host, not an independent full-corpus benchmark. OpenAlex list pricing is estimated from the observed rate-limit endpoint (1 credit / $0.0001 per list call on 2026-11-04), subject to provider changes; singleton source lookups were observed at 0 credits. Crossref public REST API requires rate-limit courtesy and may return 404 for non-Crossref DOI registrants.

**Recommendation:** do not crawl the full historical population for venue discovery. First consider a targeted, transparent journal-history sample and independently judged shortlist relevance. Crossref identity recovery of one venue ID in 502 selected records does not justify hundreds of thousands of DOI lookups.
