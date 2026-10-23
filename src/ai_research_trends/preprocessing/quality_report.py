"""Render a Phase 3 audit report from verified, local processing artifacts."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import pyarrow.parquet as pq

from ai_research_trends.preprocessing.validate_tables import file_sha256


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Render the verified Phase 3 quality report")
    parser.add_argument("processed_dir", type=Path)
    parser.add_argument("--output", type=Path, default=Path("reports/PHASE3_DATA_QUALITY_REPORT.md"))
    parser.add_argument("--compare-dir", type=Path, help="Independently processed rerun for SHA-256 comparison")
    return parser


def render_report(processed_dir: Path, compare_dir: Path | None = None) -> str:
    manifest_path = processed_dir / "manifest.json"
    quality_path = processed_dir / "quality.json"
    manifest = json.loads(manifest_path.read_text())
    quality = json.loads(quality_path.read_text())
    if manifest.get("status") != "complete" or not manifest.get("complete"):
        raise ValueError("Refusing to report an incomplete Phase 3 run")
    if file_sha256(quality_path) != manifest["quality_json_sha256"]:
        raise ValueError("Quality JSON checksum does not match processing manifest")
    for name, item in manifest["inputs"].items():
        if file_sha256(Path(item["path"])) != item["sha256"]:
            raise ValueError(f"{name} input checksum does not match processing manifest")
    for name, item in manifest["tables"].items():
        if file_sha256(processed_dir / f"{name}.parquet") != item["sha256"]:
            raise ValueError(f"{name} Parquet checksum does not match processing manifest")
    if not all(item["status"] == "PASS" for item in manifest["validation"].values()):
        raise ValueError("Refusing to report failed integrity checks")

    works = pq.read_table(processed_dir / "works.parquet", columns=[
        "work_type", "fwci", "is_retracted", "publication_year", "sample_stratum"
    ]).to_pylist()
    categories = pq.read_table(processed_dir / "category_membership.parquet", columns=[
        "analytical_layer", "category"
    ]).to_pylist()
    category_counts = Counter((r["analytical_layer"], r["category"]) for r in categories)
    fwci_by_type = Counter(r["work_type"] for r in works if r["fwci"] is None)
    type_counts = Counter(r["work_type"] for r in works)
    years = Counter(r["publication_year"] for r in works)
    plan = json.loads(Path(manifest["inputs"]["plan"]["path"]).read_text())
    if sum(years.values()) != manifest["tables"]["works"]["rows"]:
        raise ValueError("Work-year count does not match the manifest")
    if any(r["is_retracted"] for r in works):
        raise ValueError("Retracted work found in primary sample")

    lines = [
        "# Phase 3 Data Quality Report",
        "",
        "## A. Processing overview",
        "",
        f"- Status: **{manifest['status']}**; processed at {manifest['processed_at_utc']}.",
        f"- Source collection run: `{manifest['source_run_id']}`; observation time: {manifest['observation_time_utc']}.",
        f"- Processing Git HEAD: `{manifest['git_head_at_processing']}`; source-code SHA-256: `{manifest['source_code_sha256']}`.",
        f"- Output directory: `{processed_dir}`; processing manifest: `{manifest_path}`.",
        "- Original raw and interim JSONL files were read only; no OpenAlex API request was made.",
        "- Transformations: strict corpus and ID validation; Unicode-preserving whitespace normalization; DOI normalization; abstract reconstruction; relationship deduplication; nullable bibliometric, text and collaboration features; sorted typed Parquet export.",
        "",
        "### Verified inputs",
        "",
        "| Artifact | Path | SHA-256 |",
        "|---|---|---|",
    ]
    for name, item in manifest["inputs"].items():
        lines.append(f"| {name} | `{item['path']}` | `{item['sha256']}` |")
    lines += [
        "",
        "### Sampling allocation (detailed sample, not population estimates)",
        "",
        "| Year | Population N | Planned n | Actual n | Nominal N/n |",
        "|---:|---:|---:|---:|---:|",
    ]
    for stratum in plan["strata"]:
        year = stratum["publication_year"]
        if years[year] != stratum["sample_size"]:
            raise ValueError(f"Year {year} actual count differs from sampling plan")
        lines.append(f"| {year} | {stratum['population_size']:,} | {stratum['sample_size']:,} | {years[year]:,} | {stratum['sampling_weight']:.6f} |")
    lines += [
        "",
        "## B. Table inventory",
        "",
        "| Parquet table | Rows | Unique keys | Columns | Bytes | SHA-256 |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for name, item in manifest["tables"].items():
        lines.append(f"| `{name}` | {item['rows']:,} | {item['unique_keys']:,} | {item['columns']} | {item['bytes']:,} | `{item['sha256']}` |")
    lines += [
        "",
        "## C. Missingness audit",
        "",
        f"All rates use the {quality['records']:,}-work detailed-sample denominator; these are not population prevalence estimates.",
        "",
        "| Field/coverage | Missing | Percent | Phase 2 missing | Difference |",
        "|---|---:|---:|---:|---:|",
    ]
    for name, count in quality["missing"].items():
        lines.append(f"| {name} | {count:,} | {100 * count / quality['records']:.2f}% | {quality['phase2_missing'][name]:,} | {quality['missing_difference_vs_phase2'][name]:+d} |")
    for group_name, heading in (("publication_year", "By publication year"), ("work_type", "By work type")):
        lines += ["", f"### {heading}", "", "| Group | Works | Missing title | DOI | Abstract | FWCI | Institution | Country | Language | OA |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
        for group, entry in quality["by"][group_name].items():
            m = entry["missing"]
            lines.append(f"| {group} | {entry['records']:,} | {m['title']:,} | {m['doi']:,} | {m['abstract']:,} | {m['fwci']:,} | {m['institution']:,} | {m['country']:,} | {m['language']:,} | {m['open_access']:,} |")
    lines += [
        "",
        f"FWCI missing by type: {', '.join(f'{kind}: {fwci_by_type[kind]:,}/{type_counts[kind]:,}' for kind in sorted(type_counts))}. All sampled preprints lack FWCI; cross-type FWCI comparisons must exclude or separately treat them.",
        f"Affiliation uncertainty: international collaboration is unknown for {quality['unknown_international_collaboration']:,} works and institutional collaboration for {quality['unknown_institutional_collaboration']:,}; unknown is not domestic/single-institution.",
        f"Reference-list source status: {', '.join(f'{key}={value:,}' for key, value in sorted(quality['reference_list_status'].items()))}. An absent list is not a confirmed zero-reference work.",
        "",
        "## D. Integrity and classification audit",
        "",
        f"- Validation: **{sum(v['status'] == 'PASS' for v in manifest['validation'].values())}/{len(manifest['validation'])} PASS**. Checks cover corpus/date/type/retraction, canonical and unique IDs, six plan strata and nominal weights, composite keys, bridge-table foreign keys, OA/FWCI/citation consistency, population-series separation and file checksums.",
        f"- Processing issues: {len(quality['issues'])}; by field: `{json.dumps(quality['issue_counts'], sort_keys=True)}`. See `quality.json` for row-level quarantine records.",
        "- OpenAlex-native and custom text-derived memberships are independent overlapping layers. Unmatched text is not a validated negative, especially where abstracts are unavailable.",
        "",
        "| Layer | Category | Matched works |",
        "|---|---|---:|",
    ]
    for (layer, category), count in sorted(category_counts.items()):
        lines.append(f"| {layer} | {category} | {count:,} |")
    if compare_dir is not None:
        comparison = json.loads((compare_dir / "manifest.json").read_text())
        if comparison.get("status") != "complete" or comparison.get("inputs") != manifest["inputs"]:
            raise ValueError("Comparison run is incomplete or has different source inputs")
        mismatches = [
            name for name, item in manifest["tables"].items()
            if comparison["tables"][name]["sha256"] != item["sha256"]
            or file_sha256(compare_dir / f"{name}.parquet") != item["sha256"]
        ]
        if comparison["quality_json_sha256"] != manifest["quality_json_sha256"]:
            mismatches.append("quality.json")
        if mismatches:
            raise ValueError(f"Deterministic rerun differs: {mismatches}")
        lines += [
            "",
            f"- Independent rerun: `{compare_dir}`; all {len(manifest['tables'])} Parquet SHA-256 checksums and the quality JSON checksum match exactly. Processing timestamps and code hashes in manifests are separate metadata and need not match.",
        ]
    lines += [
        "",
        "## E. Engineered features and null policy",
        "",
        "- `publication_age_years = (collection completion timestamp - publication_date).days / 365.2425`; the same observation timestamp is used for every work, and future-dated records fail validation.",
        "- `log1p_citations = ln(1 + cited_by_count)`; `zero_citation_flag` is true only for an observed zero. Outliers are retained. `has_fwci` reflects presence; missing FWCI remains null, never zero-imputed.",
        "- `has_oa_metadata` requires both OA fields. Binary OA and status must agree; missing OA is never assumed closed.",
        "- Authorship count counts positions. Identified author, institution and country counts use unique identifiers/codes. Collaboration flags are true only with at least two observed entities; false requires complete relevant affiliation coverage; otherwise null.",
        "- Text lengths use normalized but case-preserving source text. Native/custom category counts and LLM/Multimodal/RAG flags describe matching rules, not ground-truth labels.",
        "- Future ML must split by unique Work ID before fitting any vocabulary or statistical transform; duplicate relationships must not leak across train/test partitions.",
        "",
        "## F. Research limitations",
        "",
        "- The `N_h/n_h` year-stratum weights are **nominal**: OpenAlex server-side sample uniformity and snapshot stability are unverified. Do not treat weighted category estimates as design-unbiased population totals.",
        "- Population publication trends must come from `population_year_counts`, not the detailed sample. Native topic series may overlap; custom LLM/RAG/Multimodal matches have no population aggregate here.",
        "- Missing abstracts limit lexical recall; OpenAlex taxonomy may misclassify or miss topics. Missing affiliations constrain collaboration analysis and may be nonrandom.",
        "- Citations accumulate with publication age and are not scientific quality. FWCI excludes every sampled preprint. Open Access–impact associations are observational, not causal.",
        "- All findings describe the approved AI/CV primary-subfield OpenAlex corpus, not all global AI research.",
        "",
        "## G. Phase 4 readiness",
        "",
        "- Publication trends: **ready** using validated population series; do not infer prevalence from sample category proportions.",
        "- Citation impact: **ready with restrictions**: age-aware and field/type-aware comparisons; FWCI only where observed and preprints handled separately.",
        "- OA association: **ready for descriptive/adjusted observational analysis**, with no causal interpretation.",
        "- Collaboration: **ready for affiliation-observed subset/sensitivity analyses**; retain unknown states and report coverage.",
        "- Topic comparisons: **ready as method-specific, overlapping descriptive analyses**; do not equate native and custom category counts.",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    text = render_report(args.processed_dir, args.compare_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
