# Bounded AI-assisted publisher-source audit

## Frozen cases and evidence hierarchy

The **same 30 distinct publisher-recovery cases** selected by RQ7.1 were investigated. The RQ7.1 review sheet SHA-256 is `0c078c617ced7c0d58969aae212e639c83a4885d428bd2d2ddee1fa35f3df943`; the original sheet was not filled in or altered. DOI resolution and publisher-hosted pages were inspected. An authoritative publisher claim required the article identity plus a publisher-maintained journal, corporate or article source; Crossref metadata alone and mirrored aggregator metadata were not accepted as independent confirmation. One previously recorded case also has an independent publisher-directory source. DOI/title links and record-level URLs are stored **only** in the ignored private Parquet/evidence files.

| Decision | Cases |
|---|---:|
| SOURCE_BACKED_CORRECT | 6 |
| SOURCE_BACKED_ACCEPTABLE_ALIAS | 3 |
| SOURCE_BACKED_INCORRECT | 0 |
| AMBIGUOUS | 12 |
| INSUFFICIENT_EVIDENCE | 4 |
| SOURCE_ACCESS_BLOCKED | 5 |
| **Total inspected** | **30** |

Nine cases have official-source-backed identity evidence. Of these, six match a publisher name directly and three use a defensible brand/legal-name or punctuation variant. There is **no proven incorrect case**, which is different from proving all remaining cases correct. One of the nine includes an additional independent publisher directory; the others rely on the publisher's own website, which is authoritative for its stated identity but not an independent third-party review.

The observed consistency among the nine source-verifiable cases is 9/9. A mechanical Wilson 95% interval is **[0.701, 1.000]** for that selectively verifiable denominator; it must **not** be generalized to the convenience-selected 30 or the 167 publisher additions. A 30-case denominator would improperly count 21 unresolved cases as either true or false. Genuine human adjudication remains **0/30**.

### Reasons for unresolved status

- A DOI can resolve to a preprint *platform* while its Crossref publisher field names a parent company or legal entity. A platform name alone does not prove legal publisher identity.
- A journal article page can show its journal brand without asserting that the journal is the legal publisher.
- Third-party aggregators can repeat provider-supplied metadata; provider agreement is not independent source evidence.
- Five destinations produced an HTTP denial, 404, bot-verification page or fetch failure. No CAPTCHA/paywall bypass was attempted.
- One publisher-brand discrepancy was left AMBIGUOUS rather than declared incorrect without proof that it is not an imprint or historical alias.

## Request accounting and preservation

The dedicated DOI collector made **30 direct GET attempts** and recorded **74 HTTP transactions including redirects**, below its configured 120-transaction ceiling. Four exploratory direct GET attempts occurred outside the collector; their redirects were not separately instrumented. Five browser-search calls submitted 20 search queries; the browser backend does not expose its underlying HTTP request count. Thus the exact total of all external HTTP transactions is **NOT VERIFIED**; the bounded collector itself is verified. No OpenAlex/Crossref bulk crawl was performed. Original RQ7 and RQ7.1 data remain unchanged.

Private evidence: `data/analysis/ai_assisted_validation/ai_assisted_20261104_v2/publisher/`; the final publisher assessment Parquet SHA-256 and source-page response hashes are in its manifests. Positive decisions include official URLs; blocked/ambiguous cases remain unresolved. Evidence from an official site can still be wrong or stale; it is not equivalent to independent human adjudication.

**Verdict:** `PARTIAL EVIDENCE — FURTHER REVIEW REQUIRED`. The evidence justifies only a small, targeted, versioned publisher-enrichment follow-up with human checking; it does not justify claiming all 167 additions correct or expanding Crossref to the full 12,000-work analytical dataset.
