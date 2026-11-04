# RQ7.1 Crossref HTTP 404 investigation

The pilot had **440** Crossref HTTP 404 DOI tasks. A fixed, disjoint diagnostic stratum selected **20** with verified stored 404 response checksums and valid normalized DOI syntax. The [DOI Foundation Which RA? service](https://www.doi.org/the-identifier/resources/factsheets/doi-resolution-documentation) was queried once per selected DOI, using **20** logged requests; no Crossref retry or new OpenAlex collection was made.

| Measure | Observed |
|---|---:|
| Selected stored 404 cases | 20 |
| Agency HTTP 200 responses | 20 |
| DataCite registration confirmed | 19 |
| Crossref registration confirmed | 0 |
| No RA identified / unresolved | 1 |
| DOI syntax failures | 0 |

The unknown case returned DOI Foundation status `DOI does not exist`; it is not automatically classified as malformed syntax or a transient Crossref failure. Of these 20, **19** are explained by non-Crossref registration. The remainder is **UNKNOWN_REASON** until further identity investigation. This diagnostic sample is not a census of all 440. Its cross-Group A/B selection is shown in the sampling report. No DOI is publicly printed here.
