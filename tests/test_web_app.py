"""The public explorer must remain read-only and the classifier opt-in."""

from pathlib import Path

import pytest

from ai_research_trends.web.service import artifact_paths, classify, load_research, topic_brief, validate_draft


def test_manual_topic_browse_does_not_load_model(monkeypatch):
    if not artifact_paths()[0].exists():
        pytest.skip("Verified local web artifacts absent from clean clone")
    data = load_research()
    import ai_research_trends.web.service as service

    monkeypatch.setattr(service, "load_model", lambda *a, **kw: pytest.fail("model loaded"))
    brief = topic_brief(data, data.get_topics()[0]["topic_id"])
    assert brief["topic_id"] in {t["topic_id"] for t in data.get_topics()}


@pytest.mark.parametrize("title,abstract", [("", "eight words in a sufficiently long abstract content today"),
                                             ("Title", "short"), ("Title\x00", "This is a long enough abstract for testing the input validation rules clearly")])
def test_invalid_drafts(title, abstract):
    with pytest.raises(ValueError):
        validate_draft(title, abstract)


def test_no_automatic_placement():
    class Safe:
        def place_research_draft(self, *args, **kwargs):
            return {"automatic_placement": False, "requires_user_confirmation": True}

    class Unsafe:
        def place_research_draft(self, *args, **kwargs):
            return {"automatic_placement": True, "requires_user_confirmation": False}

    text = "This abstract contains enough words and characters to satisfy the draft rules today."
    assert classify(Safe(), "A title", text)["requires_user_confirmation"]
    with pytest.raises(ValueError):
        classify(Unsafe(), "A title", text)


def test_app_loads_home():
    if not artifact_paths()[0].exists():
        pytest.skip("Verified local web artifacts absent from clean clone")
    from streamlit.testing.v1 import AppTest

    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "dashboard" / "app.py"), default_timeout=30).run()
    assert not app.exception
    assert any("Explore AI" in x.value for x in app.title)


def test_every_public_page_renders_without_unwanted_inference():
    if not artifact_paths()[0].exists():
        pytest.skip("Verified local web artifacts absent from clean clone")
    from streamlit.testing.v1 import AppTest

    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "dashboard" / "app.py"), default_timeout=40).run()
    for name in ("Research Landscape", "Topic Explorer", "Classify My Research", "Paper Explorer",
                 "Methodology & Model Evaluation", "Home"):
        app.sidebar.radio[0].set_value(name).run()
        assert not app.exception, name
        expected = "Explore AI" if name == "Home" else name
        assert any(expected in heading.value for heading in app.title), name


def test_actual_local_inference_requires_confirmation():
    web, model = artifact_paths()
    if not web.exists() or not model.exists():
        pytest.skip("Private model/web artifacts absent from clean clone")
    from ai_research_trends.web.service import load_model

    result = classify(load_model(), "Interpretable computer vision for medical images",
                      "This study investigates interpretable computer vision for medical image analysis "
                      "using convolutional neural networks, segmentation and visual explanation methods.")
    assert len(result["predictions"]) == 3
    assert result["automatic_placement"] is False
    assert result["requires_user_confirmation"] is True
    assert result["status"] in {"confident_suggestion", "needs_user_confirmation", "no_confident_match"}
