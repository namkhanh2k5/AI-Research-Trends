"""Bounded, training-side-only OpenAlex candidate metadata enrichment.

Singleton requests are used so every raw response has its own immutable byte
record. Selection cannot inspect evaluation reference lists.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from ai_research_trends.analysis.load_data import load_verified_tables
from ai_research_trends.crawling.openalex_client import OpenAlexClient, canonical_work_id
from ai_research_trends.env import load_project_env
from ai_research_trends.ml.candidate_pool import historical_citers
from ai_research_trends.ml.feasibility import candidate_frequency
from ai_research_trends.preprocessing.text import reconstruct_abstract
from ai_research_trends.preprocessing.validate_tables import file_sha256


def select_training_candidates(frequency: pd.Series, *, maximum: int = 1000,
                               tail_fraction: float = .1, seed: int = 20261028) -> pd.DataFrame:
    """Top historical-frequency IDs plus a seeded frequency-one audit sample."""
    if not 1 <= maximum <= 3000 or not 0 <= tail_fraction <= .5:
        raise ValueError("maximum must be 1–3000 and tail_fraction 0–0.5")
    if frequency.index.has_duplicates or frequency.lt(1).any():
        raise ValueError("Historical frequency must have unique IDs and positive counts")
    for work_id in frequency.index:
        canonical_work_id(work_id)
    n_tail = min(int(maximum * tail_fraction), int(frequency.eq(1).sum()))
    top = sorted(((str(id_), int(count)) for id_, count in frequency.items() if count > 1),
                 key=lambda item: (-item[1], item[0]))[:maximum - n_tail]
    tail = sorted(((str(id_), int(count)) for id_, count in frequency.items() if count == 1),
                  key=lambda item: hashlib.sha256(f"{seed}:{item[0]}".encode()).hexdigest())[:n_tail]
    extra: list[tuple[str, int]] = []
    if len(top) + len(tail) < maximum:
        already = {item[0] for item in top + tail}
        extra = sorted(((str(id_), int(count)) for id_, count in frequency.items()
                        if id_ not in already), key=lambda item: (-item[1], item[0]))[:
                            maximum - len(top) - len(tail)]
    return pd.DataFrame([{"work_id": item[0], "historical_citing_works": item[1],
                          "selection_group": group}
                         for group, selected in (("top_frequency", top),
                                                 ("frequency_one_audit", tail),
                                                 ("additional_ranked", extra))
                         for item in selected])


def parse_candidate_metadata(work: dict[str, Any], expected_id: str) -> dict[str, Any]:
    """Validate identity and extract only observed fields, leaving unknowns null."""
    if canonical_work_id(work.get("id")) != expected_id:
        raise ValueError("OpenAlex returned a different candidate Work ID")
    date = work.get("publication_date")
    if date is not None and (not isinstance(date, str) or pd.isna(pd.to_datetime(date, errors="coerce"))):
        raise ValueError(f"Malformed candidate publication date for {expected_id}")
    location = work.get("primary_location") or {}
    if not isinstance(location, dict):
        raise ValueError("primary_location must be object or null")
    abstract = reconstruct_abstract(work.get("abstract_inverted_index"))
    oa = work.get("open_access") or {}
    if not isinstance(oa, dict):
        raise ValueError("open_access must be object or null")
    return {"work_id": expected_id, "title": work.get("title"), "abstract": abstract,
            "publication_date": date, "publication_year": work.get("publication_year"),
            "doi": work.get("doi"), "work_type": work.get("type"),
            "is_oa": oa.get("is_oa"), "oa_status": oa.get("oa_status"),
            "landing_page_url": location.get("landing_page_url")}


def _atomic_bytes(path: Path, data: bytes) -> None:
    temporary = path.with_suffix(path.suffix + ".part")
    with temporary.open("wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(path)


def run_enrichment(*, processed_dir: Path, plan: Path, population: Path,
                   config: Path, output_dir: Path, maximum: int = 1000,
                   seed: int = 20261028, client: OpenAlexClient | None = None) -> dict:
    """Fetch a bounded candidate subset; leave incomplete evidence on failure."""
    if output_dir.exists():
        raise FileExistsError(f"Refusing to overwrite candidate enrichment: {output_dir}")
    if output_dir.resolve().is_relative_to(processed_dir.resolve()):
        raise ValueError("Enrichment cannot write inside the Phase 3 source")
    tables, _, _ = load_verified_tables(processed_dir, plan, population, config)
    works, references = tables["works"], tables["references"]
    history = historical_citers(works, references, evaluation_year=2023)
    frequency = candidate_frequency(references, history)
    selected = select_training_candidates(frequency, maximum=maximum, seed=seed)
    output_dir.mkdir(parents=True)
    raw = output_dir / "raw_responses"
    raw.mkdir()
    selected.to_csv(output_dir / "selected_training_candidates.csv", index=False)
    manifest: dict[str, Any] = {
        "status": "incomplete", "complete": False,
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "selection": "2020–2022 all historical citing-work frequency only; no evaluation reference IDs",
        "seed": seed, "maximum": maximum, "selected": len(selected),
        "source_phase3_manifest_sha256": file_sha256(processed_dir / "manifest.json"),
        "selection_sha256": file_sha256(output_dir / "selected_training_candidates.csv"),
        "responses": [], "unavailable_ids": [], "api_failures": []}
    manifest_path = output_dir / "manifest.json"
    _atomic_bytes(manifest_path, (json.dumps(manifest, indent=2) + "\n").encode())
    client = client or OpenAlexClient()
    if not client.api_key:
        raise RuntimeError("OPENALEX_API_KEY is not configured; no candidate requests made")
    rows: list[dict[str, Any]] = []
    for record in selected.itertuples(index=False):
        work_id = str(record.work_id)
        short_id = work_id.rsplit("/", 1)[-1]
        try:
            response = client.request(f"/works/{short_id}", allow_statuses=frozenset({404}))
            if response.status_code == 404:
                path = raw / f"{short_id}.http404"
                _atomic_bytes(path, response.content)
                manifest["unavailable_ids"].append({
                    "work_id": work_id, "path": str(path.relative_to(output_dir)),
                    "sha256": file_sha256(path), "bytes": path.stat().st_size,
                    "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
                    "status_code": 404})
                continue
            path = raw / f"{short_id}.json"
            _atomic_bytes(path, response.content)
            fetched_at = datetime.now(timezone.utc).isoformat()
            manifest["responses"].append({"work_id": work_id,
                                           "path": str(path.relative_to(output_dir)),
                                           "sha256": file_sha256(path), "bytes": path.stat().st_size,
                                           "retrieved_at_utc": fetched_at,
                                           "status_code": response.status_code})
            payload = response.json()
            parsed = parse_candidate_metadata(payload, work_id)
            parsed.update({"historical_citing_works": int(record.historical_citing_works),
                           "selection_group": record.selection_group,
                           "retrieved_at_utc": fetched_at})
            rows.append(parsed)
        except Exception as exc:
            manifest["api_failures"].append({"work_id": work_id,
                                             "error_type": type(exc).__name__,
                                             "message": str(exc)[:300]})
            break
        if len(rows) % 50 == 0:
            _atomic_bytes(manifest_path, (json.dumps(manifest, indent=2) + "\n").encode())
    pd.DataFrame(rows).to_csv(output_dir / "candidate_metadata.csv", index=False)
    manifest["metadata_sha256"] = file_sha256(output_dir / "candidate_metadata.csv")
    manifest["retrieved"] = len(rows)
    manifest["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    manifest["complete"] = not manifest["api_failures"] and (
        len(rows) + len(manifest["unavailable_ids"]) == len(selected))
    manifest["status"] = ("complete_with_unavailable" if manifest["unavailable_ids"] else "complete") if (
        manifest["complete"]) else "incomplete"
    _atomic_bytes(manifest_path, (json.dumps(manifest, indent=2) + "\n").encode())
    return manifest


def verify_enrichment(output_dir: Path) -> dict[str, int]:
    """Read-only check of selected IDs, extracted metadata, and every raw byte hash."""
    manifest = json.loads((output_dir / "manifest.json").read_text())
    if manifest.get("complete") is not True:
        raise ValueError("Enrichment manifest is incomplete")
    selected_path = output_dir / "selected_training_candidates.csv"
    metadata_path = output_dir / "candidate_metadata.csv"
    if file_sha256(selected_path) != manifest["selection_sha256"] or (
            file_sha256(metadata_path) != manifest["metadata_sha256"]):
        raise ValueError("Enrichment CSV checksum mismatch")
    selected = pd.read_csv(selected_path)
    metadata = pd.read_csv(metadata_path)
    returned = {item["work_id"] for item in manifest["responses"]}
    unavailable = {item["work_id"] for item in manifest["unavailable_ids"]}
    if selected.work_id.duplicated().any() or metadata.work_id.duplicated().any() or (
            set(selected.work_id) != returned | unavailable or returned & unavailable or
            set(metadata.work_id) != returned or len(selected) != manifest["selected"] or
            len(metadata) != manifest["retrieved"]):
        raise ValueError("Selected, retrieved, and unavailable candidate IDs disagree")
    for item in manifest["responses"] + manifest["unavailable_ids"]:
        path = (output_dir / item["path"]).resolve()
        if not path.is_relative_to(output_dir.resolve()) or file_sha256(path) != item["sha256"]:
            raise ValueError(f"Raw candidate response checksum/path mismatch: {item['work_id']}")
    return {"selected": len(selected), "retrieved": len(metadata),
            "unavailable": len(unavailable), "raw_responses_verified": len(returned) + len(unavailable)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Enrich a bounded training-selected Work-ID subset")
    parser.add_argument("--processed-dir", type=Path, default=Path(
        "data/processed/openalex_stratified/stratified_20261019T155909Z"))
    parser.add_argument("--plan", type=Path, default=Path("data/metadata/phase2_sampling_plan.json"))
    parser.add_argument("--population", type=Path, default=Path(
        "data/metadata/population_counts_pre_phase2.json"))
    parser.add_argument("--config", type=Path, default=Path("config/topics.yaml"))
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--maximum", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=20261028)
    parser.add_argument("--verify-only", action="store_true",
                        help="Verify an existing enrichment without API requests or writes")
    args = parser.parse_args(argv)
    if args.verify_only:
        print(json.dumps(verify_enrichment(args.output_dir)))
        return 0
    load_project_env()
    result = run_enrichment(processed_dir=args.processed_dir, plan=args.plan,
                            population=args.population, config=args.config,
                            output_dir=args.output_dir, maximum=args.maximum, seed=args.seed)
    print(json.dumps({"status": result["status"], "retrieved": result["retrieved"],
                      "selected": result["selected"], "output_dir": str(args.output_dir)}))
    return 0 if result["complete"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
