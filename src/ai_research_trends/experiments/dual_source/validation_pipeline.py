"""RQ7.1 read-only source audit and bounded DOI-agency evidence collection."""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, urlparse

import pandas as pd
import requests

from ai_research_trends.experiments.dual_source.pipeline import DEFAULT_RUN, verify
from ai_research_trends.experiments.dual_source.validation_core import (
    REVIEW_STATUS, STRATA, classify_404, classify_conflict, license_evidence, parse_license_records,
    reviewed_correctness, select_review_sample,
)
from ai_research_trends.experiments.venue_enrichment import atomic_manifest
from ai_research_trends.preprocessing.validate_tables import file_sha256


DEFAULT_VALIDATION = Path("data/analysis/rq7_quality_validation/rq7_1_20261104_v2")
AGENCY_DOC = "https://www.doi.org/the-identifier/resources/factsheets/doi-resolution-documentation"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def save_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_manifest(path, value)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def source_hashes(source: Path) -> dict[str, str]:
    files = [source / "plan.json", source / "cohort.parquet", source / "collection_manifest.json",
             source / "processing_manifest.json", source / "evaluation.json"]
    files += sorted((source / "processed").glob("*.parquet"))
    return {str(p): file_sha256(p) for p in files}


def check_source(source: Path, expected: dict[str, str] | None = None) -> dict[str, str]:
    result = verify(source)
    if result["status"] != "PASS":
        raise ValueError("RQ7 pilot verifier failed")
    current = source_hashes(source)
    if len(current) != 14 or (expected is not None and current != expected):
        raise ValueError("RQ7 original source inventory or checksums changed")
    return current


def _write_table(path: Path, frame: pd.DataFrame) -> dict:
    tmp = path.with_name("." + path.name + ".partial")
    frame.to_parquet(tmp, index=False)
    tmp.replace(path)
    return {"path": path.name, "sha256": file_sha256(path), "rows": len(frame),
            "bytes": path.stat().st_size}


def _make_review_sheets(run: Path, sample: pd.DataFrame, canonical: pd.DataFrame,
                        conflicts: pd.DataFrame) -> dict[str, dict]:
    by_work = canonical.set_index("work_id")
    sheets = {}
    for stratum in STRATA:
        selected = sample.loc[sample.primary_review_stratum.eq(stratum)]
        rows = []
        for item in selected.itertuples():
            row = by_work.loc[item.work_id]
            field = "publisher" if stratum == STRATA[0] else "license" if stratum == STRATA[1] else "doi_404"
            original = None
            recovered = row.get(field) if field in row.index else None
            if stratum == STRATA[2]:
                options = conflicts.loc[conflicts.work_id.eq(item.work_id)].sort_values("field")
                if options.empty:
                    raise ValueError("Conflict stratum record lacks conflict evidence")
                example = options.iloc[0]
                field, original, recovered = example["field"], example["openalex_value"], example["crossref_value"]
            if stratum == STRATA[3]:
                original, recovered = item.doi, None
            evidence = license_evidence(row.license) if field == "license" else {}
            rows.append({"work_id": item.work_id, "doi": item.doi, "title": item.title,
                         "publication_year": item.publication_year, "work_type": item.work_type,
                         "cohort_group": item.cohort_group, "field_under_review": field,
                         "recovered_or_compared_value": str(recovered) if recovered is not None else None,
                         "original_provider_value": str(original) if original is not None else None,
                         "suggested_official_evidence": "DOI landing page / official venue or publisher page" if stratum != STRATA[3] else AGENCY_DOC,
                         "evidence_url": None, "evidence_retrieved_at_utc": None,
                         "automated_license_identifier": ",".join(evidence.get("license_identifiers", [])),
                         "review_decision": REVIEW_STATUS, "reviewer_id": None,
                         "reviewer_comments": None})
        path = run / f"review_sheet_{stratum.lower()}.csv"
        pd.DataFrame(rows).to_csv(path, index=False)
        sheets[stratum] = {"path": path.name, "sha256": file_sha256(path), "rows": len(rows)}
    return sheets


