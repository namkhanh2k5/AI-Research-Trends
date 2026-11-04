"""Read-only inventory of historical OpenAlex publication-location metadata."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow.dataset as ds
import pyarrow.compute as pc

from ai_research_trends.crawling.openalex_client import canonical_work_id
from ai_research_trends.crawling.verify_collection import verify_completed_collection
from ai_research_trends.crawling.verify_ml_expansion import verify as verify_expansion
from ai_research_trends.ml.validate_integrated_data import verify_run
from ai_research_trends.preprocessing.validate_tables import file_sha256
from ai_research_trends.experiments.venue_core import (
    extract_openalex_venue, normalize_source_type, source_id, valid_issns,
)


ORIGINAL_RAW = Path("data/raw/openalex_stratified/stratified_20261019T155909Z/works.jsonl")
EXPANSION_RAW = Path("data/raw/openalex_ml_expansion/ml_expansion_20261101T052506Z/works.jsonl")
ORIGINAL_PROCESSED = Path("data/processed/openalex_stratified/stratified_20261019T155909Z")
INTEGRATED = Path("data/processed/ml_topic_classification/finalization_p2_20261101_v3")
WORK_ID_PREFIX = re.compile(r'^\{"id":\s*"([^"]+)"')


def _read_allowed_original_ids() -> set[str]:
    dataset = ds.dataset(ORIGINAL_PROCESSED / "works.parquet", format="parquet")
    table = dataset.to_table(columns=["work_id"], filter=pc.field("publication_year") <= 2024)
    return set(table.column("work_id").to_pylist())


def _source_rows(work: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for location in [work.get("primary_location"), *(work.get("locations") or [])]:
        if not isinstance(location, dict) or not isinstance(location.get("source"), dict):
            continue
        src = location["source"]
        try:
            sid = source_id(src.get("id"))
        except ValueError:
            continue
        if not sid:
            continue
        issns, invalid = valid_issns(src.get("issn"))
        rows.append({"source_id": sid, "display_name": src.get("display_name"),
                     "source_type": normalize_source_type(src.get("type")),
                     "issn_l": src.get("issn_l"), "issns": json.dumps(issns),
                     "publisher": src.get("host_organization_name"),
                     "invalid_issn_count": len(invalid)})
    return rows


def collect_local_rows() -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    """Inspect only 2020–24 paper IDs; 2025 text and labels never enter the experiment."""
    verify_completed_collection(ORIGINAL_RAW.parent / "manifest.json")
    verify_expansion(EXPANSION_RAW.parent / "manifest.json")
    verify_run(INTEGRATED)
    original_ids = _read_allowed_original_ids()
    records: list[dict[str, Any]] = []
    sources: dict[str, dict[str, Any]] = {}
    inputs = {}
    for origin, path, allowed in (
        ("original_analytical_sample", ORIGINAL_RAW, original_ids),
        # The expansion manifest verifies that every record is from 2020–2023.
        # Include non-ML-eligible papers in the metadata inventory too.
        ("targeted_ml_expansion", EXPANSION_RAW, None),
    ):
        inputs[origin] = {"path": str(path), "sha256": file_sha256(path),
                          "bytes": path.stat().st_size}
        matched: set[str] = set()
        with path.open(encoding="utf-8") as stream:
            for line in stream:
                if allowed is not None:
                    prefix = WORK_ID_PREFIX.match(line)
                    if prefix is None:
                        raise ValueError("Original JSONL line does not begin with Work ID")
                    wid = canonical_work_id(prefix.group(1))
                    if wid not in allowed:
                        continue  # Do not JSON-decode sealed 2025 records.
                    work = json.loads(line)
                else:
                    work = json.loads(line)
                    wid = canonical_work_id(work["id"])
                if wid in matched:
                    if allowed is None:
                        continue  # verified expansion may repeat IDs across topic strata
                    raise ValueError(f"Duplicate work ID in {origin}: {wid}")
                matched.add(wid)
                if work.get("publication_year") not in range(2020, 2025):
                    raise ValueError("Allowed historical ID has unexpected publication year")
                item = extract_openalex_venue(work)
                item["source_record_key"] = ("original:" if origin.startswith("original") else "expansion:") + wid
                item["dataset_origin"] = origin
                item["all_source_ids"] = json.dumps(item["all_source_ids"])
                item["issns"] = json.dumps(item["issns"])
                item["warnings"] = json.dumps(item["warnings"])
                records.append(item)
                for source in _source_rows(work):
                    sid = source["source_id"]
                    if sid not in sources:
                        sources[sid] = source
        if allowed is not None and matched != allowed:
            raise ValueError(f"Historical source ID coverage mismatch: {origin}: {len(matched)} vs {len(allowed)}")
    frame = pd.DataFrame(records).sort_values("source_record_key").reset_index(drop=True)
    source_frame = pd.DataFrame(sources.values()).sort_values("source_id").reset_index(drop=True)
    if frame.source_record_key.duplicated().any():
        raise ValueError("Duplicate source record key")
    return frame, source_frame, inputs


def inventory_metrics(frame: pd.DataFrame, sources: pd.DataFrame) -> dict[str, Any]:
    def subset(part: pd.DataFrame) -> dict[str, Any]:
        return {"records": len(part), "doi": int(part.doi.notna().sum()),
                "primary_source": int(part.has_primary_source.sum()),
                "any_source": int(part.source_count.gt(0).sum()),
                "multiple_hosting_sources": int(part.source_count.gt(1).sum()),
                "resolved_journal": int((part.source_type.eq("journal") & part.source_id.notna()).sum()),
                "resolved_conference": int((part.source_type.eq("conference") & part.source_id.notna()).sum()),
                "repository_host": int(part.has_repository_host.sum()),
                "ambiguous": int(part.match_status.eq("AMBIGUOUS").sum()),
                "unmatched": int(part.match_status.eq("UNMATCHED").sum())}
    return {"overall": subset(frame),
            "unique_work_ids": int(frame.work_id.nunique()),
            "unique_dois": int(frame.doi.nunique()),
            "distinct_source_ids": int(sources.source_id.nunique()),
            "source_types": {str(k): int(v) for k, v in sources.source_type.value_counts().items()},
            "by_year": {str(k): subset(p) for k, p in frame.groupby("publication_year")},
            "by_work_type": {str(k): subset(p) for k, p in frame.groupby("work_type")},
            "by_primary_topic": {str(k): subset(p) for k, p in frame.groupby("primary_topic_id")},
            "origins": dict(Counter(frame.dataset_origin))}


def select_dois(frame: pd.DataFrame, limit: int = 500, seed: int = 20261104) -> pd.DataFrame:
    """Deterministic year × venue-completeness round robin; not population-representative."""
    if not 1 <= limit <= 1000:
        raise ValueError("Crossref pilot cap is 1,000 distinct DOI records")
    candidate = frame.loc[frame.doi.notna()].drop_duplicates("doi").copy()
    candidate["selection_stratum"] = (
        candidate.publication_year.astype(str) + ":" +
        candidate.source_id.notna().map({True: "venue_present", False: "venue_missing"})
    )
    candidate["order_hash"] = candidate.doi.map(
        lambda d: hashlib.sha256(f"{seed}:{d}".encode()).hexdigest()
    )
    groups = [part.sort_values("order_hash").to_dict("records")
              for _, part in candidate.groupby("selection_stratum", sort=True)]
    selected = []
    while len(selected) < min(limit, len(candidate)) and any(groups):
        for group in groups:
            if group and len(selected) < limit:
                selected.append(group.pop(0))
    result = pd.DataFrame(selected).drop(columns="order_hash")
    return result.sort_values(["selection_stratum", "doi"]).reset_index(drop=True)


def run_inventory(output_dir: Path, doi_limit: int = 500) -> dict[str, Any]:
    if output_dir.exists():
        raise FileExistsError(output_dir)
    frame, sources, inputs = collect_local_rows()
    output_dir.mkdir(parents=True)
    frame.to_parquet(output_dir / "openalex_work_venues.parquet", index=False)
    sources.to_parquet(output_dir / "openalex_sources.parquet", index=False)
    frame[["source_record_key", "work_id", "match_status", "warnings"]].to_parquet(
        output_dir / "venue_extraction_audit.parquet", index=False
    )
    selection = select_dois(frame, doi_limit)
    selection[["work_id", "doi", "publication_year", "selection_stratum"]].to_parquet(
        output_dir / "crossref_selection.parquet", index=False
    )
    metrics = inventory_metrics(frame, sources)
    metrics["crossref_selection"] = {"count": len(selection), "seed": 20261104,
        "design": "year x venue-present/missing round-robin; deliberately nonrepresentative"}
    (output_dir / "inventory_metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
    manifest = {"status": "complete", "stage": "offline_inventory", "inputs": inputs,
        "integrated_manifest_sha256": file_sha256(INTEGRATED / "split_manifest.json"),
        "outputs": {p.name: {"sha256": file_sha256(p), "bytes": p.stat().st_size}
                    for p in output_dir.iterdir() if p.is_file()},
        "scope": "2020-2024 only; 2025 held-out records excluded"}
    (output_dir / "inventory_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return metrics


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--doi-limit", type=int, default=500)
    args = parser.parse_args(argv)
    print(json.dumps(run_inventory(args.output_dir, args.doi_limit)["overall"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
