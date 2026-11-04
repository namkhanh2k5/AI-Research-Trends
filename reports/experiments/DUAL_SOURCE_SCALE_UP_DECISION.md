# Dual-source ETL scale-up decision

Verdict: **CONDITIONAL GO** for a bounded follow-on to the original 12,000-work sample; **no authorization for a new crawl**. Incremental metadata additions across publisher, venue, ISSN and license: 449 field instances (not unique works). Exact linked works: 944 / 1,500. Independent correctness remains unverified, so full-scale enrichment should be preceded by a small human/official-source validation of recovered fields.

Measured new OpenAlex attempts: 37; new Crossref attempts: 1,303; cache hits: 84; raw bytes: 36,285,632. These scenarios linearly scale observed request/storage rates from the mixed A+B pilot and do **not** predict match rate, representative missingness, rate limits, or fees:

| Cohort size | Fresh Crossref HTTP attempts at observed rate | Raw response storage at observed size |
|---:|---:|---:|
| 1,500 | 1,303 | 35 MiB |
| 5,000 | 4,343 | 115 MiB |
| 12,000 | 10,424 | 277 MiB |
| 25,000 | 21,717 | 577 MiB |
| 50,000 | 43,433 | 1,153 MiB |
| 100,000 | 86,867 | 2,307 MiB |

At 12,000 works, expected calls depend on DOI availability, cache reuse, registry coverage and provider changes. Group A should be used for rough scenario planning, not targeted Group B. A full 937k-work dual-source crawl is out of scope.