def prepare(source: Path = DEFAULT_RUN, run: Path = DEFAULT_VALIDATION) -> dict:
    """Create one immutable 100-work diagnostic sample, never changing the pilot."""
    if run.exists():
        raise FileExistsError(f"Validation run already exists: {run}")
    hashes = check_source(source)
    canonical = pd.read_parquet(source / "processed/canonical_works.parquet")
    conflicts = pd.read_parquet(source / "processed/metadata_conflicts.parquet")
    links = pd.read_parquet(source / "processed/provider_links.parquet")
    baseline = load_json(source / "evaluation.json")
    if len(canonical) != 1500 or len(conflicts) != baseline["metadata_conflict_count"]:
        raise ValueError("Pilot baseline totals changed")
    sample = select_review_sample(canonical, conflicts)
    full = conflicts.copy()
    classified = pd.DataFrame([classify_conflict(r) for r in full.to_dict("records")])
    full = pd.concat([full.reset_index(drop=True), classified], axis=1)
    if len(full) != len(conflicts) or not full.classification.notna().all():
        raise ValueError("Conflict conservation failed")
    run.mkdir(parents=True)
    sample_entry = _write_table(run / "review_sample.parquet", sample)
    conflict_entry = _write_table(run / "classified_conflicts.parquet", full)
    statuses = links.loc[links.match_status.eq("CROSSREF_NOT_FOUND"), ["work_id", "doi", "crossref_raw_path"]]
    cases = sample.loc[sample.primary_review_stratum.eq(STRATA[3]), ["work_id", "doi"]].merge(
        statuses, on=["work_id", "doi"], validate="one_to_one")
    case_rows = []
    collection = load_json(source / "collection_manifest.json")
    cross_entries = {e["identifier"]: e for e in collection["crossref"]}
    for row in cases.itertuples():
        entry = cross_entries.get(row.doi)
        if entry is None or entry["status_code"] != 404 or entry["path"] != row.crossref_raw_path:
            raise ValueError("404 review case lacks stored HTTP evidence")
        raw_path = source / entry["path"]
        if file_sha256(raw_path) != entry["sha256"]:
            raise ValueError("404 raw response checksum changed")
        case_rows.append({"work_id": row.work_id, "doi": row.doi,
                          "stored_crossref_status": 404, "stored_crossref_sha256": entry["sha256"],
                          "agency": None, "agency_status": "NOT_CHECKED",
                          "reason": classify_404(row.doi, 404, None)})
    cases_entry = _write_table(run / "doi_404_cases.parquet", pd.DataFrame(case_rows))
    sheets = _make_review_sheets(run, sample, canonical, conflicts)
    source_manifest = {"source_run": str(source), "captured_at_utc": utc_now(),
                       "baseline_verifier": verify(source), "source_sha256": hashes,
                       "read_only_source": True}
    save_json(run / "source_evidence_manifest.json", source_manifest)
    strata = {label: {"selected": int(sample.primary_review_stratum.eq(label).sum()),
                      "group_A": int((sample.primary_review_stratum.eq(label) & sample.cohort_group.eq("A_GENERAL")).sum()),
                      "group_B": int((sample.primary_review_stratum.eq(label) & sample.cohort_group.eq("B_TARGETED_MISSINGNESS")).sum())}
              for label in STRATA}
    save_json(run / "sampling_strata.json", {"seed": 20261104, "target": 100,
              "order": list(STRATA), "shortfall_policy": "fail; no silent redistribution",
              "strata": strata, "eligibility": {
                  "S1_PUBLISHER": int(canonical.publisher_source.eq("crossref").sum()),
                  "S2_LICENSE": int(canonical.license_source.eq("crossref").sum()),
                  "S3_CONFLICT": int(canonical.work_id.isin(conflicts.work_id).sum()),
                  "S4_CROSSREF_404": int(canonical.match_status.eq("CROSSREF_NOT_FOUND").sum())},
              "diagnostic_not_population_representative": True})
    manifest = {"run_id": run.name, "created_at_utc": utc_now(), "source_run": str(source),
                "seed": 20261104, "status": "prepared", "reviewer_status": REVIEW_STATUS,
                "source_manifest_sha256": file_sha256(run / "source_evidence_manifest.json"),
                "sample": sample_entry, "conflicts": conflict_entry, "doi_404_cases": cases_entry,
                "review_sheets": sheets, "agency_request_cap": 20,
                "license_url_request_cap": 10,
                "publisher_page_request_cap": 0,
                "agency_requests_attempted": 0, "agency_evidence": [],
                "license_url_requests_attempted": 0, "license_url_evidence": [],
                "human_decisions_count": 0}
    save_json(run / "review_sample_manifest.json", manifest)
    return {"status": "PREPARED", "selected": len(sample), "strata": strata,
            "conflicts_classified": len(full), "source_files_verified": len(hashes)}


