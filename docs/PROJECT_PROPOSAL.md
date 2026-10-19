# Project Proposal

## Title

AI Research Trends & Scientific Impact: A Bibliometric and Machine Learning
Analysis Using OpenAlex

## Motivation

AI research grew rapidly during 2020–2025, but raw publication and citation
totals conflate topic growth, database coverage, publication age, field citation
culture, and document type. This project builds a reproducible OpenAlex corpus and
uses transparent bibliometric methods to distinguish those effects as far as the
available observational data allow.

## Objectives

1. Describe topic evolution over six complete years using population-level API
   aggregates where the query supports a complete result.
2. Compare impact across AI areas using raw counts only descriptively and
   field/time-normalized metrics for inference.
3. estimate the association between OA status and impact while controlling for
   observable confounders; do not interpret it causally.
4. construct institution and country collaboration networks without multiplying
   the work-level denominator.
5. leave an auditable trail from HTTP response to analytical table and figure.

## Scope

The initial population frame is publication dates 2020-01-01 through 2025-12-31,
types article/review/preprint, and primary-topic subfields Artificial Intelligence
(1702) or Computer Vision and Pattern Recognition (1707). It is a focused AI frame,
not a claim to cover every application of AI in every discipline. A 2026 YTD
snapshot may be produced later, but never merged into complete-year growth rates.

Detailed targets are 1,000–2,000 works for the pilot, 10,000–15,000 for the
intermediate run, and 20,000–30,000 for the final analytical sample.

The unit of analysis is one unique scholarly work identified by its canonical
OpenAlex Work ID. Authors, institutions, countries, topics, and references are
multi-valued relationships to that unit; exploding them never changes the
work-level denominator. OpenAlex is the primary bibliographic source, and its raw
records and query provenance are retained so source limitations remain auditable.

## Deliverables by phase

- Phases 1–3: design documents, live-validated taxonomy, API collector, immutable
  raw responses, manifests/checksums, normalized Parquet tables, and quality report.
- Phase 4: EDA and statistical testing on actual retrieved data only.
- Phase 5: TF-IDF logistic-regression/SVM topic baselines with leakage-safe splits;
  optional exploratory clustering.
- Phase 6: optional Streamlit/Plotly dashboard and final reproducibility package.

## Success criteria

- no silent truncation;
- every work deduplicated by canonical OpenAlex ID;
- population estimates never derived from quota-balanced data without weights;
- single-label and overlapping topic results labeled separately;
- multi-valued relationships modeled as bridges, not a duplicated wide work table;
- exclusions, missingness, classifier validation, and API changes reported;
- tests pass from a clean environment using the documented commands.

## Planned EDA

Phase 4 will visualize retrieval and missingness, annual population counts,
single-label primary-topic composition, overlapping category membership, FWCI and
raw-citation distributions, OA-status comparisons, and institution/country
collaboration networks. Estimates based on the detailed sample will carry the
appropriate design weights and denominators. Every figure must identify whether
it is a population aggregate or a sample result.

## Planned machine learning

Phase 5 will start with interpretable TF-IDF plus logistic-regression and linear-SVM
baselines for text category classification. Splits will precede feature fitting and
account for time and duplicate/related versions to prevent leakage. Optional
clustering is exploratory, not a validated taxonomy. Evaluation will include
per-class precision, recall, F1, confusion matrices, and simple baselines.

## Risks

Taxonomy/model drift, API budget limits, sparse abstracts, affiliation and country
missingness, citation-window imbalance, selection bias, preprint/article merging,
and multi-membership counting are primary threats. The collection manifest and
quality report are part of the scientific output, not incidental logs.
