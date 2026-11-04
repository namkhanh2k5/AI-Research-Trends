"""Bounded, resumable OpenAlex+Crossref RQ7 pilot; no sealed-test access."""

from __future__ import annotations

import argparse
import json
import os
import re
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import pandas as pd
import pyarrow.parquet as pq
import requests
from dotenv import load_dotenv

from ai_research_trends.crawling.openalex_client import OpenAlexClient, canonical_work_id
from ai_research_trends.crawling.verify_collection import verify_completed_collection
from ai_research_trends.experiments.dual_source.core import (
    integrate_record, normalize_crossref, normalize_openalex, quality_counts,
    safe_doi, select_cohort,
)
from ai_research_trends.experiments.venue_enrichment import atomic_bytes, atomic_manifest, stable_name
from ai_research_trends.preprocessing.validate_tables import file_sha256


ORIGINAL_RAW = Path("data/raw/openalex_stratified/stratified_20261019T155909Z/works.jsonl")
ORIGINAL_PROCESSED = Path("data/processed/openalex_stratified/stratified_20261019T155909Z/works.parquet")
VENUE_INVENTORY = Path("data/analysis/venue_discovery_experiment/venue_poc_20261104_v1/openalex_work_venues.parquet")
PREVIOUS_CROSSREF = Path("data/analysis/venue_discovery_experiment/venue_poc_20261104_v1/crossref")
DEFAULT_RUN = Path("data/analysis/dual_source_etl_pilot/dual_source_rq7_20261104_v1")
WORK_PREFIX = re.compile(r'^\{"id":\s*"([^"]+)"')


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_manifest(path, value)


def reserve_attempt(manifest: dict, provider: str, cap: int) -> None:
    """Reserve a real HTTP attempt before issuing it; budget survives crashes."""
    key = f"{provider}_http_attempts"
    if manifest[key] >= cap:
        raise RuntimeError(f"{provider} HTTP attempt cap exhausted")
    manifest[key] += 1


def crossref_session(email: str) -> requests.Session:
    """Identify requests to Crossref Polite Pool without a credential header."""
    if not email or "@" not in email or " " in email:
        raise ValueError("CROSSREF_EMAIL is required for Polite Pool access")
    session = requests.Session()
    session.headers.update({"User-Agent": "AI-Research-Trends/0.1 (university research metadata pipeline)",
                            "Accept": "application/json"})
    session.params.update({"mailto": email})
    return session


def _record(path: Path, root: Path, **extra) -> dict:
    return {"path": str(path.relative_to(root)), "sha256": file_sha256(path),
            "bytes": path.stat().st_size, **extra}


def _checked(path: Path, root: Path, entry: dict) -> None:
    if path != root / entry["path"] or not path.is_file() or file_sha256(path) != entry["sha256"]:
        raise ValueError(f"Missing/changed checkpoint: {path}")


def _quarantine_uncheckpointed(root: Path, raw_dir: Path, entries: list[dict]) -> list[dict]:
    raw_dir.mkdir(parents=True, exist_ok=True)
    known = {str(root / e["path"]) for e in entries}
    moved = []
    for path in sorted(raw_dir.iterdir()):
        if not path.is_file() or str(path) in known:
            continue
        quarantine = root / "quarantine"
        quarantine.mkdir(exist_ok=True)
        target = quarantine / (path.name + ".orphan")
        if target.exists():
            raise FileExistsError(target)
        sha = file_sha256(path)
        path.replace(target)
        moved.append({"path": str(target.relative_to(root)), "sha256": sha,
                      "reason": "uncheckpointed_or_partial"})
    return moved


def plan(run: Path, *, seed: int = 20261104, general_n: int = 1200,
         targeted_n: int = 300) -> dict:
    if run.exists():
        raise FileExistsError(f"Run already exists: {run}")
    verify_completed_collection(ORIGINAL_RAW.parent / "manifest.json")
    frame = pd.read_parquet(ORIGINAL_PROCESSED,
                            columns=["work_id", "publication_year", "work_type", "doi", "is_retracted"],
                            filters=[("publication_year", "<=", 2024)])
    venue = pd.read_parquet(VENUE_INVENTORY)
    selected = select_cohort(frame, venue, seed=seed, general_n=general_n, targeted_n=targeted_n)
    run.mkdir(parents=True)
    selected.to_parquet(run / "cohort.parquet", index=False)
    manifest = {"run_id": run.name, "created_at_utc": now(), "seed": seed,
                "general_n": general_n, "targeted_n": targeted_n,
                "selection_method": "A largest-remainder year×work-type×DOI proportional; B deterministic DOI-bearing metadata gaps",
                "selected_count": len(selected),
                "groups": {str(k): int(v) for k, v in selected.group.value_counts().items()},
                "source": {str(p): _record(p, Path(".")) for p in (ORIGINAL_RAW, ORIGINAL_PROCESSED, VENUE_INVENTORY)},
                "cohort": _record(run / "cohort.parquet", run),
                "openalex_request_cap": 60, "crossref_http_attempt_cap": 1500,
                "crossref_cache_source": str(PREVIOUS_CROSSREF),
                "status": "planned"}
    write_json(run / "plan.json", manifest)
    return manifest


