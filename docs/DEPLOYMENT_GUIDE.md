# Deployment and release guide

Current supported deployment is **local/private localhost**, not public cloud. The public repository now contains retained OpenAlex research artifacts, the web package and the frozen model through Git LFS. This publication did **not** establish metadata/abstract redistribution rights, and previously published reviewer keys or 2025 labels cannot be treated as independently blind/sealed. Public hosting requires a separate rights and security review.

Release checklist:

1. Install pinned-compatible dependencies with `pip install -e ".[dev,web]"` in an isolated venv; run `pip check` and offline tests.
2. Run `git lfs pull` for required artifacts, or use the checksum-verified copy command in `docs/MODEL_AND_DATA_ARTIFACTS.md` with an approved source. Verify with `openalex-build-web-data verify ...` and the model loader; `openalex-verify-final-ml ...` checks the broader experiment run, not a substitute for checking the bundle itself.
3. Point `AI_TRENDS_WEB_DATA` and `AI_TRENDS_MODEL` to absolute local paths when appropriate. Use a read-only service account, keep files outside a web-accessible static directory, bind `127.0.0.1` unless a reviewed reverse proxy/authentication is added.
4. Run `streamlit run dashboard/app.py --server.address 127.0.0.1 --server.port 8501`. Check health endpoint and all six pages. Keep the reviewer app separate and local-only.
5. Confirm the public UI labels data scope and human validation pending. Historical reports may still describe the 2025 test as sealed at their original snapshot; its independent seal was compromised by later publication. Confirm no secret or `.env` is staged for Git.
6. For a future cloud deployment, document artifact licensing, secure storage, authentication/rate limits, resource budget, reproducible build and a rollback before switching from local/private status.

The site is **not deployed to a public URL** by this phase. GitHub source availability is not equivalent to a running app. The implementation uses no OpenAlex requests at browse/inference time; it cannot auto-refresh its local data snapshot.

Chrome E2E tests target desktop/laptop at 1440 × 900 and 1280 × 800. They do not establish production security, hosting rights, accessibility conformance or real-user usefulness. CI downloads retained LFS artifacts for offline tests, but does not run the opt-in Chrome walkthrough. A local demo can be ready while public deployment remains blocked by rights and security review.
