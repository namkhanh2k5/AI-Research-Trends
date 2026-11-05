# Pre-Phase 2 Review

**Review date:** 2026-10-19 UTC

**Decision:** ready for a controlled 12,000-work collection; collection not started

## 1. Fixed estimands and retraction policy

The study remains the defined AI/CV primary-subfield corpus: articles, reviews,
and preprints dated 2020-01-01 through 2025-12-31 whose primary topic subfield is
1702 or 1707. It is not all global AI research.

Two population estimands now use identical date/type/subfield boundaries:

- Primary non-retracted:
  `from_publication_date:2020-01-01,to_publication_date:2025-12-31,primary_topic.subfield.id:1702|1707,type:article|review|preprint,is_retracted:false`
- All-work sensitivity: the same filter without `is_retracted:false`.

OpenAlex accepted the boolean filter and described `is_retracted` as a work-level
boolean in its official attribute/filter documentation. Raw responses remain
unchanged. Primary EDA denominators and the detailed sampling frame use the first
estimand; all-work aggregates quantify sensitivity.

## 2. Validated aggregate evidence

The validated run `aggregates_20261019T074133Z` completed 12/12 queries at
`2026-10-19T07:41:41Z`. Each response contained exactly the six study years,
unique keys, non-negative integer counts, and group counts summing to `meta.count`.

| Year | Non-retracted primary N | All-work N | Excluded retractions |
|---:|---:|---:|---:|
| 2020 | 125,483 | 125,868 | 385 |
| 2021 | 128,891 | 129,604 | 713 |
| 2022 | 126,183 | 127,946 | 1,763 |
| 2023 | 145,709 | 147,631 | 1,922 |
| 2024 | 178,696 | 179,144 | 448 |
| 2025 | 232,487 | 232,589 | 102 |
| **Total** | **937,449** | **942,782** | **5,333** |

Failed or malformed aggregate runs now retain a `status=failed`, `complete=false`
manifest and never produce a complete derived count artifact.

## 3. Sampling design and API evidence

Hamilton's largest-remainder method allocated the 12,000 target proportionally
from the validated non-retracted year counts:

| Year | N | n | Nominal n/N | Nominal N/n |
|---:|---:|---:|---:|---:|
| 2020 | 125,483 | 1,606 | 0.01279855 | 78.1339 |
| 2021 | 128,891 | 1,650 | 0.01280151 | 78.1158 |
| 2022 | 126,183 | 1,615 | 0.01279887 | 78.1319 |
| 2023 | 145,709 | 1,865 | 0.01279948 | 78.1282 |
| 2024 | 178,696 | 2,288 | 0.01280387 | 78.1014 |
| 2025 | 232,487 | 2,976 | 0.01280072 | 78.1206 |

OpenAlex officially documents `sample` as random and `seed` as reproducible. An
opt-in live integration test made four small requests: pages 1 and 2 of a 20-work
2025 sample, followed by exact repeats with the same seed. On 2026-10-19 it found
20 unique IDs, no missing pages, matching `meta.count`, and identical page results.

This probe demonstrates observed short-term determinism only. The API does not
document its selection algorithm sufficiently to prove equal inclusion probability,
independence, or stability after database updates. The recorded probabilities and
weights are therefore explicitly **nominal**, conditional on uniform sampling
within each year stratum.

## 4. Reliability fixes

- Work IDs used for datasets must canonicalize to `https://openalex.org/W...`;
  other OpenAlex entity prefixes are rejected.
- Corpus validation parses exact ISO publication dates, enforces inclusive date
  limits, and separately flags date/year inconsistencies.
- Primary sampled records must explicitly have `is_retracted=false` and match the
  requested year stratum.
- Sample pages must match requested `meta.count` and exact expected page length;
  short, extra, missing, malformed, or duplicate pages fail the run.
- The stratified collector checkpoints after every validated page. Resume requires
  matching plan/config hashes, seed, and page size, and the manifest must reside
  below the configured raw root. Raw/interim roots must be non-nested.
