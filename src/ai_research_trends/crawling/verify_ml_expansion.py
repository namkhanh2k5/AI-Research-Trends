"""Read-only verification of targeted historical ML expansion evidence."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from ai_research_trends.crawling.collect_ml_expansion import validate_page
from ai_research_trends.crawling.openalex_client import canonical_work_id, validate_sample_page
from ai_research_trends.preprocessing.validate_tables import file_sha256


def verify(manifest_path: Path) -> dict:
    manifest=json.loads(manifest_path.read_text())
    if manifest.get("status")!="complete" or manifest.get("complete") is not True:
        raise ValueError("Expansion run is incomplete")
    root=manifest_path.resolve().parent
    all_ids=[]; pages=0
    for index,stratum in enumerate(manifest["strata"]):
        expected=list(range(1,math.ceil(stratum["planned_records"]/manifest["per_page"])+1))
        recorded=[entry["page_number"] for entry in stratum["pages"]]
        if recorded!=expected: raise ValueError(f"Missing or duplicated pages in stratum {index}")
        for entry in stratum["pages"]:
            path=root/f"stratum_{index:03d}"/f"page_{entry['page_number']:03d}.json"
            if not path.is_file() or file_sha256(path)!=entry["sha256"] or path.stat().st_size!=entry["bytes"]:
                raise ValueError(f"Raw page checksum/size failure: {path}")
            envelope=validate_sample_page(json.loads(path.read_bytes()),
                requested_records=stratum["planned_records"],page_number=entry["page_number"],
                per_page=manifest["per_page"])
            ids=validate_page(envelope.results,stratum)
            if ids!=entry["work_ids"]: raise ValueError(f"Page ID sequence mismatch: {path}")
            all_ids.extend(ids);pages+=1
    if len(all_ids)!=manifest["planned_raw_records"] or len(all_ids)!=manifest["raw_records"]:
        raise ValueError("Raw record count mismatch")
    if len(set(all_ids))!=manifest["unique_collected_work_ids"]:
        raise ValueError("Unique Work ID count mismatch")
    if len(all_ids)-len(set(all_ids))!=manifest["duplicate_ids_across_strata"]:
        raise ValueError("Cross-stratum duplicate diagnostic mismatch")
    raw=root/"works.jsonl"
    interim=Path(manifest["interim_jsonl_path"])
    if raw.resolve()!=Path(manifest["raw_jsonl_path"]).resolve() or not raw.is_file() or not interim.is_file():
        raise ValueError("Missing or moved final JSONL")
    if file_sha256(raw)!=manifest["raw_jsonl_sha256"] or raw.stat().st_size!=manifest["raw_jsonl_bytes"]:
        raise ValueError("Raw JSONL checksum/size mismatch")
    if file_sha256(interim)!=manifest["interim_jsonl_sha256"] or interim.stat().st_size!=manifest["interim_jsonl_bytes"]:
        raise ValueError("Interim JSONL checksum/size mismatch")
    with raw.open() as handle:
        raw_ids=[canonical_work_id(json.loads(line)["id"]) for line in handle]
    with interim.open() as handle:
        rows=[json.loads(line) for line in handle]
    interim_ids=[canonical_work_id(row["work"]["id"]) for row in rows]
    if raw_ids!=all_ids or interim_ids!=list(dict.fromkeys(all_ids)):
        raise ValueError("JSONL Work ID order or membership differs from raw pages")
    if pages!=sum(row["expected_pages"] for row in manifest["strata"]):
        raise ValueError("Expected page count mismatch")
    return {"valid":True,"read_only":True,"manifest":str(manifest_path),
            "verified_pages":pages,"raw_records":len(all_ids),"unique_work_ids":len(set(all_ids)),
            "duplicate_ids_across_strata":len(all_ids)-len(set(all_ids)),
            "raw_sha256":file_sha256(raw),"interim_sha256":file_sha256(interim)}


def main(argv: list[str]|None=None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest",type=Path)
    args=parser.parse_args(argv)
    print(json.dumps(verify(args.manifest),indent=2))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
