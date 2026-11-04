"""Hard-budgeted, resumable provider requests with immutable raw-response evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import pandas as pd
import requests
from dotenv import load_dotenv

from ai_research_trends.crawling.openalex_client import OpenAlexClient
from ai_research_trends.experiments.venue_core import parse_crossref
from ai_research_trends.preprocessing.validate_tables import file_sha256


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def atomic_bytes(path: Path, payload: bytes) -> None:
    if path.exists():
        raise FileExistsError(path)
    temporary = path.with_name("." + path.name + ".partial")
    with temporary.open("xb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(path)


def atomic_manifest(path: Path, data: dict) -> None:
    temporary = path.with_name("." + path.name + ".partial")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(path)


def stable_name(identifier: str) -> str:
    return hashlib.sha256(identifier.encode("utf-8")).hexdigest() + ".json"


def checked_manifest(path: Path, *, provider: str, identifiers: list[str], cap: int) -> dict:
    if path.exists():
        manifest = json.loads(path.read_text())
        if manifest["provider"] != provider or manifest["identifiers"] != identifiers or manifest["request_cap"] != cap:
            raise ValueError("Resume request list or budget changed")
        for item in manifest["requests"]:
            raw = path.parent / item["raw_path"]
            if not raw.is_file() or file_sha256(raw) != item["sha256"]:
                raise ValueError(f"Stored response missing or changed: {raw}")
        return manifest
    return {"provider": provider, "identifiers": identifiers, "request_cap": cap,
            "created_at_utc": utc_now(), "status": "planned", "requests": [], "errors": [],
            "http_attempts": 0, "successful": 0, "not_found": 0, "response_bytes": 0,
            "quarantined_orphans": []}


def quarantine_orphans(output_dir: Path, raw_dir: Path, manifest: dict) -> None:
    """Preserve uncheckpointed files, including interrupted `.partial` writes."""
    recorded = {str((output_dir / row["raw_path"]).resolve()) for row in manifest["requests"]}
    orphan_paths = [path for path in raw_dir.iterdir() if path.is_file() and
                    str(path.resolve()) not in recorded]
    if not orphan_paths:
        return
    quarantine = output_dir / "quarantine"
    quarantine.mkdir(exist_ok=True)
    for orphan in sorted(orphan_paths):
        destination = quarantine / (orphan.name + ".orphan")
        if destination.exists():
            raise FileExistsError(destination)
        sha = file_sha256(orphan)
        orphan.replace(destination)
        manifest.setdefault("quarantined_orphans", []).append({
            "path": str(destination.relative_to(output_dir)), "sha256": sha,
            "bytes": destination.stat().st_size, "quarantined_at_utc": utc_now()})


class CrossrefCollector:
    """Sequential Crossref singleton collector; 404 is an expected registry miss."""

    def __init__(self, *, session: requests.Session | None = None, min_interval: float = 0.3,
                 max_retries: int = 3, sleep=time.sleep):
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent":
            "AI-Research-Trends/0.1 (university venue metadata pilot; https://github.com/namkhanh2k5/AI-Research-Trends)",
            "Accept": "application/json"})
        self.min_interval = min_interval
        self.max_retries = max_retries
        self.sleep = sleep

    def collect(self, dois: list[str], output_dir: Path, *, cap: int) -> dict:
        if not 1 <= cap <= 1000 or len(dois) > cap or len(set(dois)) != len(dois):
            raise ValueError("Crossref DOI request cap or unique-ID invariant violated")
        output_dir.mkdir(parents=True, exist_ok=True)
        raw_dir = output_dir / "crossref_raw"
        raw_dir.mkdir(exist_ok=True)
        manifest_path = output_dir / "crossref_request_manifest.json"
        manifest = checked_manifest(manifest_path, provider="crossref", identifiers=dois, cap=cap)
        quarantine_orphans(output_dir, raw_dir, manifest)
        atomic_manifest(manifest_path, manifest)
        completed = {item["identifier"] for item in manifest["requests"]}
        started = time.monotonic()
        for doi in dois:
            if doi in completed:
                continue
            suffix = doi.removeprefix("https://doi.org/")
            url = "https://api.crossref.org/works/" + quote(suffix, safe="")
            last_error = None
            response = None
            for retry in range(self.max_retries + 1):
                if manifest["http_attempts"] >= cap:
                    manifest["status"] = "incomplete"
                    manifest["errors"].append({"identifier": doi,
                        "error": "hard HTTP-attempt budget exhausted", "at": utc_now()})
                    manifest["elapsed_seconds_this_invocation"] = round(time.monotonic() - started, 3)
                    atomic_manifest(manifest_path, manifest)
                    return manifest
                self.sleep(self.min_interval)
                manifest["http_attempts"] += 1
                try:
                    response = self.session.get(url, timeout=25)
                except requests.RequestException as exc:
                    last_error = str(exc)
                    if retry < self.max_retries:
                        self.sleep(min(15, 2 ** retry))
                    continue
                if response.status_code not in {429, 500, 502, 503, 504}:
                    break
                if retry < self.max_retries:
                    try:
                        delay = float(response.headers.get("Retry-After", 2 ** retry))
                    except ValueError:
                        delay = 2 ** retry
                    self.sleep(min(30, max(0, delay)))
            if response is None:
                manifest["errors"].append({"identifier": doi, "error": last_error, "at": utc_now()})
                manifest["status"] = "incomplete"
                atomic_manifest(manifest_path, manifest)
                break
            path = raw_dir / stable_name(doi)
            atomic_bytes(path, response.content)
            entry = {"identifier": doi, "url": url, "status_code": response.status_code,
                     "raw_path": str(path.relative_to(output_dir)),
                     "sha256": file_sha256(path), "bytes": path.stat().st_size,
                     "retrieved_at_utc": utc_now(),
                     "retry_after": response.headers.get("Retry-After"),
                     "rate_limit": response.headers.get("X-Rate-Limit-Limit"),
                     "rate_interval": response.headers.get("X-Rate-Limit-Interval")}
            manifest["requests"].append(entry)
            manifest["response_bytes"] += entry["bytes"]
            if response.status_code == 200:
                try:
                    parse_crossref(response.json(), doi)
                    manifest["successful"] += 1
                except (ValueError, requests.RequestException) as exc:
                    manifest["errors"].append({"identifier": doi, "error": f"malformed 200: {exc}"})
            elif response.status_code == 404:
                manifest["not_found"] += 1
            else:
                manifest["errors"].append({"identifier": doi,
                    "error": f"HTTP {response.status_code}", "at": utc_now()})
            manifest["status"] = "incomplete"
            atomic_manifest(manifest_path, manifest)
            if response.status_code in {403, 429}:
                break  # Respect provider denial; preserve evidence.
        manifest["elapsed_seconds_this_invocation"] = round(time.monotonic() - started, 3)
        manifest["status"] = "complete" if len(manifest["requests"]) == len(dois) and not manifest["errors"] else "incomplete"
        atomic_manifest(manifest_path, manifest)
        return manifest


def read_crossref_records(directory: Path) -> pd.DataFrame:
    path = directory / "crossref_request_manifest.json"
    if not path.exists():
        return pd.DataFrame()
    manifest = checked_manifest(path, provider="crossref",
        identifiers=json.loads(path.read_text())["identifiers"],
        cap=json.loads(path.read_text())["request_cap"])
    rows = []
    for entry in manifest["requests"]:
        if entry["status_code"] != 200:
            continue
        try:
            parsed = parse_crossref(json.loads((directory / entry["raw_path"]).read_bytes()), entry["identifier"])
        except (ValueError, json.JSONDecodeError):
            continue
        for key in ("issns", "invalid_issns", "event", "update_types", "relations"):
            parsed[key] = json.dumps(parsed[key], sort_keys=True, ensure_ascii=False)
        parsed["retrieved_at_utc"] = entry["retrieved_at_utc"]
        parsed["raw_sha256"] = entry["sha256"]
        rows.append(parsed)
    return pd.DataFrame(rows)


def collect_openalex_sources(source_ids: list[str], output_dir: Path, *, cap: int = 30) -> dict:
    if len(source_ids) > cap or cap > 100 or len(set(source_ids)) != len(source_ids):
        raise ValueError("OpenAlex source lookup budget exceeded")
    load_dotenv()
    if not os.getenv("OPENALEX_API_KEY"):
        raise RuntimeError("OPENALEX_API_KEY is not configured")
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = output_dir / "openalex_source_raw"
    raw_dir.mkdir(exist_ok=True)
    path = output_dir / "openalex_source_request_manifest.json"
    manifest = checked_manifest(path, provider="openalex_sources", identifiers=source_ids, cap=cap)
    quarantine_orphans(output_dir, raw_dir, manifest)
    atomic_manifest(path, manifest)
    done = {item["identifier"] for item in manifest["requests"]}
    client = OpenAlexClient(max_retries=0)  # one actual HTTP attempt per budgeted Source ID
    for sid in source_ids:
        if sid in done:
            continue
        response = client.request("sources/" + sid.rsplit("/", 1)[-1], allow_statuses=frozenset({404}))
        raw = raw_dir / stable_name(sid)
        atomic_bytes(raw, response.content)
        entry = {"identifier": sid, "status_code": response.status_code,
                 "raw_path": str(raw.relative_to(output_dir)), "sha256": file_sha256(raw),
                 "bytes": raw.stat().st_size, "retrieved_at_utc": utc_now(),
                 "rate_limit_remaining": response.headers.get("X-RateLimit-Remaining"),
                 "credits_used": response.headers.get("X-RateLimit-Credits-Used")}
        manifest["requests"].append(entry)
        manifest["http_attempts"] += 1
        manifest["response_bytes"] += entry["bytes"]
        manifest["successful"] += response.status_code == 200
        manifest["not_found"] += response.status_code == 404
        manifest["status"] = "incomplete"
        atomic_manifest(path, manifest)
    manifest["status"] = "complete" if len(manifest["requests"]) == len(source_ids) else "incomplete"
    atomic_manifest(path, manifest)
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    cross = sub.add_parser("crossref")
    cross.add_argument("--selection", type=Path, required=True)
    cross.add_argument("--output-dir", type=Path, required=True)
    cross.add_argument("--cap", type=int, default=500)
    cross.add_argument("--execute", action="store_true")
    src = sub.add_parser("openalex-sources")
    src.add_argument("--source-table", type=Path, required=True)
    src.add_argument("--output-dir", type=Path, required=True)
    src.add_argument("--cap", type=int, default=30)
    src.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "crossref":
        selection = pd.read_parquet(args.selection)
        dois = selection.doi.tolist()
        if len(dois) > args.cap:
            raise ValueError("Selection exceeds declared Crossref request cap")
        plan = {"provider": "crossref", "unique_dois": len(dois), "max_http_attempts": args.cap,
                "output_dir": str(args.output_dir)}
        result = CrossrefCollector().collect(dois, args.output_dir, cap=args.cap) if args.execute else plan
    else:
        table = pd.read_parquet(args.source_table)
        missing = table.loc[table.publisher.isna() | table.source_type.eq("unknown"), "source_id"]
        ids = sorted(set(missing))[:args.cap]
        plan = {"provider": "openalex_sources", "source_ids": len(ids), "cap": args.cap,
                "output_dir": str(args.output_dir)}
        result = collect_openalex_sources(ids, args.output_dir, cap=args.cap) if args.execute else plan
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
