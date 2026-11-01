# Final system architecture

The application is a local Streamlit/Plotly read-only explorer. Browser → `dashboard/app.py` → `ai_research_trends.web.service` → verified `ResearchData` query interface → versioned Phase 2 web package. Only the “Classify My Research” action calls `TopicPlacementService`, which verifies and loads the local frozen model bundle on demand. Manual Topic Explorer bypasses the model entirely. The reviewer UI is a **separate local-only process** (`dashboard/reviewer.py`), with blind inputs and separate reviewer-specific outputs. It is not linked or deployed from the public explorer.

| Data product | Source and scope | Consumer |
|---|---|---|
| Population publication counts | Complete OpenAlex aggregates, approved AI/CV frame | RQ1/Home/Topic Brief native-topic aggregates |
| Original sampled paper index | 12,000 detailed works | Paper Explorer, sample RQ2–RQ4 context |
| ML expansion | 2,515 targeted historical works, training only | Frozen 14-topic SVM bundle |

No normal web page calls OpenAlex or reads sealed 2025 test data. `ResearchData` checks manifest and file hashes on initialization. Model loader checks its manifest, model/config hashes and inference-code compatibility before loading the trusted local `joblib` file. Untrusted pickle/joblib input remains unsafe even if it has a checksum. Research text is rendered through Streamlit's text components, not interpolated into HTML. Inputs are size-bounded and malformed drafts fail explicitly. There is no server-side account or API-key feature.

The dashboard has six navigable pages. Figure and table labels disclose source scope; the model result includes rank, status and explicit confirmation control. The selected topic is session state only. There is no automated mutation of OpenAlex records or long-term user profile.

The final-test gate retains the frozen `allow_final_test_execution: false` and pre-read human approval checks. A project-level exclusive registry additionally records attempt start and completed receipt with protocol/model/test hashes. The registry is a local governance aid, **not** a guarantee across separate clones, manually deleted files or unauthorized copies. Human review and permission are still required.
