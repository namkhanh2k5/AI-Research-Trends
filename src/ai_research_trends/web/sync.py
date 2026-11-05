"""Bounded publication-date synchronization for the *mutable application* corpus.

This is not change-data capture: OpenAlex created/updated-date filters require
paid access. Historical research data and the frozen classifier are untouched.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import pandas as pd

from ai_research_trends.artifact_paths import application_artifacts
from ai_research_trends.crawling.openalex_client import (
    OpenAlexClient, OpenAlexError, canonical_work_id, parse_list_response, utc_now,
)
from ai_research_trends.preprocessing.common import clean_text, normalize_doi, nonnegative_int
from ai_research_trends.preprocessing.text import reconstruct_abstract
from ai_research_trends.preprocessing.validate_tables import file_sha256
from ai_research_trends.web.paper_discovery import DEFAULT_WORKS, build_index, verify_index

DEFAULT_ROOT = Path(__file__).resolve().parents[3] / "data/application/openalex_sync"
MIN_DATE = date(2026, 1, 1)
RUN_ID = re.compile(r"sync_[0-9]{8}T[0-9]{6}Z_[0-9a-f]{8}\Z")
APP_COLUMNS = ("work_id", "title", "abstract", "publication_date", "publication_year",
               "work_type", "doi", "primary_topic_id", "cited_by_count",
               "first_seen_at_utc", "last_seen_at_utc")


def _atomic_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".partial", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    _atomic_bytes(path, (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode())


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def publication_filter(start: date, end: date) -> str:
    """Reusable AI/CV type/subfield/retraction scope, with a separate 2026+ window."""
    if start < MIN_DATE or end < start or end > datetime.now(timezone.utc).date():
        raise ValueError("Sync window must be a past or current publication-date range from 2026")
    return (f"from_publication_date:{start},to_publication_date:{end},"
            "primary_topic.subfield.id:1702|1707,type:article|review|preprint,is_retracted:false")


def normalize_application_work(work: dict[str, Any], start: date, end: date,
                               retrieved_at: str) -> dict[str, Any]:
    """Reject out-of-scope metadata; preserve nullable text without inventions."""
    wid = canonical_work_id(work.get("id", ""))
    published = date.fromisoformat(work["publication_date"])
    year = work.get("publication_year")
    if (not start <= published <= end or not isinstance(year, int) or isinstance(year, bool)
            or year != published.year or work.get("type") not in {"article", "review", "preprint"}
            or work.get("is_retracted") is not False):
        raise ValueError(f"Out-of-scope application work: {wid}")
    topic = work.get("primary_topic")
    if not isinstance(topic, dict) or not isinstance(topic.get("subfield"), dict):
        raise ValueError(f"Missing primary-topic subfield: {wid}")
    subfield = str(topic["subfield"].get("id", "")).rstrip("/").split("/")[-1]
    if subfield not in {"1702", "1707"}:
        raise ValueError(f"Out-of-scope subfield: {wid}")
    topic_id = topic.get("id")
    if topic_id is not None:
        if not isinstance(topic_id, str) or not re.fullmatch(r"https://openalex\.org/T[1-9][0-9]*", topic_id):
            raise ValueError(f"Malformed primary topic: {wid}")
    try:
        abstract = reconstruct_abstract(work.get("abstract_inverted_index"))
    except (ValueError, TypeError) as exc:
        # Unlike research preprocessing, online discovery cannot publish an
        # unverifiable text representation without a separate quarantine audit.
        raise ValueError(f"Malformed abstract for {wid}: {exc}") from exc
    return {"work_id": wid, "title": clean_text(work.get("title")), "abstract": abstract,
            "publication_date": published.isoformat(), "publication_year": year,
            "work_type": work["type"], "doi": normalize_doi(work.get("doi")),
            "primary_topic_id": topic_id,
            "cited_by_count": nonnegative_int(work.get("cited_by_count"), "cited_by_count"),
            "first_seen_at_utc": retrieved_at, "last_seen_at_utc": retrieved_at}


def _ids(payload: dict[str, Any]) -> list[str]:
    envelope = parse_list_response(payload)
    ids = [canonical_work_id(work.get("id", "")) for work in envelope.results]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate Work IDs within an API page")
    return ids


def _page_request(client: OpenAlexClient, params: dict[str, Any]) -> tuple[bytes, dict[str, Any]]:
    response = client.request("works", params)
    raw = response.content
    try:
        payload = json.loads(raw)
    except (ValueError, TypeError) as exc:
        raise OpenAlexError("OpenAlex returned malformed JSON") from exc
    parse_list_response(payload)
    return raw, payload


def _validate_page(payload: dict[str, Any], *, expected: int | None, per_page: int,
                   seen: set[str]) -> tuple[list[str], str | None, int]:
    page = parse_list_response(payload)
    count = page.meta.get("count")
    if not isinstance(count, int) or isinstance(count, bool) or count < 0:
        raise ValueError("Invalid OpenAlex meta.count")
    if expected is not None and count != expected:
        raise ValueError("OpenAlex result count changed during synchronization")
    ids = _ids(payload)
    if seen.intersection(ids):
        raise ValueError("Duplicate Work ID across cursor pages")
    if len(ids) > per_page or (page.next_cursor and not ids):
        raise ValueError("Malformed cursor page")
    return ids, page.next_cursor, count


def _window(state: dict[str, Any] | None, start: date | None, end: date | None,
            lookback_days: int) -> tuple[date, date]:
    today = datetime.now(timezone.utc).date()
    end = end or today
    if start is None:
        if state is None:
            start = max(MIN_DATE, end - timedelta(days=lookback_days - 1))
        else:
            start = max(MIN_DATE, date.fromisoformat(state["window_end"]) - timedelta(days=lookback_days - 1))
    publication_filter(start, end)
    if state is not None and start > date.fromisoformat(state["window_end"]) + timedelta(days=1):
        raise ValueError("Requested window skips unpublished dates after the last successful checkpoint")
    return start, end


def daily_windows(start: date, end: date, *, max_days: int = 31) -> list[date]:
    """Plan every day explicitly so an oversized day cannot skip later dates."""
    publication_filter(start, end)
    if not 1 <= max_days <= 366:
        raise ValueError("max_days must be between 1 and 366")
    days = (end - start).days + 1
    if days > max_days:
        raise ValueError(
            f"Unprocessed range {start}..{end} contains {days} days, above max_days={max_days}. "
            "Run consecutive explicit --from-date/--to-date chunks; do not skip dates."
        )
    return [start + timedelta(days=offset) for offset in range(days)]


def sync_daily(*, start: date, end: date, max_days: int = 31,
               **kwargs: Any) -> list[dict[str, Any]]:
    """Commit one complete day at a time; stop at the first incomplete day."""
    completed: list[dict[str, Any]] = []
    for day in daily_windows(start, end, max_days=max_days):
        try:
            completed.append(sync(start=day, end=day, **kwargs))
        except Exception as exc:
            raise RuntimeError(
                f"Daily synchronization stopped at {day}; no later date was processed. "
                f"The last published verified state remains available. "
                f"Inspect that day's incomplete run manifest, then retry with "
                f"--from-date {day} --to-date {day}; if its count exceeds max_records, "
                "raise the cap only within the supported 10,000 limit or investigate the API."
            ) from exc
    return completed


def _merge_application(previous: Path | None, new_rows: list[dict[str, Any]]) -> tuple[pd.DataFrame, dict[str, int]]:
    old = pd.read_parquet(previous) if previous is not None else pd.DataFrame(columns=APP_COLUMNS)
    if old.work_id.duplicated().any():
        raise ValueError("Existing application store has duplicate Work IDs")
    current = {str(row["work_id"]): row for row in old.to_dict("records")}
    added = updated = unchanged = 0
    for row in new_rows:
        prior = current.get(row["work_id"])
        if prior is None:
            added += 1
        else:
            row["first_seen_at_utc"] = prior["first_seen_at_utc"]
            compared = [k for k in APP_COLUMNS if k not in {"first_seen_at_utc", "last_seen_at_utc"}]
            changed = any((prior[k] if pd.notna(prior[k]) else None) != row[k] for k in compared)
            updated += int(changed)
            unchanged += int(not changed)
        current[row["work_id"]] = row
    result = pd.DataFrame([current[key] for key in sorted(current)], columns=APP_COLUMNS)
    return result, {"newly_observed_ids": added, "observed_metadata_updates": updated,
                    "unchanged_reobservations": unchanged}


def _safe_run(root: Path, run_id: str) -> Path:
    if not RUN_ID.fullmatch(run_id):
        raise ValueError("Unsafe run identifier")
    return root / "runs" / run_id


def _quarantine_orphans(run_dir: Path, known: set[str]) -> None:
    """Retain uncommitted bytes without accepting them as checkpoints."""
    raw_dir = run_dir / "raw_pages"
    if not raw_dir.exists():
        return
    orphans = [path for path in raw_dir.iterdir() if path.name not in known]
    for path in orphans:
        if not path.is_file() and not path.is_symlink():
            raise ValueError(f"Unexpected raw-page directory: {path.name}")
        target = run_dir / "quarantine" / f"{path.name}.{uuid4().hex[:8]}"
        target.parent.mkdir(parents=True, exist_ok=True)
        os.replace(path, target)
    if orphans:
        raise ValueError(f"Quarantined {len(orphans)} uncheckpointed raw-page file(s); retry resume")


def sync(*, root: Path, original_works: Path, web_dir: Path, original_index: Path,
         client: OpenAlexClient, start: date | None = None, end: date | None = None,
         lookback_days: int = 3, per_page: int = 100, max_records: int = 3000,
         resume: str | None = None, rebuild_index=build_index) -> dict[str, Any]:
    """Collect, verify and publish one bounded window; commit state only last."""
    if not 1 <= per_page <= 100 or not 1 <= max_records <= 10000 or not 1 <= lookback_days <= 365:
        raise ValueError("Invalid sync limits")
    root.mkdir(parents=True, exist_ok=True)
    with (root / ".sync.lock").open("a+b") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("Another sync is active") from exc
        state_path = root / "state.json"
        state = _read_json(state_path) if state_path.exists() else None
        if resume:
            run_dir = _safe_run(root, resume)
            manifest_path = run_dir / "manifest.json"
            manifest = _read_json(manifest_path)
            if manifest.get("status") == "complete":
                raise ValueError("Completed sync runs are immutable")
            start, end = date.fromisoformat(manifest["window_start"]), date.fromisoformat(manifest["window_end"])
            if manifest["filter"] != publication_filter(start, end) or manifest["per_page"] != per_page:
                raise ValueError("Resume parameters disagree with checkpoint")
            for checkpoint in manifest.get("pages", []):
                if not re.fullmatch(r"page_[0-9]{4}\.json", checkpoint.get("file", "")):
                    raise ValueError("Unsafe checkpoint page filename")
        else:
            start, end = _window(state, start, end, lookback_days)
            run_id = f"sync_{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}_{uuid4().hex[:8]}"
            run_dir = _safe_run(root, run_id)
            run_dir.mkdir(parents=True, exist_ok=False)
            manifest_path = run_dir / "manifest.json"
            manifest = {"status": "incomplete", "run_id": run_id, "created_at_utc": utc_now(),
                        "window_start": start.isoformat(), "window_end": end.isoformat(),
                        "filter": publication_filter(start, end), "per_page": per_page,
                        "mode": "publication_date_bounded_fallback_not_cdc", "pages": [],
                        "source": "OpenAlex works cursor API"}
            _atomic_json(manifest_path, manifest)
        try:
            # Replay *every* checkpointed page against the live cursor sequence.
            # IDs/count/cursor must match; raw evidence is never replaced.
            seen: set[str] = set()
            cursor = "*"
            total: int | None = None
            rows: list[dict[str, Any]] = []
            checkpoints = manifest["pages"]
            _quarantine_orphans(run_dir, {entry["file"] for entry in checkpoints})
            if checkpoints:
                total = manifest.get("expected_count")
                if not isinstance(total, int) or total < 0:
                    raise ValueError("Checkpoint has invalid expected count")
            index = 0
            while True:
                params = {"filter": manifest["filter"], "per_page": per_page, "cursor": cursor}
                if index < len(checkpoints):
                    checkpoint = checkpoints[index]
                    if checkpoint["cursor_in"] != cursor:
                        raise ValueError("Checkpoint cursor chain is invalid")
                    stored = run_dir / "raw_pages" / checkpoint["file"]
                    if not stored.is_file() or file_sha256(stored) != checkpoint["sha256"]:
                        raise ValueError("Checkpoint raw page is missing or corrupt")
                raw, payload = _page_request(client, params)
                ids, next_cursor, count = _validate_page(payload, expected=total, per_page=per_page, seen=seen)
                total = count
                if total > max_records:
                    raise ValueError(f"Window has {total} records; exceeds max_records={max_records}. "
                                     "For a single day, increase the cap only if the complete count fits 10,000")
                if index < len(checkpoints):
                    if checkpoint["ids"] != ids or checkpoint["cursor_out"] != next_cursor:
                        raise ValueError("Checkpoint membership/cursor changed; start a fresh run")
                    # Preserve originally captured metadata; never substitute probe responses.
                    payload = json.loads(stored.read_bytes())
                else:
                    file_name = f"page_{index + 1:04d}.json"
                    target = run_dir / "raw_pages" / file_name
                    if target.exists():
                        quarantine = run_dir / "quarantine" / file_name
                        quarantine.parent.mkdir(parents=True, exist_ok=True)
                        os.replace(target, quarantine)
                        raise ValueError("Uncheckpointed orphan page quarantined; retry this run")
                    _atomic_bytes(target, raw)
                    checkpoint = {"file": file_name, "sha256": hashlib.sha256(raw).hexdigest(),
                                  "bytes": len(raw), "cursor_in": cursor, "cursor_out": next_cursor,
                                  "ids": ids, "retrieved_at_utc": utc_now()}
                    checkpoints.append(checkpoint)
                    manifest["expected_count"] = total
                    _atomic_json(manifest_path, manifest)
                seen.update(ids)
                for work in parse_list_response(payload).results:
                    rows.append(normalize_application_work(work, start, end, checkpoint["retrieved_at_utc"]))
                cursor = next_cursor
                if not cursor:
                    break
                index += 1
            if total != len(rows) or len(seen) != len(rows):
                raise ValueError(f"Incomplete cursor traversal: expected {total}, got {len(rows)}")
            if state:
                previous = Path(state["application_works"])
                if not previous.resolve().is_relative_to(root.resolve()) or file_sha256(previous) != state["application_sha256"]:
                    raise ValueError("Published application source changed")
            else:
                previous = None
            frame, changes = _merge_application(previous, rows)
            app_path = run_dir / "application_works.parquet"
            stage = run_dir / ".application_works.partial"
            frame.to_parquet(stage, index=False)
            with stage.open("rb") as handle:
                os.fsync(handle.fileno())
            os.replace(stage, app_path)
            app_hash = file_sha256(app_path)
            _atomic_json(run_dir / "application_manifest.json", {
                "status": "complete", "rows": len(frame), "sha256": app_hash,
                "source_run": manifest["run_id"], "source_pages": len(checkpoints)})
            # Rebuild a full TF-IDF corpus; publish only the verified new index.
            index = run_dir / "index"
            if len(frame):
                if not index.exists():
                    rebuild_index(original_works, web_dir, index, application_works_path=app_path)
                built = verify_index(index, works_path=original_works, web_dir=web_dir)
                if built["source"].get("application_works_sha256") != app_hash:
                    raise ValueError("Existing index does not match the resumed application data")
            else:
                index = Path(state["index"]) if state else original_index
                built = verify_index(index, works_path=original_works, web_dir=web_dir)
            manifest.pop("last_error", None)
            manifest.pop("failed_at_utc", None)
            manifest.update({"status": "complete", "completed_at_utc": utc_now(),
                             "retrieved": len(rows), "unique_ids": len(seen), "application_rows": len(frame),
                             "changes": changes, "application_sha256": app_hash,
                             "index": str(index.resolve()),
                             "storage_bytes": sum(path.stat().st_size for path in run_dir.rglob("*") if path.is_file())})
            _atomic_json(manifest_path, manifest)
            # This single small pointer is the application transaction commit.
            _atomic_json(state_path, {"status": "complete", "run_id": manifest["run_id"],
                                      "last_success_at_utc": manifest["completed_at_utc"],
                                      "window_end": end.isoformat(),
                                      "application_works": str(app_path.resolve()),
                                      "application_sha256": app_hash, "index": str(index.resolve()),
                                      "application_rows": len(frame)})
            return manifest
        except Exception as exc:
            manifest["status"] = "incomplete"
            manifest["last_error"] = f"{type(exc).__name__}: {exc}"
            manifest["failed_at_utc"] = utc_now()
            _atomic_json(manifest_path, manifest)
            raise


def read_sync_status(root: Path = DEFAULT_ROOT) -> dict[str, Any] | None:
    state_path = root / "state.json"
    if not state_path.is_file():
        return None
    try:
        state = _read_json(state_path)
        if state.get("status") != "complete":
            return None
        path = Path(state["index"])
        original = application_artifacts()["paper_discovery"]
        if not path.is_dir() or not (path.resolve().is_relative_to(root.resolve()) or path == original):
            return None
        application = Path(state["application_works"])
        if not application.resolve().is_relative_to(root.resolve()):
            return None
        run = _safe_run(root, state["run_id"])
        manifest = _read_json(run / "manifest.json")
        if manifest.get("status") != "complete" or file_sha256(application) != state["application_sha256"]:
            return None
        index_manifest = _read_json(path / "manifest.json")
        if (index_manifest.get("status") != "complete"
                or set(index_manifest.get("files", {})) != {"papers.parquet", "matrix.npz", "vectorizer.json"}):
            return None
        indexed_app_hash = index_manifest.get("source", {}).get("application_works_sha256")
        if indexed_app_hash is not None and indexed_app_hash != state["application_sha256"]:
            return None
        for name, evidence in index_manifest.get("files", {}).items():
            artifact = path / name
            if (name not in {"papers.parquet", "matrix.npz", "vectorizer.json"}
                    or not artifact.is_file() or artifact.stat().st_size != evidence["bytes"]
                    or file_sha256(artifact) != evidence["sha256"]):
                return None
        indexed_app = index_manifest.get("stats", {}).get("indexed_application_works")
        if indexed_app is None:
            # Backward-compatible status for indexes built before this counter
            # was recorded. Both source files were checksum-verified above.
            app_ids = set(pd.read_parquet(application, columns=["work_id"]).work_id)
            indexed = pd.read_parquet(path / "papers.parquet", columns=["work_id", "publication_year"])
            # Historical research works win ID collisions and are dated no
            # later than 2025; never count those rows as new application works.
            indexed_app = int((indexed.work_id.isin(app_ids) & (indexed.publication_year >= 2026)).sum()) if app_ids else 0
        if not isinstance(indexed_app, int) or indexed_app < 0:
            return None
        state["application_rows"] = int(manifest["application_rows"])
        state["indexed_application_works"] = indexed_app
        state["index_scope"] = index_manifest["scope"]
        return state
    except (OSError, ValueError, KeyError):
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--original-works", type=Path, default=DEFAULT_WORKS)
    parser.add_argument("--web-dir", type=Path, default=application_artifacts()["web_data"])
    parser.add_argument("--original-index", type=Path, default=application_artifacts()["paper_discovery"])
    parser.add_argument("--env-file", type=Path, default=Path(".env"),
                        help="Local ignored credential file; never copied into sync outputs")
    parser.add_argument("--from-date", type=date.fromisoformat)
    parser.add_argument("--to-date", type=date.fromisoformat)
    parser.add_argument("--lookback-days", type=int, default=3)
    parser.add_argument("--per-page", type=int, default=100)
    parser.add_argument("--max-records", type=int, default=3000)
    parser.add_argument("--max-days", type=int, default=31,
                        help="Maximum number of consecutive daily windows per invocation")
    parser.add_argument("--resume", metavar="RUN_ID")
    parser.add_argument("--execute", action="store_true", help="Perform bounded API collection; default is dry run")
    args = parser.parse_args(argv)
    state = read_sync_status(args.root)
    if args.resume:
        manifest = _read_json(_safe_run(args.root, args.resume) / "manifest.json")
        start, end = date.fromisoformat(manifest["window_start"]), date.fromisoformat(manifest["window_end"])
    else:
        start, end = _window(state, args.from_date, args.to_date, args.lookback_days)
    preview = {"mode": "publication_date_bounded_fallback_not_cdc", "from_date": str(start),
               "to_date": str(end), "filter": publication_filter(start, end),
               "root": str(args.root), "max_records_per_day": args.max_records,
               "execute": args.execute}
    if not args.resume:
        preview["daily_windows"] = [str(day) for day in daily_windows(start, end, max_days=args.max_days)]
    if not args.execute:
        print(json.dumps(preview, indent=2))
        return 0
    from ai_research_trends.env import load_project_env
    load_project_env(args.env_file)
    client = OpenAlexClient()
    if not client.api_key:
        parser.error("OPENALEX_API_KEY is required for cursor paging; key value is never logged")
    options = {"root": args.root.resolve(), "original_works": args.original_works,
               "web_dir": args.web_dir, "original_index": args.original_index,
               "client": client, "lookback_days": args.lookback_days,
               "per_page": args.per_page, "max_records": args.max_records}
    if args.resume:
        results = [sync(start=start, end=end, resume=args.resume, **options)]
    else:
        results = sync_daily(start=start, end=end, max_days=args.max_days, **options)
    print(json.dumps([{"status": result["status"], "run_id": result["run_id"],
                       "window_end": result["window_end"], "retrieved": result["retrieved"],
                       "unique_ids": result["unique_ids"], "application_rows": result["application_rows"],
                       "storage_bytes": result["storage_bytes"], "changes": result["changes"]}
                      for result in results], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
