"""CLI for collecting a deterministic, unbalanced OpenAlex pilot sample."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ai_research_trends.config import build_primary_analysis_filter, load_config
from ai_research_trends.crawling.openalex_client import OpenAlexClient
from ai_research_trends.env import load_project_env


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Collect a deterministic OpenAlex pilot sample, preserving byte-identical "
            "raw pages and a query/checksum manifest."
        )
    )
    parser.add_argument("--config", default="config/topics.yaml", help="Study YAML path")
    parser.add_argument("--size", type=int, help="Sample size (default: config pilot_size)")
    parser.add_argument("--seed", type=int, help="Random seed (default: config sampling_seed)")
    parser.add_argument("--raw-root", default="data/raw/openalex", help="Raw response root")
    parser.add_argument("--interim-root", default="data/interim", help="Extracted JSONL root")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    load_project_env()
    config = load_config(Path(args.config))
    study = config["study"]
    size = args.size if args.size is not None else int(study["pilot_size"])
    seed = args.seed if args.seed is not None else int(study["sampling_seed"])
    query_filter = build_primary_analysis_filter(study)

    client = OpenAlexClient()
    summary = client.collect_sample(
        query_filter=query_filter,
        requested_records=size,
        seed=seed,
        raw_root=args.raw_root,
        interim_root=args.interim_root,
    )
    print(json.dumps(summary.__dict__, indent=2))
    if not summary.complete_for_requested_sample:
        print("ERROR: requested sample was not completely retrieved", flush=True)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
