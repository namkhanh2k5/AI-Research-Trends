"""Read-only, training-period-only data gap audit for the Phase 6B catalogue."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import pandas as pd
import yaml

from ai_research_trends.ml.topic_pilot import prepare_rows
from ai_research_trends.preprocessing.validate_tables import file_sha256


def audit_training_gaps(
    works: pd.DataFrame, topics: pd.DataFrame, catalogue: dict,
    metadata: pd.DataFrame, targets: tuple[int, ...] = (225, 300),
) -> pd.DataFrame:
    """Audit only 2020–2023 works; never consult validation/test labels."""
    historical = works.loc[works.publication_year.between(2020, 2023)].copy()
    if historical.empty or historical.work_id.duplicated().any():
        raise ValueError("Historical work IDs must be present and unique")
    eligible, exclusion = prepare_rows(historical)
    if not set(eligible.work_id).issubset(set(historical.work_id)):
        raise ValueError("Eligibility introduced a work outside the training period")
    ranks = topics.loc[topics.topic_rank.eq(1), ["work_id", "topic_id", "topic_score"]]
    if ranks.work_id.duplicated().any():
        raise ValueError("Duplicate rank-one topic relationships")
    historical = historical.merge(ranks, on="work_id", validate="one_to_one")
    if not historical.primary_topic_id.eq(historical.topic_id).all():
        raise ValueError("Primary-topic label disagrees with rank-one topic")
    selected = catalogue["catalogue_b"]
    if len(selected) != 14 or len(selected) != len(set(selected)):
        raise ValueError("Expected fourteen unique selected topic IDs")
    names = metadata.set_index("short_id")
    if not set(selected).issubset(set(names.index)):
        raise ValueError("Selected topic is absent from verified metadata")
    audit = exclusion.set_index("work_id")
    rows = []
    for short in selected:
        topic_id = f"https://openalex.org/{short}"
        source = historical.loc[historical.primary_topic_id.eq(topic_id)].copy()
        usable = eligible.loc[eligible.primary_topic_id.eq(topic_id)].copy()
        if source.empty:
            raise ValueError(f"No historical source works for selected topic {short}")
        reason_counts = audit.loc[source.work_id, "exclusion_reason"].value_counts()
        usable_rate = len(usable) / len(source)
        scores = source.topic_score.dropna()
        row = {
            "topic_id": topic_id, "short_id": short,
            "topic_name": names.at[short, "name"],
            "official_description": names.at[short, "description"],
            "primary_subfield_id": str(names.at[short, "subfield_id"]),
            "source_training_works": len(source),
            "usable_training_works": len(usable),
            "title_available": int(source.title.notna().sum()),
            "abstract_available": int(source.abstract.notna().sum()),
            "missing_abstract_rate": float(source.abstract.isna().mean()),
            "version_exclusions": int(reason_counts.get("later_version", 0)),
            "text_exclusions": int(reason_counts.get("missing_title_or_abstract", 0)),
            "version_exclusion_rate": float(reason_counts.get("later_version", 0) / len(source)),
            "observed_usable_rate": usable_rate,
            "topic_score_median": float(scores.median()) if len(scores) else None,
            "topic_score_p10": float(scores.quantile(.1)) if len(scores) else None,
            "topic_score_p90": float(scores.quantile(.9)) if len(scores) else None,
            "work_type_counts": json.dumps(source.work_type.value_counts().sort_index().to_dict(), sort_keys=True),
            "language_counts": json.dumps(source.language.fillna("<missing>").value_counts().sort_index().to_dict(), sort_keys=True),
            "overlap_concern": catalogue["scope_review"][short]["overlap"],
            "scope_reason": catalogue["scope_review"][short]["reason"],
        }
        for year in range(2020, 2024):
            row[f"source_{year}"] = int(source.publication_year.eq(year).sum())
            row[f"usable_{year}"] = int(usable.publication_year.eq(year).sum())
        for target in targets:
            gap = max(0, target - len(usable))
            row[f"shortfall_{target}"] = gap
            row[f"estimated_raw_needed_{target}"] = math.ceil(gap / usable_rate) if usable_rate else None
        rows.append(row)
    return pd.DataFrame(rows).sort_values("short_id").reset_index(drop=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--processed-dir", type=Path, default=Path("data/processed/openalex_stratified/stratified_20261019T155909Z"))
    parser.add_argument("--catalogue", type=Path, default=Path("config/phase6b_catalogue.yaml"))
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output_dir.exists(): parser.error("Output directory exists; use a new versioned path")
    config = yaml.safe_load(args.catalogue.read_text())
    metadata_path = Path(config["source_metadata_csv"])
    if file_sha256(metadata_path) != config["source_metadata_sha256"]:
        raise ValueError("Verified topic metadata checksum mismatch")
    works_path = args.processed_dir / "works.parquet"
    topics_path = args.processed_dir / "work_topics.parquet"
    frame = audit_training_gaps(pd.read_parquet(works_path), pd.read_parquet(topics_path),
                                config, pd.read_csv(metadata_path))
    args.output_dir.mkdir(parents=True, exist_ok=False)
    output = args.output_dir / "data_gap.csv"
    frame.to_csv(output, index=False)
    manifest = {"status": "complete", "training_years": [2020, 2021, 2022, 2023],
                "validation_year": "excluded", "test_year": "excluded",
                "source_work_sha256": file_sha256(works_path),
                "source_topic_sha256": file_sha256(topics_path),
                "catalogue_sha256": file_sha256(args.catalogue),
                "metadata_sha256": file_sha256(metadata_path),
                "data_gap_sha256": file_sha256(output), "rows": len(frame),
                "usable_selected_training": int(frame.usable_training_works.sum())}
    (args.output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"rows": len(frame), "usable_selected_training": manifest["usable_selected_training"],
                      "shortfall_225": int(frame.shortfall_225.sum()),
                      "shortfall_300": int(frame.shortfall_300.sum())}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
