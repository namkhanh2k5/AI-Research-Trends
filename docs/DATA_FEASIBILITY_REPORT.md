# Phase 1 Data Feasibility Report

The canonical, fully tabulated report is
[`reports/data_feasibility.md`](../reports/data_feasibility.md). This document is
kept as the documentation entry point to avoid maintaining two conflicting sets
of results.

## Final Phase 1 finding

OpenAlex is feasible for the project under the fixed **defined AI/CV
primary-subfield corpus**: complete years 2020–2025, work types article/review/
preprint, and primary-topic subfields 1702/1707. A live year aggregation returned
942,782 works at 2026-10-19T03:06:51Z. The deterministic pilot contains 1,000 raw
and 1,000 unique works, zero duplicates, and zero boundary violations.

The principal risks are non-random analytical missingness and category
measurement. In the pilot, all 234 preprints lack FWCI, while affiliation/country
missingness is about 38% for preprints versus 21% for articles. Custom LLM,
Multimodal AI, and RAG text rules are kept separate from OpenAlex-native topic
counts; a small audit found one false-positive RAG match and several ambiguous
centrality judgments.

Retracted works are retained and flagged in storage, excluded from primary
estimates, counted explicitly, and included in a planned sensitivity analysis.
Phase 2 is methodologically ready subject to API-key setup and implementation of
the proportional year-stratified checkpointed collector. No Phase 2 expansion has
been run.
