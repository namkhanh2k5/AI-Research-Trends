# Deployment and release guide

Current supported deployment is **local/private localhost**, not public cloud. The GitHub repository excludes raw/processed OpenAlex data, web package, model binary, reviewer ratings and sealed 2025 test. A public deployment would need a separately approved artifact distribution and metadata/abstract rights review. Do not publish private reviewer packages or test labels to make the app run.

Release checklist:

1. Install pinned-compatible dependencies with `pip install -e ".[dev,web]"` in an isolated venv; run `pip check` and offline tests.
2. Rebuild or securely transfer the versioned web package and trusted model bundle. Verify with `openalex-build-web-data verify ...` and `openalex-verify-final-ml ...`; inspect recorded SHA-256 values.
3. Point `AI_TRENDS_WEB_DATA` and `AI_TRENDS_MODEL` to absolute local paths when appropriate. Use a read-only service account, keep files outside a web-accessible static directory, bind `127.0.0.1` unless a reviewed reverse proxy/authentication is added.
4. Run `streamlit run dashboard/app.py --server.address 127.0.0.1 --server.port 8501`. Check health endpoint and all six pages. Keep the reviewer app separate and local-only.
5. Confirm the public UI labels data scope, human validation pending and sealed 2025 status; confirm no secret, `.env`, binary or raw dataset is staged for Git.
6. For a future cloud deployment, document artifact licensing, secure storage, authentication/rate limits, resource budget, reproducible build and a rollback before switching from local/private status.

The site is **not deployed to a public URL** by this phase. GitHub source availability is not equivalent to a running app. The implementation uses no OpenAlex requests at browse/inference time; it cannot auto-refresh its local data snapshot.
