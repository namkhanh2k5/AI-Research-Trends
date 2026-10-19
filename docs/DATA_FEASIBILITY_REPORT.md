# Phase 1 Data Feasibility Report

The canonical, fully tabulated report is
[`reports/data_feasibility.md`](../reports/data_feasibility.md). This document is
kept as the documentation entry point to avoid maintaining two conflicting sets
of results.

## Pre-Phase 2 finding

OpenAlex is feasible for the project under the fixed **defined AI/CV
primary-subfield corpus**: complete years 2020–2025, work types article/review/
preprint, and primary-topic subfields 1702/1707. The validated primary non-retracted
aggregation returned 937,449 works at 2026-10-19T07:41:41Z; the parallel all-work
sensitivity frame contains 942,782. The historical pilot contains 1,000 raw
and 1,000 unique works, zero duplicates, and zero boundary violations.

The principal risks are non-random analytical missingness and category
measurement. In the pilot, all 234 preprints lack FWCI, while affiliation/country
missingness is about 38% for preprints versus 21% for articles. Custom LLM,
Multimodal AI, and RAG text rules are kept separate from OpenAlex-native topic
counts; a small audit found one false-positive RAG match and several ambiguous
centrality judgments.

Raw retracted works are retained and flagged; primary estimates and detailed
sampling apply `is_retracted:false`, with all-work aggregates as sensitivity data.
The proportional year-stratified plan and checkpoint/resume collector are now
implemented. Phase 2 is ready for a controlled run subject to API-key/quota checks
and the sampling caveat in the canonical report. No Phase 2 expansion has been run.
