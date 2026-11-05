"""Application boundary: verified local data, optional verified model, no network calls."""

from __future__ import annotations

import os
import hashlib
from datetime import datetime, timezone
from pathlib import Path

from ai_research_trends.analysis.web_queries import ResearchData
from ai_research_trends.artifact_paths import application_artifacts

_APPLICATION = application_artifacts()
DEFAULT_WEB = _APPLICATION["web_data"]
DEFAULT_MODEL = _APPLICATION["model_bundle"]
DEFAULT_DISCOVERY = _APPLICATION["paper_discovery"]


def current_2025_test_notice() -> str:
    """Current disclosure status, separate from the historical frozen protocol."""
    return ("The 2025 test labels were publicly exposed, so this set is no longer "
            "an independently blind or sealed evaluation.")


def artifact_paths() -> tuple[Path, Path]:
    return (Path(os.environ.get("AI_TRENDS_WEB_DATA", DEFAULT_WEB)),
            Path(os.environ.get("AI_TRENDS_MODEL", DEFAULT_MODEL)))


def discovery_path() -> Path:
    if override := os.environ.get("AI_TRENDS_DISCOVERY_INDEX"):
        return Path(override)
    status = sync_status()
    return Path(status["index"]) if status else DEFAULT_DISCOVERY


def sync_status() -> dict | None:
    from ai_research_trends.web.sync import DEFAULT_ROOT, read_sync_status
    status = read_sync_status(Path(os.environ.get("AI_TRENDS_APPLICATION_SYNC_ROOT", DEFAULT_ROOT)))
    if status is None:
        return None
    raw_threshold = os.environ.get("AI_TRENDS_SYNC_STALE_HOURS", "48")
    try:
        threshold = float(raw_threshold)
        if not 1 <= threshold <= 8760:
            raise ValueError("Out-of-range freshness threshold")
    except ValueError:
        threshold = 48.0
    return with_freshness(status, stale_after_hours=threshold)


def with_freshness(status: dict, *, stale_after_hours: float = 48,
                   now: datetime | None = None) -> dict:
    """Describe freshness without claiming complete OpenAlex change capture."""
    if not 1 <= stale_after_hours <= 8760:
        raise ValueError("Invalid freshness threshold")
    observed = datetime.fromisoformat(status["last_success_at_utc"].replace("Z", "+00:00"))
    if observed.tzinfo is None:
        raise ValueError("Sync timestamp must be timezone-aware")
    reference = now or datetime.now(timezone.utc)
    if reference.tzinfo is None:
        raise ValueError("Reference time must be timezone-aware")
    hours = max(0.0, (reference.astimezone(timezone.utc) - observed.astimezone(timezone.utc)).total_seconds() / 3600)
    return {**status, "hours_since_success": hours, "stale": hours > stale_after_hours,
            "stale_after_hours": stale_after_hours}


def load_discovery(path: Path | None = None):
    from ai_research_trends.web.paper_discovery import PaperDiscovery

    return PaperDiscovery(path or discovery_path())


def suggestion_message(status: str) -> str:
    """Three score-strength states; never assert an automatic topic assignment."""
    messages = {
        "confident_suggestion": "The model found a stronger candidate topic. Please review and confirm it yourself.",
        "needs_user_confirmation": "Possible topics were found, but the score is insufficient for a strong suggestion. Please review the alternatives.",
        "no_confident_match": "This idea may lie outside the fourteen supported topics. You can revise the description or browse topics manually.",
    }
    if status not in messages:
        raise ValueError(f"Unknown suggestion status: {status}")
    return messages[status]


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


def draft_fingerprint(title: str, abstract: str) -> str:
    """Bind a suggestion to the normalized text actually supplied by the user."""
    if not isinstance(title, str) or not isinstance(abstract, str):
        raise ValueError("Title and abstract must be text")
    normalized = "\0".join(" ".join(value.split()) for value in (title, abstract))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def doi_url(value: str | None) -> str | None:
    """Return an HTTPS DOI resolver URL only for a plausible DOI."""
    if not isinstance(value, str) or not value.strip():
        return None
    doi = value.strip()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if doi.lower().startswith(prefix):
            doi = doi[len(prefix):]
            break
    if not doi.lower().startswith("10.") or "/" not in doi or any(c.isspace() for c in doi):
        return None
    return f"https://doi.org/{doi}"


def topic_brief(data: ResearchData, topic_id: str) -> dict:
    """Manual browsing intentionally never loads or runs the ML model."""
    return data.get_topic_brief(topic_id)


def classify(service, title: str, abstract: str) -> dict:
    title, abstract = validate_draft(title, abstract)
    result = service.place_research_draft(title, abstract, top_k=3)
    if result.get("automatic_placement") is not False or result.get("requires_user_confirmation") is not True:
        raise ValueError("Unsafe automatic-placement result")
    return result
