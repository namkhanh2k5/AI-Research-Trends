# Finalization Phase 1 — OpenAlex label snapshot check

At `2026-11-01T05:16:13Z`–`05:17` UTC, a deterministic training-only audit requested **120** existing OpenAlex Work IDs: **six from each of the fourteen selected primary-topic strata (84)** and **36 outside-catalogue works**. No 2024 validation or 2025 locked-test labels were used for selection. The query used authenticated singleton `GET /works/{Work ID}` requests. Every original response byte stream, retrieval time, HTTP status, header-based credit observation and SHA-256 is retained locally under `data/analysis/finalization_p1_label_drift_20261101_v1/`; individual IDs and response bodies are not published. Read-only verification passed **120/120** response hashes and all three summary-output hashes.

| Check | Observed |
|---|---:|
| Requested / retrieved / unavailable | 120 / 120 / 0 |
| Old vs current primary-topic agreement | 120 / 120 |
| Old vs current top-three **set** agreement | 120 / 120 |
| Selected old labels changed or moved outside catalogue | 0 / 84 |
| Missing title, old vs current | 0 vs 0 |
| Missing abstract, old vs current | 24 vs 24 |
| Observed singleton credits used | 0 per response header |

The [small public summary](../../finalization_p1/label_drift_summary.json) and [aggregate transition counts](../../finalization_p1/label_drift_transitions.csv) omit work identifiers and abstracts. This is evidence of **no observed change in this bounded audit**, not proof that all OpenAlex labels are stable. The selected six-per-topic sample and 36 outside cases were deterministic and not a probability sample of every topic/version; zero changes cannot justify a global drift-rate estimate. Later OpenAlex updates may still change titles, abstracts, topic scores or primary labels. OpenAlex's [topic documentation](https://help.openalex.org/data/topics/) also notes that classification is a system output, not independently adjudicated research truth.

For integration, retain the original Phase 3 snapshot and the new retrieval snapshot separately. The new collector records `topic_snapshot_version`, source query and retrieval timestamp per work. Do not retroactively relabel the original 12,000 works from this small check. Resolve any future conflicting snapshots explicitly and perform independent human scope review before treating the fourteen topic classes as validated labels. The existing Phase 6B blind annotation guidance remains the review protocol.
