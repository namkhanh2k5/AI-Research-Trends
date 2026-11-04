# RQ7.1 publisher-correctness audit

The pilot added publisher values to **167/1500** works: Group A 135, Group B 32. Exactly **30 distinct publisher-recovery works** were selected (A 22, B 8). DOI linkage and Crossref parsing establish provenance, **not publisher correctness**. One selected case has an AI-performed, source-backed check linking an official article DOI page and an independent publisher directory; this is not a human adjudication or a random validation subsample.

| Measure | Observed |
|---|---:|
| Selected for independent review | 30 |
| AI source-backed publisher identities | 1 |
| Human-reviewed | 0 |
| Human-verified correct or alias | 0 |
| Human-verified incorrect | 0 |
| Still without independent source-backed correctness | 29 |
| Pending human review | 30 |

AI source-backed verification yield: **1/30 = 3.3%**. Among these source-checked cases, observed correctness is **1/1**; the mechanical Wilson 95% interval is **[0.207, 1.000]**. This interval is scientifically uninformative with a convenience-selected denominator of 1 and must not be extrapolated to all 167 recoveries. Human-review correctness: **NOT ESTIMABLE (0 denominator)**. Company aliases, imprints and host organizations need source-by-source review. Crossref and OpenAlex may share upstream metadata; provider agreement is not independent ground truth. Full-scale publisher expansion is gated on actual authoritative review, especially in Group A.
