# Desktop browser validation notes

The supported website target is desktop/laptop: **1440 × 900** and **1280 × 800**.
The opt-in Chrome/Playwright suite checks the real Streamlit navigation,
classification/confirmation, Paper Explorer, report download, missing-model
behavior, and document-level horizontal overflow at those two viewport sizes.
These checks are browser automation, not a human usability or accessibility
assessment. They do not establish cross-browser behavior.

The earlier independent audit inspected historical desktop and narrow-screen
captures and recorded its findings in the accompanying pre-remediation reports.
Those disposable screenshot collections and the one-off browser probe were
removed from the current repository; **no screenshots are retained here as
current visual evidence**. The two real Chrome captures used by the academic
report and presentation remain under `deliverables/presentation/figures/`.

To repeat the supported desktop check, start the verified local app on
`127.0.0.1:8501` and run:

```bash
AI_TRENDS_RUN_BROWSER_TESTS=1 pytest -q tests/browser/test_live_app.py
```

The suite no longer writes screenshots into tracked research directories.
If a new visual review is needed, capture images in an external temporary
directory and document the exact app revision and browser version.