def _load_plan(run: Path) -> tuple[dict, pd.DataFrame]:
    manifest = read_json(run / "plan.json")
    selected = run / manifest["cohort"]["path"]
    _checked(selected, run, manifest["cohort"])
    for key, entry in manifest["source"].items():
        path = Path(key)
        if not path.is_file() or file_sha256(path) != entry["sha256"]:
            raise ValueError(f"Source artifact changed: {path}")
    cohort = pd.read_parquet(selected)
    if cohort.work_id.duplicated().any() or len(cohort) != manifest["selected_count"]:
        raise ValueError("Cohort count/uniqueness changed")
    return manifest, cohort


def preflight(run: Path) -> dict:
    """Store redacted provider diagnostics; neither key nor contact email is logged."""
    _load_plan(run)
    load_dotenv()
    email = os.getenv("CROSSREF_EMAIL")
    if not os.getenv("OPENALEX_API_KEY") or not email:
        raise RuntimeError("OpenAlex key or Crossref email absent")
    cross = crossref_session(email).get("https://api.crossref.org/works", params={"rows": 0}, timeout=30)
    cross.raise_for_status()
    if cross.json().get("status") != "ok":
        raise ValueError("Crossref preflight response invalid")
    openalex = OpenAlexClient(max_retries=0).request("works", {"per-page": 1})
    if not isinstance(openalex.json().get("meta"), dict):
        raise ValueError("OpenAlex preflight response invalid")
    diagnostics = {"checked_at_utc": now(),
                   "crossref": {"status_code": cross.status_code,
                                "pool": cross.headers.get("x-api-pool"),
                                "rate_limit": cross.headers.get("x-rate-limit-limit"),
                                "rate_interval": cross.headers.get("x-rate-limit-interval"),
                                "concurrency_limit": cross.headers.get("x-concurrency-limit")},
                   "openalex": {"status_code": openalex.status_code,
                                "remaining": openalex.headers.get("X-RateLimit-Remaining"),
                                "limit": openalex.headers.get("X-RateLimit-Limit"),
                                "credits_used": openalex.headers.get("X-RateLimit-Credits-Used")}}
    write_json(run / "connection_preflight.json", diagnostics)
    return diagnostics


def _collection_manifest(run: Path, plan_manifest: dict, *, read_only: bool = False) -> dict:
    path = run / "collection_manifest.json"
    if path.exists():
        data = read_json(path)
        if data["cohort_sha256"] != plan_manifest["cohort"]["sha256"]:
            raise ValueError("Resume cohort changed")
        data.setdefault("openalex_aliases", [])
    else:
        data = {"status": "incomplete", "started_at_utc": now(),
                "cohort_sha256": plan_manifest["cohort"]["sha256"],
                "openalex": [], "openalex_aliases": [], "crossref": [], "openalex_http_attempts": 0,
                "crossref_http_attempts": 0, "errors": [], "orphans": []}
    for provider in ("openalex", "crossref"):
        for entry in data[provider]:
            _checked(run / entry["path"], run, entry)
        if not read_only:
            evidence = [e["evidence"] for e in data["errors"] if e.get("provider") == provider and e.get("evidence")]
            data["orphans"] += _quarantine_uncheckpointed(run, run / "raw" / provider, data[provider] + evidence)
    for entry in data.get("openalex_aliases", []):
        _checked(run / entry["path"], run, entry)
    if not read_only:
        data["orphans"] += _quarantine_uncheckpointed(run, run / "raw" / "openalex_alias", data.get("openalex_aliases", []))
    if not read_only:
        write_json(path, data)
    return data


def _store_response(run: Path, provider: str, identifier: str, content: bytes,
                    *, status: int, cache_source: str | None = None, headers: dict | None = None) -> dict:
    raw_dir = run / "raw" / provider
    raw_dir.mkdir(parents=True, exist_ok=True)
    name = stable_name(identifier)
    path = raw_dir / name
    atomic_bytes(path, content)
    return _record(path, run, identifier=identifier, status_code=status,
                   retrieved_at_utc=now(), cache_source=cache_source,
                   rate_headers=headers or {})


