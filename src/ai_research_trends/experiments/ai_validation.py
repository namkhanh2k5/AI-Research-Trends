"""Isolated, blind AI-assisted topic audit and bounded official-source publisher audit.

This module never reads restricted answer keys, model predictions, or sealed-test data.
Record-level output belongs only under the Git-ignored data/analysis tree.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
from collections import Counter
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

import pandas as pd
import requests
import yaml

from ai_research_trends.ml.human_review_workflow import validate_blind_sheet, validate_package
from ai_research_trends.preprocessing.validate_tables import file_sha256


RUN_ROOT = Path("data/analysis/ai_assisted_validation")
HUMAN_PACKAGE = Path("data/analysis/finalization_p2_human_review_20261101_v1")
PUBLISHER_SHEET = Path("data/analysis/rq7_quality_validation/rq7_1_20261104_v2/review_sheet_s1_publisher.csv")
CATALOGUE = Path("config/phase6b_catalogue.yaml")
TOPIC_CHOICES = {"NONE", "UNCLEAR"}
PUBLISHER_STATUSES = {
    "SOURCE_BACKED_CORRECT", "SOURCE_BACKED_ACCEPTABLE_ALIAS", "SOURCE_BACKED_INCORRECT",
    "AMBIGUOUS", "INSUFFICIENT_EVIDENCE", "SOURCE_ACCESS_BLOCKED",
}
SOURCE_BACKED = {"SOURCE_BACKED_CORRECT", "SOURCE_BACKED_ACCEPTABLE_ALIAS", "SOURCE_BACKED_INCORRECT"}
CONFIDENCES = {"HIGH", "MEDIUM", "LOW", "INSUFFICIENT_EVIDENCE"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name("." + path.name + ".partial")
    tmp.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def require_private_output(path: Path) -> None:
    root = RUN_ROOT.resolve()
    target = path.resolve()
    if target == root or root not in target.parents:
        raise ValueError(f"Record-level AI audit outputs must stay under {RUN_ROOT}")


def atomic_parquet(path: Path, frame: pd.DataFrame) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name("." + path.name + ".partial")
    frame.to_parquet(tmp, index=False)
    tmp.replace(path)
    return {"path": str(path), "rows": len(frame), "bytes": path.stat().st_size,
            "sha256": file_sha256(path)}


def load_blind_inputs(package: Path = HUMAN_PACKAGE, catalogue_path: Path = CATALOGUE
                      ) -> tuple[dict[str, pd.DataFrame], pd.DataFrame, dict[str, str]]:
    """Verify frozen inputs without touching any answer key or model prediction file."""
    validated = validate_package(package)
    if not validated["valid"] or validated["human_statistics"] != "pending":
        raise ValueError("Human package state is not the expected blind pending state")
    catalogue = yaml.safe_load(catalogue_path.read_text(encoding="utf-8"))
    metadata_path = Path(catalogue["source_metadata_csv"])
    if file_sha256(metadata_path) != catalogue["source_metadata_sha256"]:
        raise ValueError("Frozen topic metadata hash mismatch")
    metadata = pd.read_csv(metadata_path)
    allowed = set(catalogue["catalogue_b"])
    topics = metadata.loc[metadata.short_id.isin(allowed)].copy()
    if len(topics) != 14 or topics.short_id.duplicated().any():
        raise ValueError("Frozen 14-topic catalogue incomplete")
    frames = {}
    hashes = {str(catalogue_path): file_sha256(catalogue_path),
              str(metadata_path): file_sha256(metadata_path),
              str(package / "manifest.json"): file_sha256(package / "manifest.json")}
    for kind, expected in (("calibration", 40), ("evaluation", 100)):
        path = package / "reviewer_a" / f"blind_{kind}.csv"
        frame = pd.read_csv(path)
        result = validate_blind_sheet(frame, allowed)
        if result["examples"] != expected:
            raise ValueError(f"Blind {kind} count changed")
        frames[kind] = frame
        hashes[str(path)] = file_sha256(path)
    return frames, topics, hashes


def validate_topic_decisions(decisions: pd.DataFrame, blind: pd.DataFrame,
                             allowed: set[str]) -> pd.DataFrame:
    required = {"example_id", "selected_topic_id", "second_plausible_topic_id",
                "confidence_category", "evidence_summary", "ambiguity_notes"}
    if not required.issubset(decisions.columns):
        raise ValueError("AI decisions lack required columns")
    if decisions.example_id.duplicated().any() or set(decisions.example_id) != set(blind.example_id):
        raise ValueError("AI decisions must cover exactly the blind examples once")
    if not decisions.selected_topic_id.isin(allowed | TOPIC_CHOICES).all():
        raise ValueError("Invalid selected topic")
    second = decisions.second_plausible_topic_id.dropna()
    if not second.isin(allowed).all():
        raise ValueError("Invalid secondary topic")
    if not decisions.confidence_category.isin(CONFIDENCES).all():
        raise ValueError("Invalid qualitative confidence")
    if decisions.evidence_summary.isna().any() or decisions.evidence_summary.astype(str).str.len().lt(12).any():
        raise ValueError("Every AI decision needs substantive evidence")
    if decisions.loc[decisions.selected_topic_id.eq("UNCLEAR"), "confidence_category"].ne(
            "INSUFFICIENT_EVIDENCE").any():
        raise ValueError("UNCLEAR requires insufficient evidence")
    if decisions.loc[decisions.selected_topic_id.isin(TOPIC_CHOICES),
                     "second_plausible_topic_id"].notna().any():
        raise ValueError("NONE/UNCLEAR cannot claim a secondary catalogue topic")
    if (decisions.second_plausible_topic_id == decisions.selected_topic_id).any():
        raise ValueError("Primary and secondary topics cannot be the same")
    return decisions.sort_values("example_id").reset_index(drop=True)


def topic_metrics(frame: pd.DataFrame) -> dict:
    values = frame.selected_topic_id.value_counts().sort_index().to_dict()
    return {"assessed": len(frame), "single_catalogue_choice": int(frame.selected_topic_id.str.startswith("T").sum()),
            "none": int(frame.selected_topic_id.eq("NONE").sum()),
            "unclear": int(frame.selected_topic_id.eq("UNCLEAR").sum()),
            "confidence": dict(Counter(frame.confidence_category)),
            "secondary_plausible": int(frame.second_plausible_topic_id.notna().sum()),
            "ambiguous_or_overlapping": int(frame.ambiguity_notes.notna().sum()),
            "topic_distribution": {str(k): int(v) for k, v in values.items()},
            "human_validated_correctness": "NOT_VERIFIED"}


def validate_scope(scope: pd.DataFrame, topics: pd.DataFrame) -> pd.DataFrame:
    required = {"topic_id", "scope_status", "boundary_note", "overlap_note"}
    allowed = {"CLEARLY_DEFINED", "MOSTLY_CLEAR", "OVERLAPPING", "AMBIGUOUS_SCOPE",
               "NEEDS_EXPERT_REVIEW"}
    if not required.issubset(scope.columns) or len(scope) != 14:
        raise ValueError("Scope assessment must cover all fourteen topics")
    if scope.topic_id.duplicated().any() or set(scope.topic_id) != set(topics.short_id):
        raise ValueError("Scope assessment differs from frozen catalogue")
    if not scope.scope_status.isin(allowed).all() or scope.boundary_note.isna().any():
        raise ValueError("Scope assessments lack valid status and boundary note")
    result = scope.merge(topics[["short_id", "name", "description", "subfield_id", "source_url"]],
                         left_on="topic_id", right_on="short_id", validate="one_to_one")
    return result.drop(columns="short_id").sort_values("topic_id").reset_index(drop=True)


def freeze_topic_assessments(package: Path, scope_path: Path, calibration_path: Path,
                             evaluation_path: Path, output: Path,
                             *, model_id: str = "OpenAI ChatGPT Codex (exact backend version unavailable)",
                             prompt_version: str = "ai-validation-v1") -> dict:
    if output.exists():
        raise FileExistsError("AI topic assessment run already frozen")
    frames, topics, source_hashes = load_blind_inputs(package)
    allowed = set(topics.short_id)
    scope = validate_scope(pd.read_csv(scope_path, sep="\t"), topics)
    decisions = {}
    combined = None
    if calibration_path == evaluation_path:
        combined = pd.read_csv(calibration_path, sep="\t", keep_default_na=True)
        expected_ids = set(frames["calibration"].example_id) | set(frames["evaluation"].example_id)
        if len(combined) != 140 or combined.example_id.duplicated().any() or set(combined.example_id) != expected_ids:
            raise ValueError("Combined AI sheet must cover all 140 blind examples once")
    for name, path in (("calibration", calibration_path), ("evaluation", evaluation_path)):
        frame = (combined.loc[combined.example_id.isin(set(frames[name].example_id))].copy()
                 if combined is not None else pd.read_csv(path, sep="\t", keep_default_na=True))
        frame = validate_topic_decisions(frame, frames[name], allowed)
        frame["selected_topic_name"] = frame.selected_topic_id.map(
            topics.set_index("short_id").name).where(frame.selected_topic_id.isin(allowed), None)
        frame["decision"] = frame.selected_topic_id.map(
            lambda item: "ONE_TOPIC" if item in allowed else item)
        frame["alternative_topic_reason"] = frame.ambiguity_notes
        frame["assessment_method"] = "assistant_semantic_review_of_blind_title_abstract"
        frame["reviewer_type"] = "AI_ASSISTED"
        decisions[name] = frame
    output.mkdir(parents=True, exist_ok=False)
    artifacts = {}
    artifacts["topic_scope_assessment"] = atomic_parquet(output / "topic_scope_assessment.parquet", scope)
    for name, frame in decisions.items():
        artifacts[f"{name}_ai_assessments"] = atomic_parquet(output / f"{name}_ai_assessments.parquet", frame)
    metrics = {name: topic_metrics(frame) for name, frame in decisions.items()}
    atomic_json(output / "topic_metrics.json", metrics)
    artifacts["topic_metrics"] = {"path": str(output / "topic_metrics.json"),
                                  "sha256": file_sha256(output / "topic_metrics.json")}
    manifest = {"status": "frozen_ai_assessment_human_pending", "frozen_at_utc": utc_now(),
                "model_id": model_id, "exact_backend_version": "NOT_AVAILABLE",
                "prompt_version": prompt_version,
                "assessment_method": "Assistant reviewed blind titles and abstracts; not a calibrated classifier or human rater",
                "input_hashes": {**source_hashes,
                                 str(scope_path): file_sha256(scope_path),
                                 str(calibration_path): file_sha256(calibration_path),
                                 str(evaluation_path): file_sha256(evaluation_path)},
                "artifacts": artifacts, "human_topic_validation": "PENDING",
                "restricted_keys_accessed": False, "model_predictions_accessed": False,
                "sealed_2025_test_accessed": False}
    atomic_json(output / "manifest.json", manifest)
    return manifest


class PageMetadata(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.meta: dict[str, list[str]] = {}
        self._title = False
        self.title = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "title":
            self._title = True
        elif tag == "meta":
            key = attributes.get("name") or attributes.get("property") or attributes.get("itemprop")
            val = attributes.get("content")
            if key and val:
                self.meta.setdefault(key.casefold(), []).append(val.strip())

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._title = False

    def handle_data(self, data: str) -> None:
        if self._title:
            self.title += data


def parse_page_metadata(content: bytes) -> dict:
    page = PageMetadata()
    page.feed(content.decode("utf-8", errors="replace"))
    return {"page_title": page.title.strip(), "meta": page.meta}


def validate_publisher_decisions(frame: pd.DataFrame, source: pd.DataFrame) -> pd.DataFrame:
    required = {"work_id", "doi", "crossref_publisher", "official_publisher", "official_venue",
                "evidence_url", "secondary_evidence_url", "retrieved_at_utc", "publisher_relation",
                "assessment_status", "confidence_category", "reasoning_summary", "evidence_independence",
                "reviewer_type", "human_adjudicated"}
    if not required.issubset(frame.columns) or len(frame) != 30:
        raise ValueError("Publisher decisions require exactly 30 rows and all evidence columns")
    if frame.work_id.duplicated().any() or set(frame.work_id) != set(source.work_id):
        raise ValueError("Publisher case identities differ from frozen review sample")
    if not frame.assessment_status.isin(PUBLISHER_STATUSES).all():
        raise ValueError("Invalid publisher status")
    if not frame.confidence_category.isin(CONFIDENCES).all():
        raise ValueError("Invalid publisher confidence")
    if not frame.reviewer_type.eq("AI_ASSISTED").all() or frame.human_adjudicated.fillna(True).astype(bool).any():
        raise ValueError("AI judgments must not impersonate human reviewers")
    for row in frame.loc[frame.assessment_status.isin(SOURCE_BACKED)].itertuples():
        parsed = urlparse(str(row.evidence_url))
        if parsed.scheme not in ("https", "http") or not parsed.hostname or not row.official_publisher:
            raise ValueError("Positive/negative source-backed decision lacks official evidence URL or publisher")
        if row.evidence_independence not in ("OFFICIAL_SOURCE_BACKED", "OFFICIAL_PLUS_INDEPENDENT_DIRECTORY"):
            raise ValueError("Source-backed decision must identify evidence hierarchy")
    return frame.sort_values("work_id").reset_index(drop=True)


def publisher_metrics(frame: pd.DataFrame) -> dict:
    counts = Counter(frame.assessment_status)
    verified = sum(counts[x] for x in SOURCE_BACKED)
    correct = counts["SOURCE_BACKED_CORRECT"] + counts["SOURCE_BACKED_ACCEPTABLE_ALIAS"]
    wilson = None
    if verified:
        z = 1.959963984540054
        p = correct / verified
        center = (p + z*z/(2*verified)) / (1 + z*z/verified)
        half = z * math.sqrt(p*(1-p)/verified + z*z/(4*verified*verified)) / (1 + z*z/verified)
        wilson = [max(0.0, center-half), min(1.0, center+half)]
    return {"selected": len(frame), "inspected": int(frame.assessment_status.notna().sum()),
            "status_counts": {x: int(counts[x]) for x in sorted(PUBLISHER_STATUSES)},
            "source_verifiable": verified, "source_consistent": correct,
            "observed_consistency_among_verifiable": correct / verified if verified else None,
            "wilson_95_selected_verifiable_only": wilson,
            "independent_directory_cases": int(frame.evidence_independence.eq(
                "OFFICIAL_PLUS_INDEPENDENT_DIRECTORY").sum()),
            "human_adjudicated": 0,
            "all_167_recoveries_verified": False}


def freeze_publisher_assessments(source: pd.DataFrame, decisions: pd.DataFrame,
                                 page_evidence: dict, output: Path) -> dict:
    if output.exists():
        raise FileExistsError("Publisher assessment run already frozen")
    if len(page_evidence.get("cases", [])) != 30:
        raise ValueError("Official page evidence must cover 30 cases")
    if decisions.work_id.duplicated().any() or set(decisions.work_id) != set(source.work_id):
        raise ValueError("Publisher decision identities do not cover the frozen sample")
    seen = {item["work_id"]: item for item in page_evidence["cases"]}
    if set(seen) != set(source.work_id):
        raise ValueError("Official page evidence identities differ from source")
    merged = source[["work_id", "doi", "recovered_or_compared_value"]].merge(
        decisions, on="work_id", validate="one_to_one")
    merged = merged.rename(columns={"recovered_or_compared_value": "crossref_publisher"})
    if "doi_x" in merged:
        if not merged.doi_x.eq(merged.doi_y).all():
            raise ValueError("Decision DOI identity mismatch")
        merged = merged.drop(columns="doi_y").rename(columns={"doi_x": "doi"})
    merged["retrieved_at_utc"] = merged.work_id.map(lambda x: seen[x]["retrieved_at_utc"])
    merged["reviewer_type"] = "AI_ASSISTED"
    merged["human_adjudicated"] = False
    checked = validate_publisher_decisions(merged, source)
    output.mkdir(parents=True, exist_ok=False)
    artifact = atomic_parquet(output / "publisher_ai_assessments.parquet", checked)
    metrics = publisher_metrics(checked)
    atomic_json(output / "publisher_metrics.json", metrics)
    manifest = {"status": "frozen_ai_publisher_assessment_human_pending", "frozen_at_utc": utc_now(),
                "input_hashes": {str(PUBLISHER_SHEET): file_sha256(PUBLISHER_SHEET)},
                "official_page_evidence_sha256": sha256_bytes(json.dumps(page_evidence, sort_keys=True).encode()),
                "artifacts": {"publisher_ai_assessments": artifact,
                              "publisher_metrics": {"path": str(output / "publisher_metrics.json"),
                                                    "sha256": file_sha256(output / "publisher_metrics.json")}},
                "direct_get_attempts": page_evidence["direct_get_attempts"],
                "observed_http_transactions": page_evidence["observed_http_transactions"],
                "budget": page_evidence["budget"], "human_publisher_adjudication": "PENDING"}
    atomic_json(output / "manifest.json", manifest)
    return manifest


def collect_official_pages(source: pd.DataFrame, output: Path, *, budget: int = 120,
                           session: requests.Session | None = None) -> dict:
    """Bounded DOI resolver visits; landing pages are evidence leads, not automatic correctness."""
    if budget < 0 or budget > 120 or len(source) != 30:
        raise ValueError("Official-source request budget must be 0..120 for 30 frozen cases")
    if output.exists():
        raise FileExistsError("Never overwrite source evidence")
    session = session or requests.Session()
    evidence: list[dict] = []
    attempts = 0
    transactions = 0
    for row in source.itertuples():
        item = {"work_id": row.work_id, "doi": row.doi,
                "crossref_publisher": row.recovered_or_compared_value,
                "retrieved_at_utc": utc_now(), "status": "NOT_CHECKED",
                "landing_url": None, "http_status": None, "response_sha256": None,
                "page_title": None, "metadata": {}, "redirect_chain": []}
        if transactions >= budget:
            item["status"] = "BUDGET_EXHAUSTED"
            evidence.append(item)
            continue
        try:
            attempts += 1
            current = row.doi
            chain = []
            while True:
                parsed_url = urlparse(current)
                if parsed_url.scheme not in ("http", "https") or not parsed_url.hostname:
                    raise ValueError("DOI redirect to non-HTTP URL")
                if transactions >= budget:
                    item["status"] = "BUDGET_EXHAUSTED_ON_REDIRECT"
                    break
                response = session.get(current, timeout=15, allow_redirects=False,
                                       headers={"User-Agent": "AI-Research-Trends/0.1 academic metadata audit"})
                transactions += 1
                chain.append(response)
                location = response.headers.get("Location")
                if response.is_redirect and location:
                    if len(chain) >= 10:
                        item["status"] = "REDIRECT_LIMIT"
                        break
                    current = urljoin(response.url, location)
                    continue
                break
            if not chain:
                raise ValueError("No source response was obtained")
            response = chain[-1]
            if item["status"] == "NOT_CHECKED":
                item["status"] = "FETCHED" if response.ok else "HTTP_ERROR"
            parsed = parse_page_metadata(response.content) if response.ok else {"page_title": None, "meta": {}}
            item.update({"landing_url": response.url, "http_status": response.status_code,
                         "response_sha256": sha256_bytes(response.content),
                         "page_title": parsed["page_title"], "metadata": parsed["meta"],
                         "redirect_chain": [{"url": hop.url, "status": hop.status_code} for hop in chain]})
        except requests.RequestException as error:
            # Exact errors are useful locally; never promote a failed fetch into verified evidence.
            item.update({"status": "FETCH_ERROR", "error_type": type(error).__name__})
        evidence.append(item)
    result = {"created_at_utc": utc_now(), "direct_get_attempts": attempts,
              "observed_http_transactions": transactions, "budget": budget,
              "cases": evidence,
              "warning": "A DOI redirect or page title alone does not establish legal publisher identity"}
    atomic_json(output, result)
    return result


def verify_frozen_run(root: Path, *, package: Path = HUMAN_PACKAGE) -> dict:
    """Read-only: verify all frozen files and still-blind source package."""
    topic_manifest_path = root / "topic/frozen/manifest.json"
    publisher_manifest_path = root / "publisher/frozen/manifest.json"
    topic = json.loads(topic_manifest_path.read_text(encoding="utf-8"))
    publisher = json.loads(publisher_manifest_path.read_text(encoding="utf-8"))
    if topic["status"] != "frozen_ai_assessment_human_pending":
        raise ValueError("Unexpected topic assessment state")
    if publisher["status"] != "frozen_ai_publisher_assessment_human_pending":
        raise ValueError("Unexpected publisher assessment state")
    if topic["human_topic_validation"] != "PENDING" or publisher["human_publisher_adjudication"] != "PENDING":
        raise ValueError("Human-review status was incorrectly promoted")
    if topic["restricted_keys_accessed"] or topic["model_predictions_accessed"] or topic["sealed_2025_test_accessed"]:
        raise ValueError("Prohibited evaluation source accessed")
    source = validate_package(package)
    if not source["valid"]:
        raise ValueError("Blind reviewer package changed")
    for path, digest in topic["input_hashes"].items():
        if file_sha256(Path(path)) != digest:
            raise ValueError(f"Topic input hash changed: {path}")
    if file_sha256(PUBLISHER_SHEET) != publisher["input_hashes"][str(PUBLISHER_SHEET)]:
        raise ValueError("RQ7.1 publisher sample changed")
    outputs = {}
    for name, manifest in (("topic", topic), ("publisher", publisher)):
        for key, entry in manifest["artifacts"].items():
            path = Path(entry["path"])
            if file_sha256(path) != entry["sha256"]:
                raise ValueError(f"Frozen output hash changed: {path}")
            outputs[f"{name}/{key}"] = entry["sha256"]
    calibration = pd.read_parquet(root / "topic/frozen/calibration_ai_assessments.parquet")
    evaluation = pd.read_parquet(root / "topic/frozen/evaluation_ai_assessments.parquet")
    topics = pd.read_parquet(root / "topic/frozen/topic_scope_assessment.parquet")
    publishers = pd.read_parquet(root / "publisher/frozen/publisher_ai_assessments.parquet")
    if (len(calibration), len(evaluation), len(topics), len(publishers)) != (40, 100, 14, 30):
        raise ValueError("Frozen assessment counts differ from approved diagnostic set")
    if calibration.example_id.duplicated().any() or evaluation.example_id.duplicated().any():
        raise ValueError("Frozen AI decisions contain duplicate example IDs")
    if publishers.work_id.duplicated().any():
        raise ValueError("Frozen publisher decisions contain duplicate works")
    overall_path = root / "manifest.json"
    if overall_path.exists():
        overall = json.loads(overall_path.read_text(encoding="utf-8"))
        if overall["status"] != "complete_ai_assessment_human_pending":
            raise ValueError("Overall run has an unexpected status")
        if overall["topic_manifest_sha256"] != file_sha256(topic_manifest_path):
            raise ValueError("Frozen topic manifest hash changed")
        if overall["publisher_manifest_sha256"] != file_sha256(publisher_manifest_path):
            raise ValueError("Frozen publisher manifest hash changed")
        for path, digest in overall["input_hashes"].items():
            if file_sha256(Path(path)) != digest:
                raise ValueError(f"Private decision/evidence input hash changed: {path}")
    handoff_path = root / "reviews/manifest.json"
    if handoff_path.exists():
        handoff = json.loads(handoff_path.read_text(encoding="utf-8"))
        if handoff["status"] != "prepared_human_review_pending" or handoff["publisher_cases"] != 30:
            raise ValueError("Private human handoff manifest is incomplete")
        for path, digest in handoff["files"].items():
            if file_sha256(Path(path)) != digest:
                raise ValueError(f"Private human handoff file changed: {path}")
    return {"status": "PASS", "counts": {"topics": 14, "calibration": 40,
                                          "evaluation": 100, "publishers": 30},
            "artifacts_verified": len(outputs), "human_topic_validation": "PENDING",
            "human_publisher_adjudication": "PENDING",
            "sealed_2025_test": "NOT_ACCESSED"}


def seal_run_manifest(root: Path, *, browser_search_calls: int,
                      browser_search_queries: int, exploratory_get_attempts: int) -> dict:
    """Bind private decision/evidence inputs to the already-frozen outputs once."""
    result = verify_frozen_run(root)
    destination = root / "manifest.json"
    if destination.exists():
        raise FileExistsError("Overall AI audit manifest already sealed")
    private_inputs = [root / "topic/topic_scope_decisions.tsv",
                      root / "topic/blind_ai_decisions.tsv",
                      root / "publisher/official_page_evidence.json",
                      root / "publisher/publisher_ai_decisions.tsv"]
    if (root / "revision_provenance.json").exists():
        private_inputs.append(root / "revision_provenance.json")
    evidence = json.loads((root / "publisher/official_page_evidence.json").read_text())
    manifest = {"status": "complete_ai_assessment_human_pending", "sealed_at_utc": utc_now(),
                "counts": result["counts"],
                "input_hashes": {str(path): file_sha256(path) for path in private_inputs},
                "topic_manifest_sha256": file_sha256(root / "topic/frozen/manifest.json"),
                "publisher_manifest_sha256": file_sha256(root / "publisher/frozen/manifest.json"),
                "direct_doi_get_attempts_recorded_in_collector": evidence["direct_get_attempts"],
                "observed_http_transactions_in_collector": evidence["observed_http_transactions"],
                "collector_budget": evidence["budget"],
                "browser_search_calls": browser_search_calls,
                "browser_search_queries": browser_search_queries,
                "browser_backend_http_request_count": "NOT_AVAILABLE",
                "exploratory_direct_get_attempts_outside_collector": exploratory_get_attempts,
                "human_topic_validation": "PENDING", "human_publisher_adjudication": "PENDING",
                "sealed_2025_final_test": "NOT_ACCESSED"}
    atomic_json(destination, manifest)
    return manifest


def revise_run(previous: Path, new_root: Path, corrections_path: Path) -> dict:
    """Create an immutable versioned correction after full-abstract re-review.

    The previous frozen run remains byte-for-byte unchanged and is linked by hash.
    No external request is made by this function.
    """
    verify_frozen_run(previous)
    if new_root.exists():
        raise FileExistsError("Never replace an existing AI validation run")
    previous_manifest = json.loads((previous / "manifest.json").read_text())
    corrections = pd.read_csv(corrections_path, sep="\t")
    if len(corrections) == 0 or corrections.example_id.duplicated().any():
        raise ValueError("Revision requires unique nonempty corrections")
    prior = pd.read_csv(previous / "topic/blind_ai_decisions.tsv", sep="\t")
    if not set(corrections.example_id).issubset(set(prior.example_id)):
        raise ValueError("Correction refers to an unknown blind example")
    if not set(corrections.columns).issubset(set(prior.columns)):
        raise ValueError("Correction field is not in the frozen decision schema")
    revised = prior.copy().set_index("example_id")
    for row in corrections.set_index("example_id").itertuples():
        for field in corrections.columns.drop("example_id"):
            revised.loc[row.Index, field] = getattr(row, field)
    revised = revised.reset_index()
    for name in ("topic", "publisher"):
        (new_root / name).mkdir(parents=True, exist_ok=False)
    shutil.copyfile(previous / "topic/topic_scope_decisions.tsv", new_root / "topic/topic_scope_decisions.tsv")
    revised.to_csv(new_root / "topic/blind_ai_decisions.tsv", sep="\t", index=False)
    shutil.copyfile(previous / "publisher/official_page_evidence.json",
                    new_root / "publisher/official_page_evidence.json")
    shutil.copyfile(previous / "publisher/publisher_ai_decisions.tsv",
                    new_root / "publisher/publisher_ai_decisions.tsv")
    freeze_topic_assessments(HUMAN_PACKAGE, new_root / "topic/topic_scope_decisions.tsv",
                             new_root / "topic/blind_ai_decisions.tsv",
                             new_root / "topic/blind_ai_decisions.tsv", new_root / "topic/frozen",
                             prompt_version="ai-validation-v2-full-abstract-review")
    freeze_publisher_assessments(pd.read_csv(PUBLISHER_SHEET),
                                  pd.read_csv(new_root / "publisher/publisher_ai_decisions.tsv", sep="\t"),
                                  json.loads((new_root / "publisher/official_page_evidence.json").read_text()),
                                  new_root / "publisher/frozen")
    atomic_json(new_root / "revision_provenance.json",
                {"previous_run": str(previous),
                 "previous_manifest_sha256": file_sha256(previous / "manifest.json"),
                 "corrections_sha256": file_sha256(corrections_path),
                 "corrected_example_ids": list(corrections.example_id),
                 "reason": "Blind full-abstract re-review, before answer-key/model inspection",
                 "external_requests": 0})
    return seal_run_manifest(new_root,
                             browser_search_calls=previous_manifest["browser_search_calls"],
                             browser_search_queries=previous_manifest["browser_search_queries"],
                             exploratory_get_attempts=previous_manifest[
                                 "exploratory_direct_get_attempts_outside_collector"])


def prepare_private_handoff(root: Path) -> dict:
    """Publisher proposals may be reviewed; topic AI choices stay hidden from raters."""
    verify_frozen_run(root)
    reviews = root / "reviews"
    if reviews.exists():
        raise FileExistsError("Private reviewer handoff already exists")
    topic_dir = reviews / "topic_human_handoff"
    publisher_dir = reviews / "publisher_human_handoff"
    topic_dir.mkdir(parents=True, exist_ok=False)
    publisher_dir.mkdir(parents=True, exist_ok=False)
    topic_note = topic_dir / "INSTRUCTIONS.md"
    topic_note.write_text(
        "Give the original reviewer_a and reviewer_b blind packages to separate real raters. "
        "Do not reveal this AI run or its topic choices until both independent sheets are frozen. "
        "Do not open the restricted answer keys or 2025 final test.\n", encoding="utf-8")
    frame = pd.read_parquet(root / "publisher/frozen/publisher_ai_assessments.parquet")
    proposals = frame[["work_id", "doi", "crossref_publisher", "official_publisher",
                       "evidence_url", "secondary_evidence_url", "assessment_status",
                       "reasoning_summary"]].copy()
    proposals["human_decision"] = ""
    proposals["human_note"] = ""
    path = publisher_dir / "publisher_proposals_for_human_check.csv"
    tmp = path.with_name("." + path.name + ".partial")
    proposals.to_csv(tmp, index=False)
    tmp.replace(path)
    manifest = {"status": "prepared_human_review_pending", "created_at_utc": utc_now(),
                "topic_package_unchanged": True, "publisher_cases": len(proposals),
                "ai_decisions_not_human": True,
                "files": {str(topic_note): file_sha256(topic_note), str(path): file_sha256(path)}}
    atomic_json(reviews / "manifest.json", manifest)
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("preflight", help="Validate frozen blind inputs without reading keys")
    check.add_argument("--package", type=Path, default=HUMAN_PACKAGE)
    fetch = sub.add_parser("fetch-publisher", help="Visit DOI landing pages within a strict request budget")
    fetch.add_argument("--sheet", type=Path, default=PUBLISHER_SHEET)
    fetch.add_argument("--output", type=Path, required=True)
    fetch.add_argument("--budget", type=int, default=120)
    topic = sub.add_parser("freeze-topic", help="Validate and freeze all blind AI topic decisions")
    topic.add_argument("--package", type=Path, default=HUMAN_PACKAGE)
    topic.add_argument("--scope", type=Path, required=True)
    topic.add_argument("--calibration", type=Path, required=True)
    topic.add_argument("--evaluation", type=Path, required=True)
    topic.add_argument("--output", type=Path, required=True)
    publisher = sub.add_parser("freeze-publisher", help="Validate and freeze 30 source-audited cases")
    publisher.add_argument("--sheet", type=Path, default=PUBLISHER_SHEET)
    publisher.add_argument("--decisions", type=Path, required=True)
    publisher.add_argument("--page-evidence", type=Path, required=True)
    publisher.add_argument("--output", type=Path, required=True)
    verify = sub.add_parser("verify-run", help="Read-only checksum and separation verification")
    verify.add_argument("--run", type=Path, required=True)
    seal = sub.add_parser("seal-run", help="Write immutable overall manifest after verification")
    seal.add_argument("--run", type=Path, required=True)
    seal.add_argument("--browser-search-calls", type=int, required=True)
    seal.add_argument("--browser-search-queries", type=int, required=True)
    seal.add_argument("--exploratory-get-attempts", type=int, required=True)
    revise = sub.add_parser("revise-run", help="Freeze a corrected version without changing prior evidence")
    revise.add_argument("--previous", type=Path, required=True)
    revise.add_argument("--new-run", type=Path, required=True)
    revise.add_argument("--corrections", type=Path, required=True)
    handoff = sub.add_parser("prepare-handoff", help="Prepare isolated, private human-review handoff")
    handoff.add_argument("--run", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "preflight":
        frames, topics, hashes = load_blind_inputs(args.package)
        print(json.dumps({"status": "PASS", "topics": len(topics),
                          "blind_examples": {k: len(v) for k, v in frames.items()},
                          "input_hashes": hashes}, indent=2))
    elif args.command == "fetch-publisher":
        require_private_output(args.output)
        sheet = pd.read_csv(args.sheet)
        if len(sheet) != 30 or sheet.work_id.duplicated().any():
            raise ValueError("Publisher source review sheet changed")
        result = collect_official_pages(sheet, args.output, budget=args.budget)
        print(json.dumps({"cases": len(result["cases"]),
                          "direct_get_attempts": result["direct_get_attempts"],
                          "observed_http_transactions": result["observed_http_transactions"],
                          "budget": result["budget"]}, indent=2))
    elif args.command == "freeze-topic":
        require_private_output(args.output)
        result = freeze_topic_assessments(args.package, args.scope, args.calibration,
                                          args.evaluation, args.output)
        print(json.dumps({"status": result["status"],
                          "artifacts": result["artifacts"]}, indent=2))
    elif args.command == "freeze-publisher":
        require_private_output(args.output)
        result = freeze_publisher_assessments(pd.read_csv(args.sheet),
                                              pd.read_csv(args.decisions, sep="\t"),
                                              json.loads(args.page_evidence.read_text()), args.output)
        print(json.dumps({"status": result["status"],
                          "artifacts": result["artifacts"]}, indent=2))
    elif args.command == "verify-run":
        print(json.dumps(verify_frozen_run(args.run), indent=2))
    elif args.command == "seal-run":
        require_private_output(args.run / "manifest.json")
        result = seal_run_manifest(args.run, browser_search_calls=args.browser_search_calls,
                                   browser_search_queries=args.browser_search_queries,
                                   exploratory_get_attempts=args.exploratory_get_attempts)
        print(json.dumps({"status": result["status"], "counts": result["counts"],
                          "manifest_sha256": file_sha256(args.run / "manifest.json")}, indent=2))
    else:
        if args.command == "revise-run":
            require_private_output(args.new_run / "manifest.json")
            result = revise_run(args.previous, args.new_run, args.corrections)
            print(json.dumps({"status": result["status"], "counts": result["counts"],
                              "manifest_sha256": file_sha256(args.new_run / "manifest.json")}, indent=2))
        else:
            require_private_output(args.run / "reviews/manifest.json")
            result = prepare_private_handoff(args.run)
            print(json.dumps({"status": result["status"], "publisher_cases": result["publisher_cases"],
                              "files": result["files"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
