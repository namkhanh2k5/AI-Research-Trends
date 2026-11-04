"""Audit-only real Chrome walkthrough; local evidence, Git-ignored."""

from __future__ import annotations

import json
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parent
URL = "http://127.0.0.1:8501"
TITLE = "Interpretable medical image segmentation with neural networks"
ABSTRACT = ("This synthetic demonstration draft studies convolutional neural networks for "
            "medical image segmentation and evaluates visual explanations of lesion boundaries. "
            "It is not a sampled OpenAlex paper or a real reviewer submission.")


def shot(page, name):
    page.wait_for_timeout(500)
    page.screenshot(path=str(OUT / name), full_page=True)
    return {"screenshot": name, "scroll_width": page.evaluate("document.documentElement.scrollWidth"),
            "viewport_width": page.viewport_size["width"], "heading": page.locator("h1").all_text_contents()}


def nav(page, label):
    page.get_by_text(label, exact=True).first.click()
    page.wait_for_timeout(700)


def main():
    results = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path="/usr/bin/google-chrome", headless=True,
                                            args=["--no-sandbox", "--disable-dev-shm-usage"])
        page = browser.new_page(viewport={"width": 1440, "height": 900}, device_scale_factor=1)
        page.goto(URL, wait_until="domcontentloaded")
        page.get_by_text("Explore AI & Computer Vision Research").wait_for(timeout=30000)
        results.append(shot(page, "01_home_desktop.png"))
        nav(page, "Research Landscape")
        results.append(shot(page, "02_landscape_desktop.png"))
        nav(page, "Topic Explorer")
        results.append(shot(page, "03_topic_explorer_desktop.png"))
        nav(page, "Classify My Research")
        results.append(shot(page, "04_classify_initial_desktop.png"))
        page.get_by_label("Research title").fill(TITLE)
        page.get_by_label("Abstract").fill(ABSTRACT)
        page.get_by_role("button", name="Suggest topics").click()
        page.get_by_text("Status:", exact=False).wait_for(timeout=30000)
        results.append(shot(page, "05_classify_prediction_desktop.png"))
        results.append({"classify_exception": page.locator('[data-testid="stException"]').all_text_contents()})
        if page.get_by_label("Your own topic choice (you may select any catalogue topic)").count():
            page.get_by_label("Your own topic choice (you may select any catalogue topic)").click()
            page.get_by_text("Topic Modeling", exact=False).last.click()
            page.get_by_role("button", name="Confirm my selection").click()
            page.get_by_text("Your manual selection is confirmed", exact=False).wait_for(timeout=10000)
            results.append(shot(page, "06_classify_confirmed_desktop.png"))
        else:
            results.append({"06_classify_confirmed_desktop.png": "NOT CAPTURED: live KeyError blocks confirmation"})
        # Probe stale suggestion after draft edit without re-submitting.
        page.get_by_label("Research title").fill("Changed synthetic title after confirmation")
        results.append({"stale_suggestion_after_input_change": page.get_by_text(
            "Status:", exact=False).count() > 0})
        nav(page, "Paper Explorer")
        results.append(shot(page, "07_paper_explorer_desktop.png"))
        nav(page, "Methodology & Model Evaluation")
        results.append(shot(page, "08_methodology_desktop.png"))
        # Two additional viewport sizes: a real browser rendering, not AppTest.
        for width, height, label in [(1280, 800, "laptop"), (768, 1024, "tablet")]:
            page.set_viewport_size({"width": width, "height": height})
            results.append(shot(page, f"09_methodology_{label}.png"))
        mobile = browser.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=1,
                                  is_mobile=True, has_touch=True)
        mobile.goto(URL, wait_until="domcontentloaded")
        mobile.get_by_text("Explore AI & Computer Vision Research").wait_for(timeout=30000)
        results.append(shot(mobile, "10_home_mobile.png"))
        # Streamlit collapses the sidebar on narrow screens.
        toggle = mobile.get_by_role("button", name="Expand sidebar")
        if toggle.count():
            toggle.click()
        nav(mobile, "Classify My Research")
        collapse = mobile.get_by_role("button", name="Collapse sidebar")
        if collapse.count():
            collapse.click()
        results.append(shot(mobile, "11_classify_mobile.png"))
        browser.close()
    (OUT / "browser_observations.json").write_text(json.dumps(results, indent=2) + "\n")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
