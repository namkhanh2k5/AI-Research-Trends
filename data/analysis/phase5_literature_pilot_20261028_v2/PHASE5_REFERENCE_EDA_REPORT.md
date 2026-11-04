# RQ5 — What prior literature does sampled AI/CV research build on?

This is an **exploratory Phase 5 extension** to RQ1–RQ4. It describes reference
frequencies within 12,000 sampled citing works, not all OpenAlex works,
global citation counts, scientific quality or mandatory citations. The fixed-seed
sample is not a verified probability sample.

## Reference availability

289,110 unique edges point to 207,102
distinct referenced Work IDs. The sample has
7,529 recorded nonempty lists,
4,471 recorded empty lists, and
0 missing lists.
`reference_distribution_by_year.csv`, `reference_distribution_by_type.csv`,
`reference_distribution_by_subfield.csv` and `reference_availability_native_categories.csv`
give denominators and missingness. Native category memberships overlap; they are not
exclusive subareas. List absence is not proof that a work cites nothing.

![Observed reference counts per sampled work](figures/phase5/references_per_work.png)

## Observed citation concentration

Gini coefficient of distinct sampled citing-work frequencies:
0.264. The top 1% and 5% of
referenced IDs account for 12.8%
and 24.3% of observed
edges, respectively. This is within-sample concentration, not global influence.

![Lorenz curve for sampled reference edges](figures/phase5/reference_lorenz.png)

## Reference age and metadata coverage

Only 727/289,110 observed edges have a
referenced work also present in the 12,000-work sample and thus a locally verified
publication date. 288,383 edges lack local candidate
date metadata; 13 matched edges are future-dated relative
to their citing paper and are excluded from age summaries. For the
714 non-future matched edges only, median age is
1.74 years and 98.3%
are at most five years old. These are a highly selected matched-in-sample subset,
**not** an estimate of reference age in the full citation graph. `reference_age_known.csv`
and `reference_age_by_subfield.csv` preserve the restricted denominator. No dates
were invented for external referenced IDs.

## Primary-subfield core lists

`top_references_by_subfield.csv` ranks each primary subfield's top 20 referenced IDs
by distinct supporting sampled citing works. Titles appear only when a referenced
work is itself in the local sample. Top-list overlap: 1702 vs 1707: 8/32 (Jaccard 0.250). This is a
descriptive signal of shared versus specialized observed reference lists, not a
research-quality ranking. Most cited IDs lack local title/age metadata; no external
metadata were fetched in this pilot.

## Coverage and inference limits

The ≥2-citer historical candidate pool has 8,183 IDs, and its
eligible 2023 query median **ID-level** reference overlap is 10.0%.
Pool overlap is the ceiling for a retriever that can only rank those IDs;
candidate-generation recall has **not** been measured. A fixed-seed sample of
citing works, incomplete references, unknown candidate dates and possible OpenAlex
metadata updates limit inference. See the [G1/G2 feasibility report](PHASE5_FEASIBILITY_REPORT.md).
