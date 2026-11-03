"""Application boundary: verified local data, optional verified model, no network calls."""

from __future__ import annotations

import os
from pathlib import Path

from ai_research_trends.analysis.web_queries import ResearchData

DEFAULT_WEB = Path("data/analysis/finalization_p2_web_data_20261101_v3")
DEFAULT_MODEL = Path("models/finalization_p3/topic_placement_v2")


def artifact_paths() -> tuple[Path, Path]:
    return (Path(os.environ.get("AI_TRENDS_WEB_DATA", DEFAULT_WEB)),
            Path(os.environ.get("AI_TRENDS_MODEL", DEFAULT_MODEL)))


def load_research(path: Path | None = None) -> ResearchData:
    web, _ = artifact_paths()
    return ResearchData(path or web)


def load_model(model_path: Path | None = None, web_path: Path | None = None):
    from ai_research_trends.ml.final_inference import TopicPlacementService

    web, model = artifact_paths()
    return TopicPlacementService(model_path or model, web_path or web)


def validate_draft(title: str, abstract: str) -> tuple[str, str]:
    if not isinstance(title, str) or not isinstance(abstract, str):
        raise ValueError("Title and abstract must be text")
    title, abstract = title.strip(), abstract.strip()
    if not title or len(title) > 500:
        raise ValueError("Title must contain 1–500 characters")
    if len(abstract) < 50 or len(abstract.split()) < 8 or len(abstract) > 20000:
        raise ValueError("Abstract must contain 50–20,000 characters and at least 8 words")
    if "\x00" in title + abstract:
        raise ValueError("NUL characters are not allowed")
    return title, abstract


def topic_brief(data: ResearchData, topic_id: str) -> dict:
    """Manual browsing intentionally never loads or runs the ML model."""
    return data.get_topic_brief(topic_id)


def classify(service, title: str, abstract: str) -> dict:
    title, abstract = validate_draft(title, abstract)
    result = service.place_research_draft(title, abstract, top_k=3)
    if result.get("automatic_placement") is not False or result.get("requires_user_confirmation") is not True:
        raise ValueError("Unsafe automatic-placement result")
    return result
