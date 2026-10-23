"""Read only fully verified Phase 3 tables; reject cardinality and hash drift."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from ai_research_trends.config import load_config
from ai_research_trends.crawling.plan_stratified_sample import validate_sampling_plan
from ai_research_trends.preprocessing.normalize_population import normalize_population
from ai_research_trends.preprocessing.schemas import SCHEMAS
from ai_research_trends.preprocessing.validate_tables import (
    file_sha256,
    validate_output_directory,
)


def load_verified_tables(
    processed_dir: Path, plan_path: Path, population_path: Path, config_path: Path
) -> tuple[dict[str, pd.DataFrame], dict, dict]:
    """Return validated tables, processing manifest and approved sampling plan."""
    manifest = json.loads((processed_dir / "manifest.json").read_text())
    if manifest.get("status") != "complete" or manifest.get("complete") is not True:
        raise ValueError("Phase 3 manifest is not complete")
    for name, record in manifest["inputs"].items():
        if file_sha256(Path(record["path"])) != record["sha256"]:
            raise ValueError(f"Phase 3 input hash mismatch: {name}")
    for key, path in (("plan", plan_path), ("population", population_path), ("config", config_path)):
        if file_sha256(path) != manifest["inputs"][key]["sha256"]:
            raise ValueError(f"Supplied {key} does not match the Phase 3 manifest")
    quality = processed_dir / "quality.json"
    if file_sha256(quality) != manifest["quality_json_sha256"]:
        raise ValueError("Phase 3 quality-audit hash mismatch")
    plan = json.loads(plan_path.read_text())
    population_bytes = population_path.read_bytes()
    validate_sampling_plan(plan, population_source_bytes=population_bytes)
    config = load_config(config_path)
    population_rows = normalize_population(json.loads(population_bytes), config)
    checks, _ = validate_output_directory(processed_dir, plan, population_rows, config)
    if not all(item["status"] == "PASS" for item in checks.values()):
        raise ValueError("Phase 3 processed-table validation failed")
    tables = {name: pd.read_parquet(processed_dir / f"{name}.parquet") for name in SCHEMAS}
    works = tables["works"]
    if works["work_id"].duplicated().any() or len(works) != plan["allocated_sample_size"]:
        raise ValueError("Verified work grain was lost during Pandas loading")
    return tables, manifest, plan


def safe_work_join(works: pd.DataFrame, bridge: pd.DataFrame, on: str = "work_id") -> pd.DataFrame:
    """Join a one-row-per-work bridge without allowing work-level inflation."""
    if bridge[on].duplicated().any():
        raise ValueError(f"Bridge is not unique on {on}; aggregate it before work-level join")
    joined = works.merge(bridge, on=on, how="left", validate="one_to_one")
    if len(joined) != len(works) or joined[on].nunique() != works[on].nunique():
        raise ValueError("Work-level join changed the unique-work count")
    return joined
