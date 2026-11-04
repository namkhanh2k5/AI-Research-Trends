# Dual-source collection — observed RQ7 pilot

- Cohort: 1,500 original-sample works from 2020–2024; Group A 1,200, Group B 300.
- New OpenAlex HTTP attempts: 37; verified batch responses: 30; singleton alias probes: 7.
- Crossref DOI tasks: 1,387; fresh HTTP attempts: 1,303; reused prior checksum-verified cache: 84.
- Crossref HTTP 200: 947; HTTP 404: 440; parsed exact DOI matches: 944 (68.1% of DOI tasks).
- Raw response bytes stored: 36,285,632; request cap: 1,500 new Crossref HTTP attempts.
- Collection elapsed: 1,116.000 seconds. Provider-normalization/integration elapsed: 3.907 seconds. Read-only validation elapsed: 1.569 seconds. Processed Parquet bytes: 1,598,299.
- OpenAlex provider-reported batch query cost: NOT AVAILABLE in stored responses; singleton alias probes are not included in this sum. Crossref is a public Polite API, not a paid Plus account.
- Historical collection anomalies: 7 recorded OpenAlex ID-drift/checkpoint events, subsequently verified through singleton alias evidence. Completed-run HTTP 429/5xx final responses: 0. Intermediate retry status codes were not separately persisted, so their exact breakdown is NOT VERIFIED.
- Crossref connection preflight at 2026-11-04T04:03:51+00:00: HTTP 200, observed `x-api-pool=polite-array`; rate-limit header 3/1s, concurrency header 3. These are observations, not permanent guarantees.
- OpenAlex connection preflight: HTTP 200 with configured bearer key; observed remaining credits 9966 of 10000 at the preflight time. Provider-reported per-response credit data are retained in local raw manifests.
- Collection started: 2026-11-04T03:46:25+00:00; completed: 2026-11-04T04:05:01+00:00.
- Source frame and selection checksums: local `plan.json`; raw response checksums: local `collection_manifest.json`.

Official access documentation: [Crossref](https://www.crossref.org/documentation/retrieve-metadata/rest-api/access-and-authentication/), [OpenAlex](https://help.openalex.org/api/authentication/).