def verify_validation(run: Path = DEFAULT_VALIDATION, *, check_source_now: bool = True) -> dict:
    manifest = load_json(run / "review_sample_manifest.json")
    source_manifest = load_json(run / "source_evidence_manifest.json")
    if file_sha256(run / "source_evidence_manifest.json") != manifest["source_manifest_sha256"]:
        raise ValueError("Source evidence manifest changed")
    if check_source_now:
        check_source(Path(manifest["source_run"]), source_manifest["source_sha256"])
    for key in ("sample", "conflicts", "doi_404_cases"):
        entry = manifest[key]
        path = run / entry["path"]
        if file_sha256(path) != entry["sha256"] or len(pd.read_parquet(path)) != entry["rows"]:
            raise ValueError(f"RQ7.1 artifact changed: {path}")
    for entry in manifest["review_sheets"].values():
        if file_sha256(run / entry["path"]) != entry["sha256"]:
            raise ValueError("Private review sheet changed; preserve and audit separately")
    sample = pd.read_parquet(run / manifest["sample"]["path"])
    classified = pd.read_parquet(run / manifest["conflicts"]["path"])
    if len(sample) != sample.work_id.nunique() or sample.primary_review_stratum.value_counts().reindex(STRATA).to_list() != [30, 30, 20, 20]:
        raise ValueError("Review sample stratum invariant failed")
    if len(classified) != 2597 or classified.classification.isna().any():
        raise ValueError("Conflict conservation failed")
    for evidence in manifest["agency_evidence"]:
        if file_sha256(run / evidence["path"]) != evidence["sha256"]:
            raise ValueError("DOI agency response checksum changed")
    if manifest.get("official_source_checks"):
        entry = manifest["official_source_checks"]
        if file_sha256(run / entry["path"]) != entry["sha256"]:
            raise ValueError("Official-source evidence checksum changed")
    if manifest.get("license_url_requests_attempted", 0) > manifest.get("license_url_request_cap", 10):
        raise ValueError("License URL request budget exceeded")
    return {"status": "PASS", "source_sha256_verified": len(source_manifest["source_sha256"]),
            "review_sample": len(sample), "conflicts_accounted": len(classified),
            "agency_requests_attempted": manifest["agency_requests_attempted"],
            "agency_evidence_files": len(manifest["agency_evidence"])}


def check_agencies(run: Path = DEFAULT_VALIDATION, *, max_requests: int = 20) -> dict:
    """At most 20 new DOI Foundation requests; each attempt is checkpointed first."""
    verify_validation(run)
    manifest_path = run / "review_sample_manifest.json"
    manifest = load_json(manifest_path)
    cases_path = run / manifest["doi_404_cases"]["path"]
    cases = pd.read_parquet(cases_path)
    if max_requests < 0 or max_requests > manifest["agency_request_cap"]:
        raise ValueError("Agency request budget exceeded")
    existing = {e["work_id"] for e in manifest["agency_evidence"]}
    session = requests.Session()
    session.headers.update({"User-Agent": "AI-Research-Trends/0.1 (bounded academic DOI agency audit)",
                            "Accept": "application/json"})
    for row in cases.itertuples():
        if row.work_id in existing or manifest["agency_requests_attempted"] >= max_requests:
            continue
        manifest["agency_requests_attempted"] += 1
        save_json(manifest_path, manifest)
        url = "https://doi.org/doiRA/" + quote(row.doi.removeprefix("https://doi.org/"), safe="")
        started = utc_now()
        status, agency, error, raw = None, None, None, b""
        try:
            response = session.get(url, timeout=15)
            status, raw = response.status_code, response.content
            if status == 200:
                payload = response.json()
                agency = payload[0].get("RA") if isinstance(payload, list) and len(payload) == 1 and isinstance(payload[0], dict) else None
        except (requests.RequestException, ValueError, IndexError) as exc:
            error = type(exc).__name__
        evidence_path = run / "agency_raw" / (row.work_id.rsplit("/", 1)[-1] + ".json")
        evidence_path.parent.mkdir(exist_ok=True)
        # A failed transport still receives a checkpoint; no fabricated response body.
        if evidence_path.exists():
            raise FileExistsError("Uncheckpointed agency evidence; inspect manually")
        tmp = evidence_path.with_name("." + evidence_path.name + ".partial")
        tmp.write_bytes(raw)
        tmp.replace(evidence_path)
        manifest["agency_evidence"].append({"work_id": row.work_id, "doi": row.doi,
             "url": url, "requested_at_utc": started, "http_status": status,
             "agency": agency, "error_type": error,
             "path": str(evidence_path.relative_to(run)), "sha256": file_sha256(evidence_path),
             "reason": classify_404(row.doi, 404, agency)})
        save_json(manifest_path, manifest)
        time.sleep(0.3)
    return {"attempted": manifest["agency_requests_attempted"],
            "with_evidence": len(manifest["agency_evidence"]),
            "reasons": dict(Counter(e["reason"] for e in manifest["agency_evidence"]))}


