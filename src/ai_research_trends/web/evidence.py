"""Small, published aggregate-only evidence contract for the research UI."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = ROOT / "reports/FINALIZATION_P4_RESEARCH_EVIDENCE.json"


def load_published_evidence(path: Path = EVIDENCE) -> dict:
    evidence = json.loads(path.read_text(encoding="utf-8"))
    expected = {"model_comparison", "open_set", "reference_context", "rq6", "final_test_2025"}
    if not expected.issubset(evidence):
        raise ValueError(f"Published evidence missing: {sorted(expected - set(evidence))}")
    final = evidence["final_test_2025"]
    if final.get("year") != 2025 or evidence["open_set"].get("final_2025_test") != "EVALUATED_ONCE":
        raise ValueError("Published evidence must record the single 2025 test run")
    if not final.get("authorization"):
        raise ValueError("Published 2025 result must name its protocol amendment")
    return evidence


def verify_available_sources(evidence: dict, root: Path = ROOT) -> dict[str, bool]:
    """Check local originals when present; aggregates only, never work-level rows."""
    results = {}
    for name in ("model_comparison", "open_set", "reference_context", "rq6", "final_test_2025"):
        item = evidence[name]
        source = root / item["source"]
        if source.is_file():
            actual = hashlib.sha256(source.read_bytes()).hexdigest()
            if actual != item["source_sha256"]:
                raise ValueError(f"Published evidence source checksum mismatch: {name}")
            results[name] = True
        else:
            results[name] = False
    return results