- Raw page bytes and hashes are preserved. Failed manifests record error type and
  message; completed JSONL is built only after all 12,000 unique records validate.
- Malformed abstract inverted indexes are quarantined from custom text labels with
  a recorded reason. Raw works and OpenAlex-native topic labels remain intact.

## 5. Category validation

OpenAlex-native topic membership and project-defined text categories remain
separate analytical layers. No RAG OpenAlex topic is invented. LLM, Multimodal AI,
and RAG rules are non-exhaustive lexical measurements and cannot be compared with
native aggregate counts as though they were equivalent classifiers.

The original positive audit retained its reported ambiguous and false-positive
cases. A follow-up fixed-seed audit frame added 10 random rule negatives per
category. One clear Multimodal false negative (`W4413958554`) motivated a contextual
cross-/multi-modal rule; 29 other negative candidates contained no clear target
evidence in available text, with one non-English title-only LLM case left ambiguous.
Revised pilot match counts are 55 LLM, 22 Multimodal AI, and 4 RAG. Neither reliable
recall nor exhaustive identification is claimed.

## 6. Tests and reproducibility

- Offline suite: **44 passed, 1 skipped** (the skipped test is live by default).
- Opt-in OpenAlex integration probe: **1 passed**.
- Python compilation: passed.
- Full installation, `pip check`, CLI, import, and final Git checks are performed
  in the final validation step documented in the commit handoff.

An MIT `LICENSE` now matches `pyproject.toml`. README setup/CLI/resume commands are
current, and tested dependency versions are documented. `.env`, virtual
environments, retrieved datasets, metadata artifacts, caches, models, and generated
figures remain excluded from Git.

## 7. Outstanding risks

- OpenAlex can backfill works and change topic assignments, so counts and seeded
  samples may change between retrieval dates.
- Uniform server-side sampling is an assumption, not a verified guarantee.
- The primary-subfield boundary intentionally omits applied AI assigned elsewhere.
- Missing abstracts suppress opportunities for custom matches; malformed text is
  quarantined rather than guessed.
- Pilot FWCI missingness is 100% for preprints, and affiliation missingness is
  work-type dependent; complete-case impact and collaboration analyses can be
  compositionally biased.
- Custom category audits are small and single-reviewer; a larger enriched negative
  audit and second reviewer are needed before inferential category comparisons.
- API quotas, transient failures, and disk capacity must be monitored during the
  controlled run.

## 8. Exact next commands

Install/update entry points and validate the current environment:

```bash
source .venv/bin/activate
pip install -e ".[dev]"
pytest
pip check
```

Regenerate aggregates and the plan if OpenAlex has changed since this review:

```bash
openalex-collect-aggregates \
  --output data/metadata/population_counts_pre_phase2.json
openalex-plan-sample \
  --population-counts data/metadata/population_counts_pre_phase2.json \
  --sample-size 12000 \
  --output data/metadata/phase2_sampling_plan.json
openalex-collect-stratified \
  --plan data/metadata/phase2_sampling_plan.json
```

After checking `.env`, available quota, plan counts, and disk space, start the
controlled collection explicitly:

```bash
openalex-collect-stratified \
  --plan data/metadata/phase2_sampling_plan.json \
  --execute
```

If interrupted, resume the same run without changing plan/config/seed/page size:

```bash
openalex-collect-stratified \
  --plan data/metadata/phase2_sampling_plan.json \
  --resume-manifest data/raw/openalex_stratified/stratified_<UTC>/manifest.json \
  --execute
```

## Readiness conclusion

**Yes—the repository is ready for a controlled 12,000-work Phase 2 collection.**
This means the code and methodological safeguards are ready; it does not remove
the documented sampling assumption or authorize treating custom labels as
exhaustive. The first completed stratum and its manifest should be inspected before
allowing the remaining strata to continue.
