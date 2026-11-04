"""Separate bounded retraction-status audit; never changes the approved corpus."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

from ai_research_trends.crawling.openalex_client import OpenAlexClient, canonical_work_id
from ai_research_trends.experiments.venue_core import normalize_doi, retraction_comparison
from ai_research_trends.experiments.venue_enrichment import (
    CrossrefCollector, atomic_bytes, atomic_manifest, read_crossref_records, utc_now,
)
from ai_research_trends.preprocessing.validate_tables import file_sha256


FILTER = ("from_publication_date:2020-01-01,to_publication_date:2024-12-31,"
          "primary_topic.subfield.id:1702|1707,type:article|review|preprint,is_retracted:true")


def collect_retractions(directory: Path, *, sample_size: int = 100, seed: int = 20261104) -> dict:
    if not 1 <= sample_size <= 100:
        raise ValueError("This single-page retraction pilot is capped at 100 works")
    if directory.exists():
        raise FileExistsError(directory)
    load_dotenv()
    client = OpenAlexClient()
    if not client.api_key:
        raise RuntimeError("OpenAlex API key is not configured")
    params = {"filter": FILTER, "sample": sample_size, "seed": seed, "per_page": sample_size}
    response = client.request("works", params)
    payload = response.json()
    results = payload.get("results")
    if not isinstance(results, list) or len(results) != sample_size:
        raise ValueError("Retraction response did not return requested sample size")
    ids = set()
    for work in results:
        wid = canonical_work_id(work["id"])
        if wid in ids:
            raise ValueError("Retraction sample has duplicate Work ID")
        ids.add(wid)
        if work.get("is_retracted") is not True:
            raise ValueError("Retraction sample contains a non-retracted work")
        if not ("2020-01-01" <= work.get("publication_date", "") <= "2024-12-31"):
            raise ValueError("Retraction sample has out-of-range date")
        if work.get("type") not in {"article", "review", "preprint"}:
            raise ValueError("Retraction sample has out-of-scope work type")
        sub = (((work.get("primary_topic") or {}).get("subfield") or {}).get("id") or "").rsplit("/", 1)[-1]
        if sub not in {"1702", "1707"}:
            raise ValueError("Retraction sample has out-of-scope subfield")
    directory.mkdir(parents=True)
    raw = directory / "openalex_retracted_sample.json"
    atomic_bytes(raw, response.content)
    dois = []
    for work in results:
        try:
            doi = normalize_doi(work.get("doi"))
        except ValueError:
            doi = None
        if doi:
            dois.append(doi)
    manifest = {"status": "complete", "retrieved_at_utc": utc_now(),
                "query": params, "endpoint": "https://api.openalex.org/works",
                "sampling_note": "OpenAlex seeded sample; convenience audit, not retraction prevalence estimate",
                "returned_records": len(results), "unique_work_ids": len(ids),
                "doi_count": len(set(dois)), "raw_path": str(raw),
                "raw_sha256": file_sha256(raw), "raw_bytes": raw.stat().st_size,
                "rate_limit_remaining": response.headers.get("X-RateLimit-Remaining"),
                "credits_used": response.headers.get("X-RateLimit-Credits-Used")}
    atomic_manifest(directory / "openalex_retraction_manifest.json", manifest)
    return manifest


def compare_retractions(directory: Path, *, crossref_cap: int = 110,
                        execute_crossref: bool = False) -> dict:
    manifest = json.loads((directory / "openalex_retraction_manifest.json").read_text())
    raw = Path(manifest["raw_path"])
    if file_sha256(raw) != manifest["raw_sha256"]:
        raise ValueError("Retraction source checksum mismatch")
    works = json.loads(raw.read_bytes())["results"]
    dois = []
    for work in works:
        try:
            doi = normalize_doi(work.get("doi"))
        except ValueError:
            doi = None
        if doi:
            dois.append(doi)
    dois = sorted(set(dois))
    if len(dois) > crossref_cap:
        raise ValueError("Retraction DOI count exceeds Crossref request cap")
    cross_dir = directory / "crossref_retractions"
    if execute_crossref:
        CrossrefCollector().collect(dois, cross_dir, cap=crossref_cap)
    cross = read_crossref_records(cross_dir)
    by_doi = cross.set_index("doi").to_dict("index") if not cross.empty else {}
    rows = []
    for work in works:
        try:
            doi = normalize_doi(work.get("doi"))
        except ValueError:
            doi = None
        parsed = by_doi.get(doi)
        if parsed:
            parsed["crossref_retraction_evidence"] = bool(parsed["crossref_retraction_evidence"])
            parsed["update_types"] = json.loads(parsed["update_types"])
        rows.append({"work_id": canonical_work_id(work["id"]), "doi": doi,
                     "publication_year": work.get("publication_year"),
                     **retraction_comparison(True, parsed)})
    frame = pd.DataFrame(rows)
    frame["crossref_update_type"] = frame.crossref_update_type.map(json.dumps)
    frame.to_parquet(directory / "retraction_comparison.parquet", index=False)
    return {"records": len(frame), "doi_records": int(frame.doi.notna().sum()),
            "crossref_metadata_available": sum(doi in by_doi for doi in frame.doi),
            "crossref_explicit_retraction_evidence": int(frame.crossref_retraction_evidence.eq(True).sum()),
            "without_explicit_crossref_retraction_evidence": int(frame.status_unknown.sum()),
            "interpretation": "Missing Crossref update evidence is not proof of non-retraction"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--sample-size", type=int, default=100)
    parser.add_argument("--crossref-cap", type=int, default=110)
    parser.add_argument("--execute-openalex", action="store_true")
    parser.add_argument("--execute-crossref", action="store_true")
    args = parser.parse_args(argv)
    if args.execute_openalex:
        print(json.dumps(collect_retractions(args.output_dir, sample_size=args.sample_size), indent=2))
    if args.execute_crossref:
        print(json.dumps(compare_retractions(args.output_dir, crossref_cap=args.crossref_cap,
                                            execute_crossref=True), indent=2))
    if not args.execute_openalex and not args.execute_crossref:
        print(json.dumps({"filter": FILTER, "sample_size": args.sample_size,
                          "crossref_cap": args.crossref_cap, "output_dir": str(args.output_dir),
                          "api_requests_started": 0}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
