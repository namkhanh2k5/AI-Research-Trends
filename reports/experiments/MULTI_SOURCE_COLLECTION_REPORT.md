# Multi-Source Collection Report

Pilot design: 500 distinct DOI values selected deterministically across year × local venue-presence strata (seed 20261104). This intentionally enriches missing cases and is **not population-representative**. Responses are stored byte-for-byte under `data/analysis/venue_discovery_experiment/venue_poc_20261104_v1` with per-response SHA-256 and checkpoint manifests. No original raw file was modified.

| Provider/action | HTTP attempts | Valid 200 | 404 | Bytes |
|---|---:|---:|---:|---:|
| Crossref selected DOI details | 500 | 289 | 210 | 3,195,332 |
| OpenAlex unique Source details | 30 | 30 | 0 | 642,887 |
| OpenAlex retracted-work sample | 1 | 100 works | 0 | 1,497,847 |
| Crossref retraction DOI details | 100 | 100 | 0 | 929,618 |

The selected-DOI Crossref manifest is **incomplete by quality status** despite all 500 requests being stored: one HTTP 200 response carried a DOI different from the requested DOI and was quarantined, not merged. 210 404s are expected registry misses, not claims that the DOI is invalid. Crossref DOI registration is not universal. The other two provider manifests are complete.

Observed Crossref request rate: 1.68 HTTP/s over 297.6 seconds. The response advertised a public-single rate limit of 5/s and concurrency 1; requests were sequential with 0.3-second minimum spacing. OpenAlex rate-limit preflight reported 10,000 daily credits remaining; 30 source singleton lookups were 0 credits in observed headers, and the retraction list request cost 1 credit. A separate preflight rate-limit request and one Crossref HEAD probe were made; these are not counted in the table above. No DBLP calls were made because the development set has no resolved conference target and a broad conference lookup would not establish reliable evaluation.

Official API references: [OpenAlex authentication/rate limits](https://help.openalex.org/api/authentication/), [OpenAlex pricing](https://help.openalex.org/access/pricing/), [Crossref REST API](https://www.crossref.org/documentation/retrieve-metadata/rest-api/).