def _previous_crossref_cache() -> dict[str, dict]:
    path = PREVIOUS_CROSSREF / "crossref_request_manifest.json"
    if not path.is_file():
        return {}
    source = read_json(path)
    cache = {}
    for entry in source["requests"]:
        raw = PREVIOUS_CROSSREF / entry["raw_path"]
        if not raw.is_file() or file_sha256(raw) != entry["sha256"]:
            raise ValueError(f"Prior cache evidence changed: {raw}")
        if entry["status_code"] in (200, 404):
            cache[entry["identifier"]] = {"path": raw, "status": entry["status_code"]}
    return cache


def _openalex_records(run: Path, manifest: dict) -> dict[str, dict]:
    works = {}
    for entry in manifest["openalex"]:
        payload = json.loads((run / entry["path"]).read_bytes())
        inverse_aliases = {current: previous for previous, current in entry.get("aliases", {}).items()}
        for work in payload.get("results", []):
            current_id = canonical_work_id(work["id"])
            wid = inverse_aliases.get(current_id, current_id)
            if wid in works:
                raise ValueError(f"OpenAlex repeated work ID: {wid}")
            works[wid] = work
    return works


def collect(run: Path, *, min_interval: float = 0.36) -> dict:
    plan_manifest, cohort = _load_plan(run)
    load_dotenv()
    if not os.getenv("OPENALEX_API_KEY") or not os.getenv("CROSSREF_EMAIL"):
        raise RuntimeError("OpenAlex key or Crossref polite-pool email absent")
    manifest = _collection_manifest(run, plan_manifest)
    if manifest["status"] == "complete":
        raise ValueError("Completed collection is immutable")
    selected_ids = sorted(cohort.work_id)
    batches = [selected_ids[i:i + 50] for i in range(0, len(selected_ids), 50)]
    done = {e["identifier"] for e in manifest["openalex"]}
    client = OpenAlexClient(max_retries=0)
    for batch_no, ids in enumerate(batches):
        key = f"batch:{batch_no:03d}"
        if key in done:
            continue
        try:
            prior = next((e["evidence"] for e in manifest["errors"]
                          if e.get("identifier") == key and e.get("evidence")), None)
            if prior:
                _checked(run / prior["path"], run, prior)
                payload = json.loads((run / prior["path"]).read_bytes())
                entry = prior
            else:
                reserve_attempt(manifest, "openalex", plan_manifest["openalex_request_cap"])
                write_json(run / "collection_manifest.json", manifest)
                response = client.request("works", {"filter": "openalex_id:" + "|".join(x.rsplit("/", 1)[-1] for x in ids),
                                                    "per_page": 100})
                payload = response.json()
                entry = _store_response(run, "openalex", key, response.content, status=response.status_code,
                                        headers={k: response.headers.get(k) for k in
                                                 ("X-RateLimit-Remaining", "X-RateLimit-Credits-Used")})
            found = [canonical_work_id(w["id"]) for w in payload.get("results", [])]
            if len(found) != len(ids) or len(set(found)) != len(found) or payload.get("meta", {}).get("count") != len(ids):
                if not prior:
                    manifest["errors"].append({"provider": "openalex", "identifier": key,
                                               "reason": "batch cardinality mismatch", "evidence": entry})
                write_json(run / "collection_manifest.json", manifest)
                raise ValueError(f"OpenAlex batch cardinality mismatch: {key}")
            missing, unexpected = set(ids) - set(found), set(found) - set(ids)
            aliases = {}
            if missing or unexpected:
                if len(missing) != len(unexpected):
                    raise ValueError(f"OpenAlex batch changed membership: {key}")
                if not prior:
                    manifest["errors"].append({"provider": "openalex", "identifier": key,
                                               "reason": "batch ID drift; singleton verification required", "evidence": entry})
                    write_json(run / "collection_manifest.json", manifest)
                for old_id in sorted(missing):
                    alias_evidence = next((e for e in manifest["openalex_aliases"] if e["identifier"] == old_id), None)
                    if alias_evidence:
                        alias_payload = json.loads((run / alias_evidence["path"]).read_bytes())
                    else:
                        reserve_attempt(manifest, "openalex", plan_manifest["openalex_request_cap"])
                        write_json(run / "collection_manifest.json", manifest)
                        probe = client.request("works/" + old_id.rsplit("/", 1)[-1])
                        alias_payload = probe.json()
                        alias_evidence = _store_response(run, "openalex_alias", old_id,
                                                         probe.content, status=probe.status_code)
                        manifest["openalex_aliases"].append(alias_evidence)
                        write_json(run / "collection_manifest.json", manifest)
                    new_id = canonical_work_id(alias_payload.get("id"))
                    if new_id not in unexpected or new_id in aliases.values():
                        raise ValueError(f"Unverified OpenAlex alias: {old_id}")
                    aliases[old_id] = new_id
            entry["aliases"] = aliases
            manifest["openalex"].append(entry)
            write_json(run / "collection_manifest.json", manifest)
        except Exception as exc:
            manifest["errors"].append({"provider": "openalex", "identifier": key,
                                       "reason": type(exc).__name__, "at": now()})
            write_json(run / "collection_manifest.json", manifest)
            raise
    works = _openalex_records(run, manifest)
    if set(works) != set(selected_ids):
        raise ValueError("OpenAlex collection not complete for planned cohort")
    dois = sorted({doi for work in works.values() if (doi := safe_doi(work.get("doi"))[0])})
    cache = _previous_crossref_cache()
    done = {e["identifier"] for e in manifest["crossref"]}
    session = crossref_session(os.environ["CROSSREF_EMAIL"])
    for index, doi in enumerate(dois):
        if doi in done:
            continue
        previous = cache.get(doi)
        if previous:
            content = previous["path"].read_bytes()
            status = previous["status"]
            source = str(previous["path"])
            headers = {}
        else:
            source = None
            response = None
            for retry in range(3):
                if manifest["crossref_http_attempts"] >= plan_manifest["crossref_http_attempt_cap"]:
                    manifest["errors"].append({"provider": "crossref", "reason": "HTTP attempt cap exhausted"})
                    write_json(run / "collection_manifest.json", manifest)
                    raise RuntimeError("Crossref HTTP attempt cap exhausted")
                reserve_attempt(manifest, "crossref", plan_manifest["crossref_http_attempt_cap"])
                write_json(run / "collection_manifest.json", manifest)
                time.sleep(min_interval)
                try:
                    response = session.get("https://api.crossref.org/works/" + quote(doi.removeprefix("https://doi.org/"), safe=""),
                                           timeout=30)
                except requests.RequestException:
                    if retry == 2:
                        manifest["errors"].append({"provider": "crossref", "identifier": doi,
                                                   "reason": "persistent transport error", "at": now()})
                        write_json(run / "collection_manifest.json", manifest)
                        raise
                    time.sleep(2 ** retry)
                    continue
                if response.status_code in (429, 500, 502, 503, 504):
                    if retry == 2:
                        break
                    try:
                        delay = float(response.headers.get("Retry-After", 2 ** retry))
                    except ValueError:
                        delay = float(2 ** retry)
                    time.sleep(min(30, max(0, delay)))
                    continue
                break
            assert response is not None
            content, status = response.content, response.status_code
            headers = {k: response.headers.get(k) for k in
                       ("x-api-pool", "x-rate-limit-limit", "x-rate-limit-interval", "x-concurrency-limit", "Retry-After")}
        entry = _store_response(run, "crossref", doi, content, status=status,
                                cache_source=source, headers=headers)
        manifest["crossref"].append(entry)
        write_json(run / "collection_manifest.json", manifest)
        if status not in (200, 404):
            manifest["errors"].append({"provider": "crossref", "identifier": doi,
                                       "reason": f"HTTP {status}", "at": now()})
            write_json(run / "collection_manifest.json", manifest)
            raise RuntimeError(f"Crossref HTTP {status}; safe stop")
        if (index + 1) % 100 == 0:
            print(f"Crossref completed {index + 1}/{len(dois)} DOI tasks; fresh HTTP attempts={manifest['crossref_http_attempts']}", flush=True)
    manifest["status"] = "complete"
    manifest["completed_at_utc"] = now()
    manifest["selected_work_count"] = len(works)
    manifest["distinct_doi_tasks"] = len(dois)
    write_json(run / "collection_manifest.json", manifest)
    return manifest


