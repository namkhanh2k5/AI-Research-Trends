"""Small OpenAlex REST client with retries and auditable raw-response storage."""

from __future__ import annotations

import hashlib
import json
import math
import os
import random
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping

import requests


RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
RATE_LIMIT_HEADERS = (
    "X-RateLimit-Limit",
    "X-RateLimit-Remaining",
    "X-RateLimit-Credits-Used",
    "X-RateLimit-Reset",
)


class OpenAlexError(RuntimeError):
    """Raised when an OpenAlex request cannot be completed safely."""


@dataclass(frozen=True)
class PageEnvelope:
    """Validated shape of an OpenAlex list or grouped response."""

    meta: dict[str, Any]
    results: list[dict[str, Any]]
    group_by: list[dict[str, Any]]

    @property
    def next_cursor(self) -> str | None:
        value = self.meta.get("next_cursor")
        return value if isinstance(value, str) and value else None


@dataclass(frozen=True)
class StoredPage:
    page_number: int
    path: str
    sha256: str
    retrieved_at_utc: str
    status_code: int
    result_count: int
    rate_limit: dict[str, str]


@dataclass(frozen=True)
class CollectionSummary:
    requested_records: int
    raw_records: int
    unique_records: int
    duplicate_records: int
    complete_for_requested_sample: bool
    run_directory: str
    raw_jsonl_path: str
    jsonl_path: str
    manifest_path: str


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def canonical_openalex_id(value: str) -> str:
    """Return a canonical absolute OpenAlex ID suitable for deduplication."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError("OpenAlex ID must be a non-empty string")
    identifier = value.strip().rstrip("/").split("/")[-1].upper()
    if len(identifier) < 2 or identifier[0] not in "WASIFTPKC" or not identifier[1:].isdigit():
        raise ValueError(f"Invalid OpenAlex ID: {value!r}")
    return f"https://openalex.org/{identifier}"


def canonical_work_id(value: str) -> str:
    """Return a canonical Work ID and reject all other OpenAlex entity IDs."""
    canonical = canonical_openalex_id(value)
    if not canonical.removeprefix("https://openalex.org/").startswith("W"):
        raise ValueError(f"Expected an OpenAlex Work ID, got: {value!r}")
    return canonical


def parse_list_response(payload: Any) -> PageEnvelope:
    """Validate and parse list-response containers without assuming non-null metadata."""
    if not isinstance(payload, dict):
        raise OpenAlexError("OpenAlex list response must be a JSON object")
    meta = payload.get("meta")
    results = payload.get("results", [])
    groups = payload.get("group_by", [])
    if not isinstance(meta, dict):
        raise OpenAlexError("OpenAlex list response is missing a valid 'meta' object")
    if not isinstance(results, list) or not all(isinstance(row, dict) for row in results):
        raise OpenAlexError("OpenAlex list response has invalid 'results'")
    if not isinstance(groups, list) or not all(isinstance(row, dict) for row in groups):
        raise OpenAlexError("OpenAlex list response has invalid 'group_by'")
    return PageEnvelope(meta=meta, results=results, group_by=groups)


def validate_sample_page(
    payload: Any,
    *,
    requested_records: int,
    page_number: int,
    per_page: int,
) -> PageEnvelope:
    """Validate sample metadata and reject short, extra, or missing basic pages."""
    envelope = parse_list_response(payload)
    count = envelope.meta.get("count")
    if count != requested_records:
        raise OpenAlexError(
            f"Sample meta.count={count!r} does not match requested size {requested_records}"
        )
    expected = min(per_page, requested_records - ((page_number - 1) * per_page))
    if expected <= 0:
        raise OpenAlexError(f"Unexpected sample page number {page_number}")
    if len(envelope.results) != expected:
        raise OpenAlexError(
            f"Sample page {page_number} contains {len(envelope.results)} records; "
            f"expected {expected}"
        )
    return envelope


class OpenAlexClient:
    """HTTP client implementing current OpenAlex API limits conservatively."""

    def __init__(
        self,
        api_key: str | None = None,
        contact_email: str | None = None,
        *,
        base_url: str = "https://api.openalex.org",
        timeout_seconds: float = 30.0,
        max_retries: int = 5,
        min_interval_seconds: float = 0.11,
        session: requests.Session | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.api_key = api_key or os.getenv("OPENALEX_API_KEY") or None
        self.contact_email = contact_email or os.getenv("OPENALEX_CONTACT_EMAIL") or None
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.min_interval_seconds = min_interval_seconds
        self.session = session or requests.Session()
        self.sleep = sleep
        self._last_request_monotonic = 0.0

        user_agent = "ai-research-trends/0.1 (university bibliometric research)"
        if self.contact_email:
            user_agent = f"{user_agent}; contact={self.contact_email}"
        self.session.headers.update({"User-Agent": user_agent, "Accept": "application/json"})
        if self.api_key:
            self.session.headers.update({"Authorization": f"Bearer {self.api_key}"})

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_monotonic
        wait = self.min_interval_seconds - elapsed
        if wait > 0:
            self.sleep(wait)

    def request(self, path: str, params: Mapping[str, Any] | None = None) -> requests.Response:
        """GET an endpoint, retrying transient errors with bounded exponential backoff."""
        url = path if path.startswith("http") else f"{self.base_url}/{path.lstrip('/')}"
        last_error: Exception | None = None

        for attempt in range(self.max_retries + 1):
            self._throttle()
            try:
                response = self.session.get(url, params=dict(params or {}), timeout=self.timeout_seconds)
                self._last_request_monotonic = time.monotonic()
            except requests.RequestException as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    break
                self.sleep(min(60.0, (2**attempt) + random.random()))
                continue

            if response.status_code not in RETRYABLE_STATUS_CODES:
                if response.status_code == 401:
                    raise OpenAlexError(
                        "OpenAlex returned 401. A verified API key is required for cursor "
                        "paging beyond its first page; set OPENALEX_API_KEY."
                    )
                if response.status_code >= 400:
                    raise OpenAlexError(self._format_http_error(response))
                return response

            if attempt >= self.max_retries:
                raise OpenAlexError(self._format_http_error(response))
            retry_after = response.headers.get("Retry-After")
            try:
                delay = float(retry_after) if retry_after is not None else 2**attempt
            except ValueError:
                delay = 2**attempt
            self.sleep(min(60.0, max(0.0, delay) + random.random() / 10))

        raise OpenAlexError(f"OpenAlex request failed after retries: {last_error}")

    @staticmethod
    def _format_http_error(response: requests.Response) -> str:
        body = response.text[:500].replace("\n", " ")
        return f"OpenAlex HTTP {response.status_code} for {response.url}: {body}"

    def get_json(self, path: str, params: Mapping[str, Any] | None = None) -> dict[str, Any]:
        response = self.request(path, params)
        try:
            payload = response.json()
        except requests.JSONDecodeError as exc:
            raise OpenAlexError(f"OpenAlex returned invalid JSON for {response.url}") from exc
        if not isinstance(payload, dict):
            raise OpenAlexError(f"Expected a JSON object from {response.url}")
        return payload

    def iter_basic_pages(
        self,
        path: str,
        params: Mapping[str, Any],
        *,
        expected_records: int,
        per_page: int = 100,
    ) -> Iterator[tuple[int, requests.Response, dict[str, Any]]]:
        """Yield every page of a <=10,000-result query without silent truncation."""
        if not 1 <= per_page <= 100:
            raise ValueError("OpenAlex currently supports per_page values from 1 to 100")
        if expected_records > 10_000:
            raise ValueError("Basic paging cannot retrieve more than 10,000 results")

        total_pages = math.ceil(expected_records / per_page)
        for page_number in range(1, total_pages + 1):
            page_params = {**params, "per_page": per_page, "page": page_number}
            response = self.request(path, page_params)
            payload = response.json()
            validate_sample_page(
                payload,
                requested_records=expected_records,
                page_number=page_number,
                per_page=per_page,
            )
            yield page_number, response, payload

    def collect_sample(
        self,
        *,
        query_filter: str,
        requested_records: int,
        seed: int,
        raw_root: str | Path,
        interim_root: str | Path,
        select: str | None = None,
    ) -> CollectionSummary:
        """Collect all pages of a deterministic server-side sample and its provenance."""
        if not 1 <= requested_records <= 10_000:
            raise ValueError("OpenAlex sample must contain between 1 and 10,000 records")

        run_id = datetime.now(timezone.utc).strftime("pilot_%Y%m%dT%H%M%SZ")
        raw_dir = Path(raw_root) / run_id
        interim_dir = Path(interim_root) / run_id
        raw_dir.mkdir(parents=True, exist_ok=False)
        interim_dir.mkdir(parents=True, exist_ok=False)

        params: dict[str, Any] = {
            "filter": query_filter,
            "sample": requested_records,
            "seed": seed,
        }
        if select:
            params["select"] = select

        pages: list[StoredPage] = []
        records: list[dict[str, Any]] = []
        for page_number, response, payload in self.iter_basic_pages(
            "works", params, expected_records=requested_records, per_page=100
        ):
            raw_bytes = response.content
            raw_path = raw_dir / f"page_{page_number:04d}.json"
            raw_path.write_bytes(raw_bytes)
            digest = hashlib.sha256(raw_bytes).hexdigest()
            result_count = len(payload["results"])
            pages.append(
                StoredPage(
                    page_number=page_number,
                    path=str(raw_path),
                    sha256=digest,
                    retrieved_at_utc=utc_now(),
                    status_code=response.status_code,
                    result_count=result_count,
                    rate_limit={
                        name: response.headers[name]
                        for name in RATE_LIMIT_HEADERS
                        if name in response.headers
                    },
                )
            )
            records.extend(payload["results"])

        seen: set[str] = set()
        unique_records: list[dict[str, Any]] = []
        invalid_ids = 0
        for record in records:
            try:
                work_id = canonical_work_id(record.get("id", ""))
            except ValueError:
                invalid_ids += 1
                continue
            if work_id not in seen:
                seen.add(work_id)
                unique_records.append(record)

        raw_jsonl_path = raw_dir / "works.jsonl"
        with raw_jsonl_path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")))
                handle.write("\n")

        jsonl_path = interim_dir / "works.jsonl"
        with jsonl_path.open("w", encoding="utf-8") as handle:
            for record in unique_records:
                handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")))
                handle.write("\n")

        raw_count = len(records)
        complete = len(unique_records) == requested_records and invalid_ids == 0
        manifest = {
            "schema_version": 1,
            "run_id": run_id,
            "created_at_utc": utc_now(),
            "endpoint": f"{self.base_url}/works",
            "authentication": "bearer_api_key" if self.api_key else "anonymous",
            "query_parameters": params,
            "supported_per_page": 100,
            "requested_records": requested_records,
            "raw_records": raw_count,
            "valid_unique_records": len(unique_records),
            "duplicate_records": raw_count - len(unique_records) - invalid_ids,
            "invalid_or_missing_work_ids": invalid_ids,
            "complete_for_requested_sample": complete,
            "population_complete": False,
            "sampling_note": (
                "Deterministic OpenAlex server-side sample; it is not the complete population. "
                "HTTP bodies are byte-identical in page files; works.jsonl is a lossless "
                "record-level extraction of each page's results array."
            ),
            "raw_records_jsonl": {
                "path": str(raw_jsonl_path),
                "sha256": hashlib.sha256(raw_jsonl_path.read_bytes()).hexdigest(),
                "records": raw_count,
            },
            "pages": [page.__dict__ for page in pages],
        }
        manifest_path = raw_dir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

        return CollectionSummary(
            requested_records=requested_records,
            raw_records=raw_count,
            unique_records=len(unique_records),
            duplicate_records=raw_count - len(unique_records) - invalid_ids,
            complete_for_requested_sample=complete,
            run_directory=str(raw_dir),
            raw_jsonl_path=str(raw_jsonl_path),
            jsonl_path=str(jsonl_path),
            manifest_path=str(manifest_path),
        )