def reclassify(run: Path = DEFAULT_VALIDATION) -> dict:
    """Revise derived taxonomy only, retaining old hash and immutable pilot evidence."""
    verify_validation(run)
    path = run / "review_sample_manifest.json"
    manifest = load_json(path)
    source = Path(manifest["source_run"])
    original = pd.read_parquet(source / "processed/metadata_conflicts.parquet")
    classified = pd.concat([original.reset_index(drop=True),
                            pd.DataFrame([classify_conflict(r) for r in original.to_dict("records")])], axis=1)
    previous = manifest["conflicts"]["sha256"]
    entry = _write_table(run / "classified_conflicts.parquet", classified)
    if previous != entry["sha256"]:
        manifest.setdefault("classification_revisions", []).append({"previous_sha256": previous,
                        "new_sha256": entry["sha256"], "changed_at_utc": utc_now(),
                        "reason": "distinguish overlapping ISSN coverage from potential semantic disagreement"})
    manifest["conflicts"] = entry
    save_json(path, manifest)
    return {"classified": len(classified), "sha256": entry["sha256"],
            "class_counts": classified.classification.value_counts().to_dict()}


def check_license_urls(run: Path = DEFAULT_VALIDATION, *, max_requests: int = 10) -> dict:
    """Probe a tiny allowlisted set of policy URLs without following redirects."""
    verify_validation(run)
    path = run / "review_sample_manifest.json"
    manifest = load_json(path)
    if max_requests < 0 or max_requests > manifest.get("license_url_request_cap", 10):
        raise ValueError("License URL request budget exceeded")
    source = Path(manifest["source_run"])
    sample = pd.read_parquet(run / manifest["sample"]["path"])
    selected = set(sample.loc[sample.primary_review_stratum.eq("S2_LICENSE"), "work_id"])
    canonical = pd.read_parquet(source / "processed/canonical_works.parquet")
    allowed = ("elsevier.com", "springer.com", "springernature.com", "wiley.com",
               "ieee.org", "acm.org", "aaai.org", "iop.org", "aps.org", "creativecommons.org")
    urls = []
    for row in canonical.loc[canonical.work_id.isin(selected)].itertuples():
        for record in parse_license_records(row.license):
            url = record.get("URL")
            host = urlparse(url).hostname if isinstance(url, str) else None
            if host and any(host == domain or host.endswith("." + domain) for domain in allowed):
                urls.append((row.work_id, url))
    existing = {(e["work_id"], e["url"]) for e in manifest.get("license_url_evidence", [])}
    session = requests.Session()
    session.headers.update({"User-Agent": "AI-Research-Trends/0.1 (bounded license URL metadata audit)"})
    for wid, url in sorted(set(urls)):
        if manifest.get("license_url_requests_attempted", 0) >= max_requests:
            break
        if (wid, url) in existing:
            continue
        manifest["license_url_requests_attempted"] = manifest.get("license_url_requests_attempted", 0) + 1
        save_json(path, manifest)
        status, error = None, None
        try:
            response = session.head(url, allow_redirects=False, timeout=15)
            status = response.status_code
        except requests.RequestException as exc:
            error = type(exc).__name__
        manifest.setdefault("license_url_evidence", []).append({"work_id": wid, "url": url,
            "requested_at_utc": utc_now(), "http_status": status, "error_type": error,
            "reachable_directly": status is not None and 200 <= status < 300,
            "license_semantics_verified": False, "reuse_rights_status": "UNKNOWN"})
        save_json(path, manifest)
        time.sleep(0.3)
    return {"attempted": manifest.get("license_url_requests_attempted", 0),
            "evidence": len(manifest.get("license_url_evidence", [])),
            "direct_2xx": sum(x["reachable_directly"] for x in manifest.get("license_url_evidence", []))}