def _original_selected(run: Path, ids: set[str]) -> dict[str, dict]:
    original = {}
    with ORIGINAL_RAW.open(encoding="utf-8") as stream:
        for line in stream:
            prefix = WORK_PREFIX.match(line)
            if prefix is None:
                raise ValueError("Original raw JSONL ID prefix missing")
            wid = canonical_work_id(prefix.group(1))
            if wid in ids:
                original[wid] = json.loads(line)
    if set(original) != ids:
        raise ValueError("Original snapshot lacks selected IDs")
    return original


def _parquet(path: Path, rows: list[dict], *, columns: list[str] | None = None) -> dict:
    frame = pd.DataFrame(rows)
    if frame.empty and columns:
        frame = pd.DataFrame(columns=columns)
    for column in frame.columns:
        if frame[column].map(lambda v: isinstance(v, (dict, list, tuple))).any():
            frame[column] = frame[column].map(lambda v: json.dumps(v, ensure_ascii=False, sort_keys=True)
                                               if isinstance(v, (dict, list, tuple)) else v)
    temp = path.with_name("." + path.name + ".partial")
    frame.to_parquet(temp, index=False)
    temp.replace(path)
    return _record(path, path.parent.parent, rows=len(frame), columns=list(frame.columns))


def process(run: Path) -> dict:
    plan_manifest, cohort = _load_plan(run)
    collection = _collection_manifest(run, plan_manifest, read_only=True)
    if collection["status"] != "complete":
        raise ValueError("Cannot process incomplete collection")
    started = time.monotonic()
    oa = _openalex_records(run, collection)
    if set(oa) != set(cohort.work_id):
        raise ValueError("Processed cohort differs from collected Work IDs")
    old = _original_selected(run, set(oa))
    cross = {}
    for entry in collection["crossref"]:
        if entry["status_code"] == 200:
            try:
                cross[entry["identifier"]] = normalize_crossref(
                    json.loads((run / entry["path"]).read_bytes()), entry["identifier"])
            except json.JSONDecodeError:
                cross[entry["identifier"]] = "PROVIDER_ERROR"
            except ValueError as exc:
                cross[entry["identifier"]] = ("IDENTIFIER_CONFLICT" if "DOI mismatch" in str(exc)
                                                  else "PROVIDER_ERROR")
    cross_status = {e["identifier"]: e["status_code"] for e in collection["crossref"]}
    groups = dict(zip(cohort.work_id, cohort.group))
    rows, oa_clean, raw_baseline = [], [], []
    work_to_page = {}
    for entry in collection["openalex"]:
        inverse_aliases = {current: previous for previous, current in entry.get("aliases", {}).items()}
        for work in json.loads((run / entry["path"]).read_bytes())["results"]:
            current_id = canonical_work_id(work["id"])
            work_to_page[inverse_aliases.get(current_id, current_id)] = entry["path"]
    aliases = {previous: current for entry in collection["openalex"]
               for previous, current in entry.get("aliases", {}).items()}
    provider_records, links, provenance, conflicts, duplicates, missingness = [], [], [], [], [], []
    for wid in sorted(oa):
        fresh, historical = oa[wid], old[wid]
        norm = normalize_openalex(fresh)
        original_norm = normalize_openalex(historical)
        norm["work_id"] = wid
        norm["openalex_current_work_id"] = aliases.get(wid, wid)
        norm["current_frame_member"] = (isinstance(norm["publication_date"], str) and
                                        "2020-01-01" <= norm["publication_date"] <= "2024-12-31" and
                                        norm["work_type"] in ("article", "review", "preprint") and
                                        str(norm["primary_subfield_id"] or "").rsplit("/", 1)[-1] in ("1702", "1707") and
                                        norm["is_retracted"] is False)
        norm["group"] = groups[wid]
        original_norm["group"] = groups[wid]
        doi = norm["doi"]
        candidate = cross.get(doi)
        status = ("DOI_MISSING" if norm["doi_status"] == "DOI_MISSING" else
                  "DOI_INVALID" if norm["doi_status"] == "DOI_INVALID" else
                  "EXACT_DOI_MATCH" if isinstance(candidate, dict) else
                  "IDENTIFIER_CONFLICT" if candidate == "IDENTIFIER_CONFLICT" else
                  "PROVIDER_ERROR" if candidate == "PROVIDER_ERROR" else
                  "CROSSREF_NOT_FOUND" if cross_status.get(doi) == 404 else "PROVIDER_ERROR")
        integrated, prov, conflict = integrate_record(norm, candidate if isinstance(candidate, dict) else None, status)
        integrated["group"] = groups[wid]
        selected_sources = {item["field"]: item["selected_source"] for item in prov}
        for field in ("publisher", "venue_name", "issns", "license"):
            integrated[field + "_source"] = selected_sources[field]
        if not norm["current_frame_member"]:
            integrated["quality_warnings"].append("current_openalex_outside_original_frame_definition")
        integrated["crossref_author_count"] = len(candidate["authors"]) if isinstance(candidate, dict) else None
        integrated["crossref_reference_count"] = len(candidate["references"]) if isinstance(candidate, dict) else None
        integrated["crossref_funder_count"] = len(candidate["funder"]) if isinstance(candidate, dict) else None
        integrated["crossref_abstract_available"] = bool(candidate["abstract"]) if isinstance(candidate, dict) else None
        integrated["crossref_orcid_available"] = any(a.get("ORCID") for a in candidate["authors"] if isinstance(a, dict)) if isinstance(candidate, dict) else None
        integrated["crossref_affiliation_available"] = any(a.get("affiliation") for a in candidate["authors"] if isinstance(a, dict)) if isinstance(candidate, dict) else None
        integrated["snapshot_drift_fields"] = [field for field in ("doi", "title", "publication_date", "publication_year", "work_type", "primary_topic_id", "primary_subfield_id", "publisher", "venue_name", "issns", "is_retracted") if norm.get(field) != original_norm.get(field)]
        rows.append(integrated)
        oa_clean.append(norm)
        raw_baseline.append({"work_id": wid, "group": groups[wid], "doi": fresh.get("doi"),
                             "doi_status": norm["doi_status"], "abstract": fresh.get("abstract_inverted_index"),
                             "publisher": (fresh.get("primary_location") or {}).get("source", {}).get("host_organization_name") if isinstance((fresh.get("primary_location") or {}).get("source"), dict) else None,
                             "venue_name": (fresh.get("primary_location") or {}).get("source", {}).get("display_name") if isinstance((fresh.get("primary_location") or {}).get("source"), dict) else None,
                             "issns": (fresh.get("primary_location") or {}).get("source", {}).get("issn") if isinstance((fresh.get("primary_location") or {}).get("source"), dict) else None,
                             "publication_date": fresh.get("publication_date"),
                             "license": (fresh.get("primary_location") or {}).get("license")})
        provenance += prov
        conflicts += conflict
        links.append({"work_id": wid, "doi": doi, "match_status": status,
                      "quarantine_reason": ("crossref_doi_mismatch" if status == "IDENTIFIER_CONFLICT" else
                                            "malformed_provider_response" if status == "PROVIDER_ERROR" else None),
                      "openalex_raw_path": work_to_page[wid],
                      "crossref_raw_path": next((e["path"] for e in collection["crossref"] if e["identifier"] == doi), None)})
        provider_records.append({"provider": "openalex", "work_id": wid, "doi": doi,
                                 "publication_year": norm["publication_year"], "title": norm["title"],
                                 "abstract_available": bool(norm["abstract"]),
                                 "author_count": norm["authorship_count"], "reference_count": norm["reference_count"],
                                 "funder_count": None, "affiliation_available": None, "orcid_available": None})
        if isinstance(candidate, dict):
            provider_records.append({"provider": "crossref", "work_id": wid, "doi": doi,
                                     "publication_year": candidate["publication_year"], "title": candidate["title"],
                                     "abstract_available": bool(candidate["abstract"]),
                                     "author_count": len(candidate["authors"]),
                                     "reference_count": len(candidate["references"]),
                                     "funder_count": len(candidate["funder"]),
                                     "affiliation_available": integrated["crossref_affiliation_available"],
                                     "orcid_available": integrated["crossref_orcid_available"]})
        if integrated["snapshot_drift_fields"]:
            duplicates.append({"work_id": wid, "issue": "snapshot_drift", "fields": integrated["snapshot_drift_fields"]})
        missingness.append({"work_id": wid, "group": groups[wid], "publication_year": norm["publication_year"],
                            "work_type": norm["work_type"], **{f"missing_{field}": not bool(integrated.get(field))
                                                                for field in ("doi", "abstract", "publisher", "venue_name", "issns", "license")}})
    doi_counts = Counter(r["doi"] for r in rows if r["doi"])
    duplicates += [{"work_id": row["work_id"], "issue": "shared_doi", "fields": [row["doi"]]}
                   for row in rows if row["doi"] and doi_counts[row["doi"]] > 1]
    if len(rows) != len(cohort) or len({r["work_id"] for r in rows}) != len(rows):
        raise ValueError("Canonical one-row-per-Work invariant failed")
    stage = {"raw_openalex": quality_counts(raw_baseline),
             "cleaned_openalex": quality_counts(oa_clean),
             "integrated": quality_counts(rows)}
    by_group = {group: {"raw_openalex": quality_counts([r for r in raw_baseline if r["group"] == group]),
                        "cleaned_openalex": quality_counts([r for r in oa_clean if r["group"] == group]),
                        "integrated": quality_counts([r for r in rows if r["group"] == group])}
                for group in ("A_GENERAL", "B_TARGETED_MISSINGNESS")}
    recovery = {field: {"missing_before": sum(not bool(r.get(field)) for r in oa_clean),
                        "crossref_available": sum(p["crossref_available"] for p in provenance if p["field"] == field),
                        "validated_additions": sum(not bool(before.get(field)) and bool(after.get(field))
                                                   for before, after in zip(oa_clean, rows)),
                        "rejected_or_deferred_additions": sum(not p["openalex_available"] and p["crossref_available"] and p["selected_source"] != "crossref"
                                                              for p in provenance if p["field"] == field),
                        "conflicts": sum(c["field"] == field for c in conflicts),
                        "missing_after": sum(not bool(r.get(field)) for r in rows)}
                for field in ("publisher", "venue_name", "issns", "license", "abstract", "publication_date")}
    retractions = [{"work_id": r["work_id"], "openalex_retracted": r["is_retracted"],
                    "crossref_retraction_evidence": r["crossref_retraction_evidence"],
                    "status": "CONFLICT_REVIEW" if r["crossref_retraction_evidence"] and not r["is_retracted"] else "NO_CONTRADICTION_OBSERVED"}
                   for r in rows]
    out = run / "processed"
    out.mkdir(exist_ok=True)
    artifacts = {}
    tables = {"canonical_works": rows, "provider_records": provider_records,
              "provider_links": links, "field_provenance": provenance,
              "metadata_conflicts": conflicts, "duplicate_audit": duplicates,
              "missingness_report": missingness, "retraction_status_audit": retractions,
              "data_quality_summary": [{"stage": stage_name, **counts} for stage_name, counts in stage.items()]}
    for name, records in tables.items():
        artifacts[name] = _parquet(out / f"{name}.parquet", records,
                                   columns=["work_id", "field", "openalex_value", "crossref_value", "resolution", "difference_kind"]
                                   if name == "metadata_conflicts" else None)
    evaluation = {"run_id": run.name, "processed_at_utc": now(), "selected": len(cohort),
                  "stage": stage, "by_group": by_group, "recovery": recovery,
                  "match_status": dict(Counter(r["match_status"] for r in rows)),
                  "snapshot_drift_work_count": sum(bool(r["snapshot_drift_fields"]) for r in rows),
                  "metadata_conflict_count": len(conflicts),
                  "conflicts_by_field": dict(Counter(c["field"] for c in conflicts)),
                  "invalid_openalex_issn_values": sum(len(r["invalid_issns"]) for r in oa_clean),
                  "invalid_crossref_issn_values": sum(len(r["invalid_issns"]) for r in cross.values() if isinstance(r, dict)),
                  "malformed_openalex_abstracts": sum(r["abstract_status"] == "MALFORMED" for r in oa_clean),
                  "crossref_retraction_evidence_count": sum(bool(r["crossref_retraction_evidence"]) for r in rows),
                  "current_out_of_frame_count": sum(not r["current_frame_member"] for r in rows),
                  "current_out_of_frame_reasons_not_disjoint": {
                      "date_outside_2020_2024": sum(not (isinstance(r["publication_date"], str) and
                                                         "2020-01-01" <= r["publication_date"] <= "2024-12-31") for r in rows),
                      "type_outside_article_review_preprint": sum(r["work_type"] not in ("article", "review", "preprint") for r in rows),
                      "primary_subfield_outside_1702_1707": sum(str(r["primary_subfield_id"] or "").rsplit("/", 1)[-1] not in ("1702", "1707") for r in rows),
                      "new_retraction_flag": sum(r["is_retracted"] is True for r in rows)},
                  "processing_seconds": round(time.monotonic() - started, 3)}
    write_json(run / "evaluation.json", evaluation)
    manifest = {"status": "complete", "created_at_utc": now(),
                "plan_sha256": file_sha256(run / "plan.json"),
                "collection_manifest_sha256": file_sha256(run / "collection_manifest.json"),
                "outputs": artifacts, "evaluation": _record(run / "evaluation.json", run),
                "processing_seconds": evaluation["processing_seconds"]}
    write_json(run / "processing_manifest.json", manifest)
    return evaluation


