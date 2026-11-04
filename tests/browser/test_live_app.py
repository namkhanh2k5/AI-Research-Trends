"""Opt-in real-browser E2E against verified local artifacts and a running Streamlit server.

Run: AI_TRENDS_RUN_BROWSER_TESTS=1 pytest -q tests/browser/test_live_app.py
This suite never reads the sealed 2025 test or sends an OpenAlex request.
"""

from __future__ import annotations

import os
import re
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

from ai_research_trends.web.service import artifact_paths

playwright = pytest.importorskip("playwright.sync_api")

URL = os.environ.get("AI_TRENDS_BROWSER_URL", "http://127.0.0.1:8501")
TITLE = "Interpretable medical image segmentation with neural networks"
ABSTRACT = (
    "This synthetic demonstration draft studies convolutional neural networks for medical image "
    "segmentation and evaluates visual explanations of lesion boundaries. It is not a sampled "
    "OpenAlex paper or a real reviewer submission."
)


@pytest.fixture(scope="module")
def browser():
    if os.environ.get("AI_TRENDS_RUN_BROWSER_TESTS") != "1":
        pytest.skip("Set AI_TRENDS_RUN_BROWSER_TESTS=1 for local Chrome E2E")
    web, model = artifact_paths()
    if not web.exists() or not model.exists():
        pytest.skip("Verified LFS web/model artifacts not downloaded")
    with playwright.sync_playwright() as engine:
        browser = engine.chromium.launch(
            executable_path=os.environ.get("AI_TRENDS_CHROME", "/usr/bin/google-chrome"),
            headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        yield browser
        browser.close()


def navigate(page, label: str) -> None:
    page.get_by_text(label, exact=True).first.click()
    playwright.expect(page.get_by_role("heading", name=label, exact=True)).to_be_visible()


def test_real_confirmation_stale_state_and_navigation(browser):
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    page.goto(URL)
    navigate(page, "Classify My Research")
    page.get_by_label("Research title").fill(TITLE)
    page.get_by_label("Abstract").fill(ABSTRACT)
    page.get_by_role("button", name="Suggest topics").click()
    playwright.expect(page.get_by_text("Status:", exact=False)).to_be_visible()
    rendered = page.locator("main").inner_text()
    assert len(re.findall(r"(?m)^.+\(T\d+\)$", rendered)) == 3, rendered
    assert not page.locator('[data-testid="stException"]').count()

    choice = page.get_by_label("Your own topic choice (you may select any catalogue topic)")
    choice.click()
    page.get_by_text("Topic Modeling", exact=True).last.click()
    page.get_by_role("button", name="Confirm my selection").click()
    playwright.expect(page.get_by_text("Your manual selection is confirmed", exact=False)).to_be_visible()
    playwright.expect(page.get_by_role("heading", name="Topic Modeling", exact=True)).to_be_visible()

    page.get_by_label("Research title").fill("Changed synthetic title")
    page.get_by_label("Research title").press("Enter")
    playwright.expect(page.get_by_text("Status:", exact=False)).to_have_count(0)
    playwright.expect(page.get_by_text("Your manual selection is confirmed", exact=False)).to_have_count(0)
    page.get_by_label("Research title").fill(TITLE)
    page.get_by_label("Research title").press("Enter")
    playwright.expect(page.get_by_text("Status:", exact=False)).to_have_count(0)
    page.get_by_role("button", name="Suggest topics").click()
    playwright.expect(page.get_by_text("Status:", exact=False)).to_be_visible()
    page.get_by_label("Abstract").fill(ABSTRACT + " An edited sentence.")
    page.get_by_label("Research title").click()
    playwright.expect(page.get_by_text("Status:", exact=False)).to_have_count(0)
    navigate(page, "Topic Explorer")
    navigate(page, "Classify My Research")
    playwright.expect(page.get_by_text("Status:", exact=False)).to_have_count(0)
    page.close()


def test_research_pages_paper_empty_and_real_download(browser):
    page = browser.new_page(viewport={"width": 1280, "height": 800}, accept_downloads=True)
    page.goto(URL)
    navigate(page, "Research Landscape")
    for tab in ("RQ5 · References", "RQ6 · Topic labels"):
        page.get_by_role("tab", name=tab).click()
    navigate(page, "Paper Explorer")
    page.get_by_label("Year", exact=True).click()
    page.get_by_text("2024", exact=True).last.click()
    playwright.expect(page.get_by_text("matching sampled works", exact=False)).to_be_visible()
    page.get_by_label("Title keyword").fill("zzzxxyy_no_match_987")
    page.get_by_label("Title keyword").press("Enter")
    playwright.expect(page.get_by_text("No sampled works match these filters", exact=False)).to_be_visible()
    navigate(page, "Methodology & Model Evaluation")
    playwright.expect(page.get_by_text("Closed-set model comparison", exact=False)).to_be_visible()
    with page.expect_download() as download_info:
        page.get_by_role("button", name="Download academic report (PDF)").click()
    assert download_info.value.suggested_filename == "FINAL_ACADEMIC_REPORT.pdf"
    assert not page.locator('[data-testid="stException"]').count()
    page.close()


def test_no_confident_match_on_desktop(browser):
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    page.goto(URL)
    navigate(page, "Classify My Research")
    page.get_by_label("Research title").fill("A quantum archaeological anthropology study")
    page.get_by_label("Abstract").fill(
        "This synthetic draft discusses archaeological pottery, ancient temple inscriptions, "
        "and chemical composition of historical artifacts in distant settlement layers."
    )
    page.get_by_role("button", name="Suggest topics").click()
    playwright.expect(page.get_by_text("Status: no confident match", exact=False)).to_be_visible()
    playwright.expect(page.get_by_label("Your own topic choice (you may select any catalogue topic)")).to_be_visible()
    assert page.evaluate("document.documentElement.scrollWidth") <= 1440
    page.close()


def test_missing_model_reports_error_but_manual_topic_browsing_works(browser, tmp_path):
    """Run a second real Streamlit process with a deliberately absent model path."""
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    env = os.environ.copy()
    env["AI_TRENDS_MODEL"] = str(tmp_path / "deliberately_absent_model")
    env["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"
    root = Path(__file__).resolve().parents[2]
    proc = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", "dashboard/app.py", "--server.headless", "true",
         "--server.address", "127.0.0.1", "--server.port", str(port)],
        cwd=root, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        health = f"http://127.0.0.1:{port}/_stcore/health"
        for _ in range(60):
            if proc.poll() is not None:
                pytest.fail("Missing-model Streamlit process exited before health check")
            try:
                if urllib.request.urlopen(health, timeout=1).status == 200:
                    break
            except (OSError, TimeoutError):
                time.sleep(.25)
        else:
            pytest.fail("Missing-model Streamlit process did not become healthy")
        page = browser.new_page()
        page.goto(f"http://127.0.0.1:{port}")
        navigate(page, "Classify My Research")
        page.get_by_label("Research title").fill(TITLE)
        page.get_by_label("Abstract").fill(ABSTRACT)
        page.get_by_role("button", name="Suggest topics").click()
        playwright.expect(page.get_by_text("Suggestion unavailable", exact=False)).to_be_visible()
        navigate(page, "Topic Explorer")
        playwright.expect(page.get_by_text("Primary-topic sample works", exact=False)).to_be_visible()
        assert not page.locator('[data-testid="stException"]').count()
        page.close()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=10)


@pytest.mark.parametrize("width,height", [(1440, 900), (1280, 800)])
def test_desktop_viewports_have_no_document_overflow(browser, width, height):
    page = browser.new_page(viewport={"width": width, "height": height})
    page.goto(URL)
    playwright.expect(page.get_by_text("Explore AI & Computer Vision Research")).to_be_visible()
    assert page.evaluate("document.documentElement.scrollWidth") <= width
    page.close()