def refresh_review_sheets(run: Path = DEFAULT_VALIDATION) -> dict:
    """Repair only unreviewed private sheets; preserve prior hashes in manifest."""
    verify_validation(run)
    path = run / "review_sample_manifest.json"
    manifest = load_json(path)
    if manifest["human_decisions_count"] != 0 or manifest["reviewer_status"] != REVIEW_STATUS:
        raise ValueError("Never overwrite completed or modified human reviews")
    source = Path(manifest["source_run"])
    sample = pd.read_parquet(run / manifest["sample"]["path"])
    canonical = pd.read_parquet(source / "processed/canonical_works.parquet")
    conflicts = pd.read_parquet(source / "processed/metadata_conflicts.parquet")
    prior = {k: v["sha256"] for k, v in manifest["review_sheets"].items()}
    manifest["review_sheets"] = _make_review_sheets(run, sample, canonical, conflicts)
    manifest.setdefault("sheet_revisions", []).append({"previous_sha256": prior,
        "new_sha256": {k: v["sha256"] for k, v in manifest["review_sheets"].items()},
        "changed_at_utc": utc_now(), "reason": "populate conflict source values in blank sheets"})
    save_json(path, manifest)
    return {"status": "REFRESHED_UNREVIEWED_SHEETS", "sheets": len(manifest["review_sheets"])}


def register_official_evidence(run: Path = DEFAULT_VALIDATION) -> dict:
    """Register bounded, locally stored source-backed checks without human claims."""
    verify_validation(run)
    path = run / "review_sample_manifest.json"
    manifest = load_json(path)
    evidence_path = run / "official_source_checks.json"
    evidence = load_json(evidence_path)
    sample = pd.read_parquet(run / manifest["sample"]["path"])
    selected = sample.loc[sample.primary_review_stratum.eq(STRATA[0])].set_index("work_id")
    for check in evidence.get("checks", []):
        wid = check.get("work_id")
        if wid not in selected.index or check.get("doi") != selected.loc[wid, "doi"]:
            raise ValueError("Official-source check is outside publisher review sample")
        if check.get("human_adjudicated") is not False or check.get("status") != "SOURCE_BACKED_CORRECT":
            raise ValueError("Automated source check cannot claim human adjudication")
        urls = check.get("evidence_urls")
        if not isinstance(urls, list) or len(urls) < 2 or not all(u.startswith("https://") for u in urls):
            raise ValueError("Official source links incomplete")
    manifest["official_source_checks"] = {"path": evidence_path.name,
        "sha256": file_sha256(evidence_path), "checks": len(evidence.get("checks", [])),
        "human_adjudications": 0}
    save_json(path, manifest)
    return {"registered_source_backed_checks": len(evidence.get("checks", [])),
            "human_adjudications": 0}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("prepare", "agency", "license-urls", "reclassify", "refresh-sheets", "register-official", "verify"))
    parser.add_argument("--source", type=Path, default=DEFAULT_RUN)
    parser.add_argument("--run", type=Path, default=DEFAULT_VALIDATION)
    parser.add_argument("--max-agency-requests", type=int, default=20)
    parser.add_argument("--max-license-requests", type=int, default=10)
    args = parser.parse_args()
    result = (prepare(args.source, args.run) if args.stage == "prepare" else
              check_agencies(args.run, max_requests=args.max_agency_requests) if args.stage == "agency" else
              check_license_urls(args.run, max_requests=args.max_license_requests) if args.stage == "license-urls" else
              reclassify(args.run) if args.stage == "reclassify" else
              refresh_review_sheets(args.run) if args.stage == "refresh-sheets" else
              register_official_evidence(args.run) if args.stage == "register-official" else
              verify_validation(args.run))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