def verify(run: Path) -> dict:
    plan_manifest, cohort = _load_plan(run)
    collection = _collection_manifest(run, plan_manifest, read_only=True)
    processed = read_json(run / "processing_manifest.json")
    if collection["status"] != "complete" or processed["status"] != "complete":
        raise ValueError("Incomplete RQ7 run")
    if file_sha256(run / "plan.json") != processed["plan_sha256"] or file_sha256(run / "collection_manifest.json") != processed["collection_manifest_sha256"]:
        raise ValueError("Manifest parent checksum mismatch")
    for entry in processed["outputs"].values():
        _checked(run / entry["path"], run, entry)
        if len(pd.read_parquet(run / entry["path"])) != entry["rows"]:
            raise ValueError("Parquet row count changed")
    _checked(run / processed["evaluation"]["path"], run, processed["evaluation"])
    canonical = pd.read_parquet(run / processed["outputs"]["canonical_works"]["path"])
    if len(canonical) != len(cohort) or canonical.work_id.duplicated().any() or set(canonical.work_id) != set(cohort.work_id):
        raise ValueError("Canonical cohort integrity failed")
    if dict(zip(canonical.work_id, canonical.group)) != dict(zip(cohort.work_id, cohort.group)):
        raise ValueError("Cohort group membership changed")
    if set(_openalex_records(run, collection)) != set(cohort.work_id):
        raise ValueError("OpenAlex raw batch membership changed")
    cross_by_doi = {e["identifier"]: e for e in collection["crossref"]}
    if len(cross_by_doi) != len(collection["crossref"]):
        raise ValueError("Duplicate Crossref DOI task")
    for row in canonical.loc[canonical.match_status.eq("EXACT_DOI_MATCH")].itertuples():
        entry = cross_by_doi.get(row.doi)
        if entry is None or entry["status_code"] != 200:
            raise ValueError("Exact DOI link lacks a successful provider response")
        if normalize_crossref(json.loads((run / entry["path"]).read_bytes()), row.doi)["doi"] != row.doi:
            raise ValueError("Exact DOI link changed identity")
    links = pd.read_parquet(run / processed["outputs"]["provider_links"]["path"])
    if links.work_id.duplicated().any() or set(links.work_id) != set(canonical.work_id):
        raise ValueError("Provider link referential integrity failed")
    for name in ("provider_records", "field_provenance", "metadata_conflicts", "duplicate_audit",
                 "missingness_report", "retraction_status_audit"):
        frame = pd.read_parquet(run / processed["outputs"][name]["path"])
        if not set(frame.work_id).issubset(set(canonical.work_id)):
            raise ValueError(f"{name} contains foreign Work IDs")
        if name in ("missingness_report", "retraction_status_audit") and (
                frame.work_id.duplicated().any() or set(frame.work_id) != set(canonical.work_id)):
            raise ValueError(f"{name} one-to-one integrity failed")
        if name == "field_provenance" and frame.duplicated(["work_id", "field"]).any():
            raise ValueError("Field provenance composite key repeated")
    summary = pd.read_parquet(run / processed["outputs"]["data_quality_summary"]["path"])
    if set(summary.stage) != {"raw_openalex", "cleaned_openalex", "integrated"} or not summary.records.eq(len(cohort)).all():
        raise ValueError("Quality stage denominators inconsistent")
    return {"status": "PASS", "selected": len(cohort), "canonical": len(canonical),
            "openalex_batches": len(collection["openalex"]),
            "crossref_tasks": len(collection["crossref"]),
            "parquet_tables": len(processed["outputs"]),
            "sha256_verified": len(collection["openalex"]) + len(collection["crossref"]) + len(processed["outputs"]) + 1}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=["plan", "preflight", "collect", "process", "verify"])
    parser.add_argument("--run", type=Path, default=DEFAULT_RUN)
    parser.add_argument("--general", type=int, default=1200)
    parser.add_argument("--targeted", type=int, default=300)
    parser.add_argument("--seed", type=int, default=20261104)
    args = parser.parse_args()
    action = {"plan": lambda: plan(args.run, seed=args.seed, general_n=args.general, targeted_n=args.targeted),
              "preflight": lambda: preflight(args.run),
              "collect": lambda: collect(args.run), "process": lambda: process(args.run),
              "verify": lambda: verify(args.run)}[args.stage]
    result = action()
    if args.stage == "plan":
        result = {k: result[k] for k in ("run_id", "selected_count", "groups", "status")}
    elif args.stage == "collect":
        result = {k: result[k] for k in ("status", "selected_work_count", "distinct_doi_tasks",
                                         "openalex_http_attempts", "crossref_http_attempts")}
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
