"""Local-only blind-review persistence; never exposes restricted answer keys."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pandas as pd

from ai_research_trends.ml.human_review_workflow import validate_package

REVIEWERS = {"reviewer_a", "reviewer_b"}
SHEETS = {"calibration", "evaluation"}


def load_blind(package: Path, reviewer: str, sheet: str) -> pd.DataFrame:
    if reviewer not in REVIEWERS or sheet not in SHEETS:
        raise ValueError("Invalid reviewer or sheet")
    validate_package(package)
    frame = pd.read_csv(package / reviewer / f"blind_{sheet}.csv").fillna("")
    if any("openalex" in c.lower() or "prediction" in c.lower() for c in frame.columns):
        raise ValueError("Review is not blind")
    return frame


def ratings_path(output_root: Path, reviewer: str, sheet: str) -> Path:
    if reviewer not in REVIEWERS or sheet not in SHEETS:
        raise ValueError("Invalid reviewer or sheet")
    return output_root / reviewer / f"ratings_{sheet}.csv"


def save_rating(output_root: Path, reviewer: str, sheet: str, blind: pd.DataFrame,
                example_id: str, best_topic: str, second: str = "", note: str = "") -> Path:
    path = ratings_path(output_root, reviewer, sheet)
    if example_id not in set(blind.example_id):
        raise ValueError("Unknown blind example")
    row = blind.loc[blind.example_id.eq(example_id)].iloc[0]
    allowed = {part.strip().split(" — ", 1)[0] for part in row.randomized_topic_options.split(" | ")}
    if best_topic not in allowed | {"NONE", "UNCLEAR"} or second not in allowed | {"", "NONE", "UNCLEAR"}:
        raise ValueError("Invalid topic selection")
    if best_topic == second:
        raise ValueError("Primary and secondary choices must differ")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        frame = pd.read_csv(path, keep_default_na=False)
        if set(frame.example_id) != set(blind.example_id):
            raise ValueError("Existing rating sheet does not match blind package")
    else:
        frame = blind[["example_id"]].copy()
        for column in ("best_topic", "second_plausible_topic", "reviewer_note"):
            frame[column] = ""
    index = frame.index[frame.example_id.eq(example_id)][0]
    frame.loc[index, ["best_topic", "second_plausible_topic", "reviewer_note"]] = [best_topic, second, note]
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, prefix=".ratings_", suffix=".csv",
                                     delete=False, encoding="utf-8") as stream:
        frame.to_csv(stream, index=False)
        stream.flush(); os.fsync(stream.fileno())
        temp = Path(stream.name)
    temp.replace(path)
    return path
