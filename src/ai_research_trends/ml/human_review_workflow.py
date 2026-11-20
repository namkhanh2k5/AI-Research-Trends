"""Integrity checks for the archived, never-completed blind-review package.

Independent human review was withdrawn from project scope on 2026-11-20 (see
config/final_test_2025_amendment.yaml); no rating was ever collected. These
checks remain only so historical manifests that bind the package still verify.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from ai_research_trends.preprocessing.validate_tables import file_sha256


RESPONSE_COLUMNS={"example_id","best_topic","second_plausible_topic","reviewer_note"}


def validate_blind_sheet(frame: pd.DataFrame, allowed: set[str]) -> dict:
    required={"example_id","title","abstract","randomized_topic_options"}|RESPONSE_COLUMNS
    if not required.issubset(frame.columns): raise ValueError("Blind sheet lacks response or paper fields")
    if any("openalex" in str(col).lower() or "prediction" in str(col).lower() for col in frame.columns):
        raise ValueError("Blind sheet leaks source labels or model predictions")
    if frame.example_id.duplicated().any() or frame.example_id.isna().any():
        raise ValueError("Blind example IDs must be unique")
    if frame[["best_topic","second_plausible_topic"]].notna().any().any():
        raise ValueError("Blind sheet already contains topic answers")
    orders=[]
    for value in frame.randomized_topic_options:
        # The frozen Phase 6B sheet stores human-readable options separated by
        # pipes, not a JSON array. Inspect only the displayed topic identifiers.
        options=[part.strip().split(" — ",1)[0] for part in str(value).split(" | ")]
        if len(options)!=len(allowed) or set(options)!=allowed:
            raise ValueError("Randomized options differ from frozen catalogue")
        orders.append(tuple(options))
    if len(set(orders))<2: raise ValueError("Topic option order is not varied")
    return {"valid":True,"examples":len(frame),"options":len(allowed),"distinct_orders":len(set(orders))}


def validate_package(output_dir: Path) -> dict:
    manifest=json.loads((output_dir/"manifest.json").read_text())
    if manifest.get("status")!="prepared_pending_real_human_annotation":
        raise ValueError("Unexpected review package status")
    for reviewer,entries in manifest["package_checksums"].items():
        for name in ("calibration","evaluation"):
            path=output_dir/reviewer/f"blind_{name}.csv"
            if file_sha256(path)!=entries[name]: raise ValueError("Blind package checksum changed")
        if file_sha256(output_dir/reviewer/"scope_review_form.csv")!=entries["scope_form_sha256"]:
            raise ValueError("Scope form checksum changed")
        if any((output_dir/reviewer).glob("restricted_key*")):
            raise ValueError("Restricted answer key exposed in reviewer package")
    return {"valid":True,"reviewers":2,"calibration_examples":manifest["calibration"]["examples"],
            "evaluation_examples":manifest["evaluation"]["examples"],
            "human_statistics":"not_performed"}
