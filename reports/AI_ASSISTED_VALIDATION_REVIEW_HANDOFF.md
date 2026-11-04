# Review handoff — AI-assisted topic/publisher experiment

## Branch and private run

- Branch: `experiment/ai-assisted-topic-publisher-validation`.
- Base: `b4b202d620718669a9842d95bb7a95c0c1e8dc50` (`experiment/rq7-independent-metadata-validation`).
- Final local run: `data/analysis/ai_assisted_validation/ai_assisted_20261104_v2/` (Git-ignored). The previous v1 run is preserved; v2 changes exactly two blind topic decisions after full-abstract re-review and makes **zero** additional external requests.
- v2 manifest SHA-256: `8e3001d0d3e8bd63b5a99b6aa43d24ca5f234d54cc346649028f1f147b64a608`.
- AI provenance: OpenAI ChatGPT Codex assistant; exact backend model/version unavailable. Prompt protocol `ai-validation-v2-full-abstract-review`. This is **one AI assessor**, not human or inter-model agreement.

## Source and output identity

| Artifact | SHA-256 / result |
|---|---|
| Frozen Catalogue B YAML | `e4b34974e2f8a6b563f29ab69ab86675de78ee9fcfbcb1f0258e7fcbd01fdda9` |
| Official-topic metadata snapshot | `024f9f13db713534fcc662ff95f477299c8cf939ca200565b2e88e13371ddd86` |
| Blind calibration CSV | `bd803f2b2c69120ff07d442c874a77a6968691ec54f28926b50b20614990a05a` |
| Blind evaluation CSV | `23a7aba6674cb1edfaf5fc8bb75400f0593de2197020fb6fc33dbf3dde66bd29` |
| Original RQ7.1 publisher sheet | `0c078c617ced7c0d58969aae212e639c83a4885d428bd2d2ddee1fa35f3df943` |
| v2 topic frozen manifest | `5b9c8f786eeb0318b6b2b5bb9d07a423c639a87bfc7d26df09e258a6874cdd60` |
| v2 calibration AI Parquet | `8c13e14642809ff23d55a73b11539734b420cb4fd890999d2073e6dc694c2222` |
| v2 evaluation AI Parquet | `ad1c608de27b6b38f9669ac4a0c17ced65daa4c4229e1eef2077944cd9fbd035` |
| v2 publisher frozen manifest | `4c899f4b15d4c2651ef477c3b5470c8fcc5a90c17e55b881d908cd6d59831950` |
| v2 publisher AI Parquet | `77d658cc0c4ce6cce96f5f1d235ce913250cf17245ef84621a7b81f57d1280df` |

The private manifests also record scope/decision TSV hashes, source-page response hashes, URLs and retrieved timestamps. Do not publish or copy those files to GitHub. Source preservation: original Phase 2, Phase 3, Phase 4, RQ6, RQ7, RQ7.1, the frozen model and the web package all passed read-only integrity checks. No genuine reviewer package was edited.

## Counts, requests and status

- Topic-scope definitions: 14/14; calibration: 40/40; evaluation: 100/100; unique IDs, no missing decisions.
- Evaluation judgments: 46 catalogue, 52 `NONE`, two `UNCLEAR`, 22 plausible secondary topics. Human accuracy/agreement: `NOT VERIFIED`.
- Publisher cases: 30/30 inspected; six source-backed correct, three source-backed acceptable aliases, zero proven incorrect, 12 ambiguous, four insufficient, five access blocked. Human adjudication: 0/30.
- Collector: 30 DOI GET attempts, 74 recorded redirect-inclusive HTTP transactions (budget 120). Four additional exploratory direct GET attempts; five web-search calls/20 queries; underlying browser request count unavailable.
- Frozen 2025 gate: `allow_final_test_execution: false`; 2025 labels/predictions **not accessed**. `HUMAN_TOPIC_VALIDATION = PENDING`; `HUMAN_PUBLISHER_ADJUDICATION = PENDING`.

## Exact local verification commands

Run from the repository root in the existing `.venv`:

```bash
.venv/bin/python -m ai_research_trends.experiments.ai_validation verify-run --run data/analysis/ai_assisted_validation/ai_assisted_20261104_v2
.venv/bin/python -m ai_research_trends.ml.human_review_workflow verify data/analysis/finalization_p2_human_review_20261101_v1
.venv/bin/python -m ai_research_trends.experiments.dual_source.validation_pipeline verify --run data/analysis/rq7_quality_validation/rq7_1_20261104_v2
.venv/bin/python -m pytest -q -ra -o addopts=''
.venv/bin/python -m pip check
```

`openalex-ai-validate --help` is available after installing the updated editable package with `pip install -e '.[dev]'`. The private record-level run is **not in GitHub**; a clean clone can run the offline unit tests but cannot reverify these 140+30 local assessments without the local ignored inputs. Exact AI inference cannot be replayed bit-for-bit because its backend version/configuration is not available; the frozen decisions and hashes can be checked.

Reported validation: 283 passed, nine skipped, no failed tests; pip check clean. Read-only experiment verifier: PASS for six frozen artifacts and source package. See the [main report](AI_ASSISTED_TOPIC_PUBLISHER_VALIDATION_FINAL_REPORT.md) and four aggregate-safe experiment reports for interpretation and unresolved risks.
