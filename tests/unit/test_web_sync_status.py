"""Current disclosure and sync freshness are honest and configurable."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from ai_research_trends.web import service


def test_web_freshness_and_current_test_disclosure():
    now = datetime(2026, 11, 5, 12, tzinfo=timezone.utc)
    recent = {"last_success_at_utc": (now - timedelta(hours=12)).isoformat()}
    old = {"last_success_at_utc": (now - timedelta(hours=72)).isoformat()}
    assert service.with_freshness(recent, now=now)["stale"] is False
    assert service.with_freshness(old, now=now)["stale"] is True
    assert service.with_freshness(old, now=now, stale_after_hours=96)["stale"] is False
    notice = service.current_2025_test_notice().lower()
    assert "publicly exposed" in notice and "no longer" in notice and "sealed" in notice
    active_app = Path("dashboard/app.py").read_text(encoding="utf-8").lower()
    assert "2025 ml test remains sealed" not in active_app
    assert "2025 final test remains sealed" not in active_app


def test_sync_status_reads_configurable_freshness(monkeypatch):
    now = datetime.now(timezone.utc)
    monkeypatch.setattr("ai_research_trends.web.sync.read_sync_status",
                        lambda *_: {"last_success_at_utc": (now - timedelta(hours=3)).isoformat()})
    monkeypatch.setenv("AI_TRENDS_SYNC_STALE_HOURS", "2")
    assert service.sync_status()["stale"] is True
    monkeypatch.setenv("AI_TRENDS_SYNC_STALE_HOURS", "not-a-number")
    assert service.sync_status()["stale"] is False
    with pytest.raises(ValueError, match="timezone-aware"):
        service.with_freshness({"last_success_at_utc": "2026-11-05T12:00:00"})
