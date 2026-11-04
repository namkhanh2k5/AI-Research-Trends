"""Deterministic, provenance-preserving OpenAlex/Crossref venue integration."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import pandas as pd

from ai_research_trends.experiments.venue_core import resolve_venue
from ai_research_trends.experiments.venue_enrichment import read_crossref_records
from ai_research_trends.preprocessing.validate_tables import file_sha256


def _decode_crossref(row: dict) -> dict:
    for key in ("issns", "invalid_issns", "event", "update_types", "relations"):
        if key in row and isinstance(row[key], str):
            row[key] = json.loads(row[key])
    return row


def paired_provider_gains(before: pd.DataFrame, after: pd.DataFrame) -> dict[str, int]:
    """Require identical row ordering before computing paired field gains."""
    if len(before) != len(after) or before.work_id.tolist() != after.work_id.tolist() or before.doi.tolist() != after.doi.tolist():
        raise ValueError("Before/after source-record cohort is misaligned")
    return {"source_api_publisher_recovered": int((before.openalex_publisher.isna().to_numpy() &
                after.openalex_publisher.notna().to_numpy()).sum()),
            "crossref_publisher_available_where_local_missing": int((before.openalex_publisher.isna().to_numpy() &
                after.crossref_publisher.notna().to_numpy()).sum())}


def integrate(inventory_dir: Path) -> dict:
    local_path = inventory_dir / "openalex_work_venues.parquet"
    manifest = json.loads((inventory_dir / "inventory_manifest.json").read_text())
    if file_sha256(local_path) != manifest["outputs"][local_path.name]["sha256"]:
        raise ValueError("Inventory source checksum mismatch")
    local = pd.read_parquet(local_path)
    cross_dir = inventory_dir / "crossref"
    cross = read_crossref_records(cross_dir)
    if not cross.empty and cross.doi.duplicated().any():
        raise ValueError("Duplicate Crossref DOI response")
    by_doi = {row["doi"]: _decode_crossref(row) for row in cross.to_dict("records")}
    if not cross.empty:
        cross.to_parquet(inventory_dir / "crossref_records.parquet", index=False)
    source_updates = {}
    source_manifest = inventory_dir / "openalex_sources_api" / "openalex_source_request_manifest.json"
    if source_manifest.is_file():
        for entry in json.loads(source_manifest.read_text())["requests"]:
            raw = source_manifest.parent / entry["raw_path"]
            if file_sha256(raw) != entry["sha256"]:
                raise ValueError("OpenAlex Source response checksum mismatch")
            if entry["status_code"] == 200:
                payload = json.loads(raw.read_bytes())
                if payload.get("id") != entry["identifier"]:
                    raise ValueError("OpenAlex Source response ID mismatch")
                source_updates[entry["identifier"]] = payload
    if source_updates:
        source_table = pd.read_parquet(inventory_dir / "openalex_sources.parquet")
        enriched_source_rows = []
        for record in source_table.to_dict("records"):
            source = source_updates.get(record["source_id"])
            enriched_source_rows.append({**record,
                "api_display_name": source.get("display_name") if source else None,
                "api_type": source.get("type") if source else None,
                "api_publisher": source.get("host_organization_name") if source else None,
                "api_issn_l": source.get("issn_l") if source else None,
                "api_issns": json.dumps(source.get("issn") or []) if source else None,
                "source_api_fetched": bool(source)})
        pd.DataFrame(enriched_source_rows).to_parquet(
            inventory_dir / "openalex_sources_enriched.parquet", index=False)
    # Baseline and enriched conditions use exactly the same selected DOI cohort.
    selected = pd.read_parquet(inventory_dir / "crossref_selection.parquet")
    selected_dois = set(selected.doi)
    rows = []
    before_rows = []
    for record in local.to_dict("records"):
        for key in ("issns", "warnings", "all_source_ids"):
            record[key] = json.loads(record[key])
        before = resolve_venue(record)
        if record["doi"] in selected_dois:
            before_rows.append(before)
        updated = dict(record)
        src = source_updates.get(record.get("source_id"))
        if src:
            if not updated.get("publisher"):
                updated["publisher"] = src.get("host_organization_name")
            if not updated.get("source_name"):
                updated["source_name"] = src.get("display_name")
            if not updated.get("issns"):
                updated["issns"] = src.get("issn") or []
            if not updated.get("issn_l"):
                updated["issn_l"] = src.get("issn_l")
        resolved = resolve_venue(updated, by_doi.get(record["doi"]))
        resolved["source_record_key"] = record["source_record_key"]
        resolved["source_enriched_from_api"] = bool(src)
        resolved["crossref_match"] = record["doi"] in by_doi
        rows.append(resolved)
    frame = pd.DataFrame(rows).sort_values("source_record_key").reset_index(drop=True)
    # Preserve every source-record decision, including duplicate Work IDs.
    frame.to_parquet(inventory_dir / "venue_conflict_audit.parquet", index=False)
    priority = {"EXACT_IDENTIFIER_MATCH": 0, "VERIFIED_BIBLIOGRAPHIC_MATCH": 1,
                "AMBIGUOUS": 2, "CONFLICT": 3, "UNMATCHED": 4}
    frame["resolution_rank"] = frame.identity_status.map(priority)
    frame["origin_rank"] = frame.dataset_origin.ne("original_analytical_sample").astype(int)
    links = frame.sort_values(["work_id", "resolution_rank", "origin_rank", "source_record_key"])
    duplicate_work_ids = int(links.work_id.duplicated().sum())
    links = links.drop_duplicates("work_id", keep="first").sort_values("work_id")
    links = links.rename(columns={"identity_status": "match_status", "openalex_source_id": "source_id"})
    links["link_type"] = "published_venue"  # unmatched rows still have null venue ID
    links.to_parquet(inventory_dir / "paper_venue_links.parquet", index=False)
    venues = []
    for vid, part in links.loc[links.canonical_venue_id.notna()].groupby("canonical_venue_id", sort=True):
        names = sorted({str(v) for v in part.display_name.dropna() if str(v).strip()})
        types = sorted(set(part.venue_type))
        issns = sorted(set().union(*(set(v or []) for v in part.issns)))
        venues.append({"canonical_venue_id": vid, "display_name": names[0] if names else None,
                       "venue_type": types[0] if len(types) == 1 else "ambiguous",
                       "openalex_source_id": part.source_id.dropna().iloc[0] if part.source_id.notna().any() else None,
                       "issns": json.dumps(issns), "issn_l": part.issn_l.dropna().iloc[0] if part.issn_l.notna().any() else None,
                       "dblp_venue_id": None,
                       "publisher": part.openalex_publisher.dropna().iloc[0] if part.openalex_publisher.notna().any() else (
                           part.crossref_publisher.dropna().iloc[0] if part.crossref_publisher.notna().any() else None),
                       "aliases": json.dumps(names[1:], ensure_ascii=False),
                       "identity_status": "EXACT_IDENTIFIER_MATCH",
                       "ambiguity_flag": len(types) != 1 or len(names) > 1,
                       "sources_observed": json.dumps(sorted(set().union(*(set(v or []) for v in part.provider_provenance))))})
    canonical = pd.DataFrame(venues).sort_values("canonical_venue_id")
    canonical.to_parquet(inventory_dir / "canonical_venues.parquet", index=False)
    before = pd.DataFrame(before_rows)
    after = frame.loc[frame.doi.isin(selected_dois)].reset_index(drop=True)
    if len(before) != len(after):
        raise ValueError("Before/after cohort denominator changed")
    response_status = {}
    cross_manifest = cross_dir / "crossref_request_manifest.json"
    if cross_manifest.is_file():
        response_status = {item["identifier"]: item["status_code"]
            for item in json.loads(cross_manifest.read_text())["requests"]}
    cross_audit = pd.DataFrame({"source_record_key": after.source_record_key.to_numpy(),
        "work_id": after.work_id.to_numpy(), "doi": after.doi.to_numpy(),
        "crossref_http_status": [response_status.get(doi) for doi in after.doi],
        "crossref_parsed_match": after.crossref_match.to_numpy(),
        "before_venue_id": before.canonical_venue_id.to_numpy(),
        "after_venue_id": after.canonical_venue_id.to_numpy(),
        "before_publisher_missing": (before.openalex_publisher.isna() & before.crossref_publisher.isna()).to_numpy(),
        "after_publisher_missing": (after.openalex_publisher.isna() & after.crossref_publisher.isna()).to_numpy(),
        "publication_year_conflict": after.publication_year_conflict.to_numpy(),
        "identity_status": after.identity_status.to_numpy()})
    cross_audit.to_parquet(inventory_dir / "crossref_enrichment_audit.parquet", index=False)
    def summary(part: pd.DataFrame) -> dict:
        return {"records": len(part), "resolved_identifier": int(part.canonical_venue_id.notna().sum()),
                "rankable_journal_or_conference": int((part.canonical_venue_id.notna() &
                    part.venue_type.isin(["journal", "conference"])).sum()),
                "missing_name": int(part.display_name.isna().sum()),
                "missing_publisher_both_providers": int((part.openalex_publisher.isna() &
                    part.crossref_publisher.isna()).sum()),
                "missing_issn": int(part.issns.map(len).eq(0).sum()),
                "ambiguous_or_conflict": int(part.identity_status.isin(["AMBIGUOUS", "CONFLICT"]).sum())}
    gains = paired_provider_gains(before, after)
    metrics = {"selected_cohort": len(before), "crossref_successful_distinct_dois": len(cross),
               "openalex_sources_fetched": len(source_updates),
               "before": summary(before), "after": summary(after),
               **gains,
               "identity_conflicts": int(after.identity_status.eq("CONFLICT").sum()),
               "issn_conflicts": int(after.issn_conflict.sum()),
               "type_conflicts": int(after.type_conflict.sum()),
               "publication_year_conflicts": int(after.publication_year_conflict.sum()),
               "duplicate_work_id_records_resolved": duplicate_work_ids,
               "all_historical_links": len(links), "canonical_venues": len(canonical),
               "venue_types": dict(Counter(canonical.venue_type)),
               "correctness_status": "NOT VERIFIED: no independent manual venue review"}
    (inventory_dir / "integration_metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
    return metrics


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    print(json.dumps(integrate(args.inventory_dir), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
