"""Build reproducible positive and negative audit frames for custom text rules."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from pathlib import Path
from typing import Any

from ai_research_trends.config import load_config
from ai_research_trends.crawling.openalex_client import canonical_work_id, utc_now
from ai_research_trends.preprocessing.categories import classify_work, searchable_text


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Create fixed-seed positive and negative manual-audit candidates for every "
            "custom category. This does not estimate precision or recall by itself."
        )
    )
    parser.add_argument("jsonl", help="Work records to audit")
    parser.add_argument("--config", default="config/topics.yaml")
    parser.add_argument("--seed", type=int, default=20251019)
    parser.add_argument("--positive-per-category", type=int, default=10)
    parser.add_argument("--negative-per-category", type=int, default=10)
    parser.add_argument(
        "--output", default="data/metadata/category_audit_candidates.json"
    )
    return parser


def _sample(rows: list[dict[str, Any]], size: int, seed: int) -> list[dict[str, Any]]:
    if size < 0:
        raise ValueError("Audit sample sizes must be non-negative")
    ordered = sorted(rows, key=lambda row: canonical_work_id(row.get("id", "")))
    return random.Random(seed).sample(ordered, min(size, len(ordered)))


def build_audit_candidates(
    rows: list[dict[str, Any]],
    config: dict[str, Any],
    *,
    seed: int,
    positive_per_category: int,
    negative_per_category: int,
) -> dict[str, Any]:
    classified = [(row, classify_work(row, config)) for row in rows]
    categories: dict[str, Any] = {}
    for slug in config["custom_emerging_technologies"]:
        positives = [
            row
            for row, matches in classified
            if slug in matches.custom_emerging and not matches.text_quarantine_reason
        ]
        negatives = [
            row
            for row, matches in classified
            if slug not in matches.custom_emerging and not matches.text_quarantine_reason
        ]
        category_seed = seed + sum(ord(character) for character in slug)
        candidates = []
        for expected_match, subset in (
            (True, _sample(positives, positive_per_category, category_seed)),
            (False, _sample(negatives, negative_per_category, category_seed + 1)),
        ):
            for row in subset:
                candidates.append(
                    {
                        "work_id": canonical_work_id(row.get("id", "")),
                        "title": row.get("title"),
                        "publication_year": row.get("publication_year"),
                        "rule_match": expected_match,
                        "text_excerpt": searchable_text(row)[:600],
                        "manual_judgment": None,
                        "manual_notes": None,
                    }
                )
        categories[slug] = {
            "population_positive": len(positives),
            "population_negative": len(negatives),
            "positive_candidates": sum(row["rule_match"] for row in candidates),
            "negative_candidates": sum(not row["rule_match"] for row in candidates),
            "candidates": candidates,
        }

    quarantined = [
        {
            "work_id": canonical_work_id(row.get("id", "")),
            "reason": matches.text_quarantine_reason,
        }
        for row, matches in classified
        if matches.text_quarantine_reason
    ]
    return {
        "schema_version": 1,
        "created_at_utc": utc_now(),
        "seed": seed,
        "records_in_audit_frame": len(rows),
        "interpretation": (
            "Candidates include rule-positive and random rule-negative records. Manual "
            "labels are required; a small random-negative audit cannot establish recall."
        ),
        "quarantined_malformed_text_records": quarantined,
        "categories": categories,
    }


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    source = Path(args.jsonl)
    source_bytes = source.read_bytes()
    rows = [json.loads(line) for line in source_bytes.splitlines() if line.strip()]
    result = build_audit_candidates(
        rows,
        load_config(args.config),
        seed=args.seed,
        positive_per_category=args.positive_per_category,
        negative_per_category=args.negative_per_category,
    )
    result["source_jsonl"] = str(source)
    result["source_sha256"] = hashlib.sha256(source_bytes).hexdigest()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"records": len(rows), "output": str(output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
