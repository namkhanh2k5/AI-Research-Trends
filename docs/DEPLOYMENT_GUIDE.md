# Deployment and release guide

Current supported deployment is **local/private localhost**, not public cloud. The GitHub repository excludes raw/processed OpenAlex data, web package, model binary, reviewer ratings and sealed 2025 test. A public deployment would need a separately approved artifact distribution and metadata/abstract rights review. Do not publish private reviewer packages or test labels to make the app run.

Release checklist:

1. Install pinned-compatible dependencies with `pip install -e ".[dev,web]"` in an isolated venv; run `pip check` and offline tests.
2. Rebuild or securely transfer the versioned web package and trusted model bundle. The local-only checksum-verified copy command and approved manifest hashes are in `docs/MODEL_AND_DATA_ARTIFACTS.md`. Verify with `openalex-build-web-data verify ...` and the model loader; `openalex-verify-final-ml ...` checks the broader experiment run, not a substitute for checking the bundle itself.
3. Point `AI_TRENDS_WEB_DATA` and `AI_TRENDS_MODEL` to absolute local paths when appropriate. Use a read-only service account, keep files outside a web-accessible static directory, bind `127.0.0.1` unless a reviewed reverse proxy/authentication is added.
4. Run `streamlit run dashboard/app.py --server.address 127.0.0.1 --server.port 8501`. Check health endpoint and all six pages. Keep the reviewer app separate and local-only.
5. Confirm the public UI labels data scope, human validation pending and sealed 2025 status; confirm no secret, `.env`, binary or raw dataset is staged for Git.
6. For a future cloud deployment, document artifact licensing, secure storage, authentication/rate limits, resource budget, reproducible build and a rollback before switching from local/private status.

The site is **not deployed to a public URL** by this phase. GitHub source availability is not equivalent to a running app. The implementation uses no OpenAlex requests at browse/inference time; it cannot auto-refresh its local data snapshot.

Phase 4.1 Chrome E2E tests cover local interactions at desktop, laptop, tablet and mobile widths. They do not establish production security, hosting rights, accessibility conformance or real-user usefulness. CI runs fixture/offline checks on a clean clone; it has no ignored model/data artifact and therefore cannot attest full end-to-end functionality. A local demo can be ready even while public deployment remains blocked by artifact rights and distribution.
