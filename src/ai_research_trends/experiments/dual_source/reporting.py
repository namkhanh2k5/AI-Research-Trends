"""Generate aggregate-only RQ7 figures and reports from verified local artifacts."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
import time

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from ai_research_trends.experiments.dual_source.pipeline import DEFAULT_RUN, read_json, verify
from ai_research_trends.preprocessing.validate_tables import file_sha256


REPORT_DIR = Path("reports/experiments")
FIG_DIR = Path("reports/figures/dual_source_etl")


def _table(stage: dict[str, dict[str, int]]) -> str:
    fields = ["valid_doi", "abstract", "publisher", "venue_name", "issns",
              "publication_date", "license", "invalid_doi", "duplicate_work_ids", "duplicate_dois"]
    lines = ["| Metric | Raw OpenAlex | Cleaned OpenAlex | Integrated | Integrated − cleaned |",
             "|---|---:|---:|---:|---:|"]
    for field in fields:
        a, b, c = (stage[key].get(field, 0) for key in
                   ("raw_openalex", "cleaned_openalex", "integrated"))
        lines.append(f"| {field} | {a:,} | {b:,} | {c:,} | {c-b:+,} |")
    n = stage["raw_openalex"]["records"]
    lines.append(f"| Work-level raw/provenance evidence | {n:,} | {n:,} | {n:,} | 0 |")
    lines.append("| Cross-provider differences | N/A | N/A | see conflict audit | N/A |")
    return "\n".join(lines)


def _bar(path: Path, labels: list[str], values: list[float], title: str,
         *, ylabel: str = "Works", color: str = "#3977a8") -> None:
    fig, ax = plt.subplots(figsize=(8, 4.2))
    ax.bar(labels, values, color=color)
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ax.tick_params(axis="x", rotation=35)
    for tick in ax.get_xticklabels():
        tick.set_horizontalalignment("right")
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def _figures(run: Path, eval_data: dict, canonical: pd.DataFrame,
             conflicts: pd.DataFrame, duplicates: pd.DataFrame, collection: dict) -> dict:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    stage = eval_data["stage"]
    quality_fields = ["doi", "abstract", "publisher", "venue_name", "issns", "publication_date", "license"]
    matrix = np.array([[stage[key][field] / stage[key]["records"] for field in quality_fields]
                       for key in ("raw_openalex", "cleaned_openalex", "integrated")])
    fig, ax = plt.subplots(figsize=(9, 3.4))
    image = ax.imshow(matrix, vmin=0, vmax=1, cmap="Blues")
    ax.set_yticks(range(3), ["Raw OpenAlex", "Cleaned OpenAlex", "Integrated"])
    ax.set_xticks(range(len(quality_fields)), quality_fields, rotation=35, ha="right")
    for row in range(3):
        for column in range(len(quality_fields)):
            ax.text(column, row, f"{matrix[row, column]:.1%}", ha="center", va="center", fontsize=8,
                    color="white" if matrix[row, column] > .6 else "black")
    fig.colorbar(image, ax=ax, label="Coverage in fixed 1,500-work cohort")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "01_missingness_before_after.png", dpi=160)
    plt.close(fig)
    _bar(FIG_DIR / "02_provider_completeness.png", quality_fields,
         [stage["cleaned_openalex"][f] for f in quality_fields], "OpenAlex metadata completeness (n=1,500)")
    _bar(FIG_DIR / "03_doi_match_status.png", list(eval_data["match_status"]),
         list(eval_data["match_status"].values()), "Exact DOI linkage and provider outcomes")
    years = sorted(canonical.publication_year.dropna().unique().tolist())
    publisher_recovery = []
    venue_recovery = []
    issn_recovery = []
    for year in years:
        part = canonical.loc[canonical.publication_year.eq(year)]
        publisher_recovery.append(int(part.publisher_source.eq("crossref").sum()))
        venue_recovery.append(int(part.venue_name_source.eq("crossref").sum()))
        issn_recovery.append(int(part.issns_source.eq("crossref").sum()))
    _bar(FIG_DIR / "04_publisher_recovery_year.png", [str(y) for y in years], publisher_recovery,
         "Crossref publisher additions by year")
    _bar(FIG_DIR / "05_venue_issn_recovery.png", ["Venue", "ISSN"],
         [sum(venue_recovery), sum(issn_recovery)], "Identifier-checked Crossref additions")
    by_type = canonical.groupby("work_type", dropna=False).agg(
        missing_publisher=("publisher", lambda v: int(v.isna().sum())),
        missing_venue=("venue_name", lambda v: int(v.isna().sum())))
    _bar(FIG_DIR / "06_quality_issues_work_type.png", by_type.index.astype(str).tolist(),
         by_type.missing_publisher.tolist(), "Missing publisher after integration, by work type")
    year_conflicts = conflicts.loc[conflicts.field.eq("publication_year")] if not conflicts.empty else conflicts
    counts = year_conflicts.work_id.map(dict(zip(canonical.work_id, canonical.publication_year))).value_counts() if not year_conflicts.empty else pd.Series(dtype=int)
    _bar(FIG_DIR / "07_publication_year_conflicts.png", [str(y) for y in years],
         [int(counts.get(y, 0)) for y in years], "Cross-provider publication-year differences")
    issue_counts = duplicates.issue.value_counts() if not duplicates.empty else pd.Series(dtype=int)
    _bar(FIG_DIR / "08_duplicate_and_drift_audit.png", issue_counts.index.astype(str).tolist() or ["none"],
         issue_counts.tolist() or [0], "Identity warnings and snapshot drift")
    _bar(FIG_DIR / "09_retraction_evidence.png", ["OpenAlex retracted", "Crossref explicit evidence"],
         [int(canonical.is_retracted.eq(True).sum()), int(canonical.crossref_retraction_evidence.eq(True).sum())],
         "Retraction evidence, originally non-retracted cohort")
    _bar(FIG_DIR / "10_request_efficiency.png", ["OA HTTP", "CR HTTP", "CR cached", "CR 200", "CR 404"],
         [collection["openalex_http_attempts"], collection["crossref_http_attempts"],
          sum(bool(e.get("cache_source")) for e in collection["crossref"]),
          sum(e["status_code"] == 200 for e in collection["crossref"]),
          sum(e["status_code"] == 404 for e in collection["crossref"])],
         "Bounded pilot request and response counts", ylabel="Requests or DOI tasks")
    return {p.name: {"sha256": file_sha256(p), "bytes": p.stat().st_size}
            for p in sorted(FIG_DIR.glob("*.png"))}


def generate(run: Path = DEFAULT_RUN) -> dict:
    validation_started = time.monotonic()
    verification = verify(run)
    validation_seconds = round(time.monotonic() - validation_started, 3)
    eval_data = read_json(run / "evaluation.json")
    collection = read_json(run / "collection_manifest.json")
    connection = read_json(run / "connection_preflight.json")
    processed = read_json(run / "processing_manifest.json")
    validation_path = run / "validation_evidence.json"
    validation = read_json(validation_path) if validation_path.is_file() else None
    validation_summary = (f"{validation['pytest_passed']} passed, {validation['pytest_skipped']} skipped, "
                          f"{validation['pytest_failed']} failed; pip check: {validation['pip_check']}"
                          if validation else "NOT VERIFIED on this machine")
    canonical = pd.read_parquet(run / "processed/canonical_works.parquet")
    provenance = pd.read_parquet(run / "processed/field_provenance.parquet")
    conflicts = pd.read_parquet(run / "processed/metadata_conflicts.parquet")
    duplicates = pd.read_parquet(run / "processed/duplicate_audit.parquet")
    # Provenance columns are derived from the table, not separately guessed.
    for field in ("publisher", "venue_name", "issns"):
        source = provenance.loc[provenance.field.eq(field), ["work_id", "selected_source"]]
        canonical[field + "_source"] = canonical.work_id.map(dict(zip(source.work_id, source.selected_source)))
    figures = _figures(run, eval_data, canonical, conflicts, duplicates, collection)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    stage = eval_data["stage"]
    group_a_n = eval_data["by_group"]["A_GENERAL"]["raw_openalex"]["records"]
    group_b_n = eval_data["by_group"]["B_TARGETED_MISSINGNESS"]["raw_openalex"]["records"]
    table = _table(stage)
    group_a = _table(eval_data["by_group"]["A_GENERAL"])
    group_b = _table(eval_data["by_group"]["B_TARGETED_MISSINGNESS"])
    cross_200 = sum(e["status_code"] == 200 for e in collection["crossref"])
    cross_404 = sum(e["status_code"] == 404 for e in collection["crossref"])
    cached = sum(bool(e.get("cache_source")) for e in collection["crossref"])
    matched = eval_data["match_status"].get("EXACT_DOI_MATCH", 0)
    match_rate = matched / len(collection["crossref"]) if collection["crossref"] else 0.0
    fetched = collection["crossref_http_attempts"]
    source_bytes = sum(e["bytes"] for e in collection["openalex"] + collection["crossref"] + collection.get("openalex_aliases", []))
    processed_bytes = sum(item["bytes"] for item in processed["outputs"].values())
    collection_seconds = round((datetime.fromisoformat(collection["completed_at_utc"]) -
                                datetime.fromisoformat(collection["started_at_utc"])).total_seconds(), 3)
    openalex_reported_costs = []
    for entry in collection["openalex"]:
        payload = read_json(run / entry["path"])
        value = ((payload.get("meta") or {}).get("x_query") or {}).get("cost_usd")
        if isinstance(value, (int, float)):
            openalex_reported_costs.append(float(value))
    observed_cost = (f"${sum(openalex_reported_costs):.6f} across {len(openalex_reported_costs)} batch responses"
                     if openalex_reported_costs else "NOT AVAILABLE in stored responses")
    recovered = eval_data["recovery"]
    recovery_lines = ["| Field | Missing before | Crossref available | Valid additions | Deferred | Conflicts | Missing after |",
                      "|---|---:|---:|---:|---:|---:|---:|"]
    recovery_lines += [f"| {field} | {m['missing_before']:,} | {m['crossref_available']:,} | {m['validated_additions']:,} | {m['rejected_or_deferred_additions']:,} | {m['conflicts']:,} | {m['missing_after']:,} |"
                       for field, m in recovered.items()]
    recovery_table = "\n".join(recovery_lines)
    inventory_lines = ["| Table | Rows | Columns | Bytes | SHA-256 |", "|---|---:|---:|---:|---|"]
    inventory_lines += [f"| `{name}.parquet` | {entry['rows']:,} | {len(entry['columns'])} | {entry['bytes']:,} | `{entry['sha256']}` |"
                        for name, entry in processed["outputs"].items()]
    inventory_table = "\n".join(inventory_lines)
    collected = f"""# Dual-source collection — observed RQ7 pilot

- Cohort: {len(canonical):,} original-sample works from 2020–2024; Group A {group_a_n:,}, Group B {group_b_n:,}.
- New OpenAlex HTTP attempts: {collection['openalex_http_attempts']:,}; verified batch responses: {len(collection['openalex']):,}; singleton alias probes: {len(collection.get('openalex_aliases', [])):,}.
- Crossref DOI tasks: {len(collection['crossref']):,}; fresh HTTP attempts: {fetched:,}; reused prior checksum-verified cache: {cached:,}.
- Crossref HTTP 200: {cross_200:,}; HTTP 404: {cross_404:,}; parsed exact DOI matches: {matched:,} ({match_rate:.1%} of DOI tasks).
- Raw response bytes stored: {source_bytes:,}; request cap: 1,500 new Crossref HTTP attempts.
- Collection elapsed: {collection_seconds:,.3f} seconds. Provider-normalization/integration elapsed: {eval_data['processing_seconds']:,.3f} seconds. Read-only validation elapsed: {validation_seconds:,.3f} seconds. Processed Parquet bytes: {processed_bytes:,}.
- OpenAlex provider-reported batch query cost: {observed_cost}; singleton alias probes are not included in this sum. Crossref is a public Polite API, not a paid Plus account.
- Historical collection anomalies: {len(collection['errors']):,} recorded OpenAlex ID-drift/checkpoint events, subsequently verified through singleton alias evidence. Completed-run HTTP 429/5xx final responses: {sum(e['status_code'] in (429, 500, 502, 503, 504) for e in collection['crossref']):,}. Intermediate retry status codes were not separately persisted, so their exact breakdown is NOT VERIFIED.
- Crossref connection preflight at {connection['checked_at_utc']}: HTTP {connection['crossref']['status_code']}, observed `x-api-pool={connection['crossref']['pool']}`; rate-limit header {connection['crossref']['rate_limit']}/{connection['crossref']['rate_interval']}, concurrency header {connection['crossref']['concurrency_limit']}. These are observations, not permanent guarantees.
- OpenAlex connection preflight: HTTP {connection['openalex']['status_code']} with configured bearer key; observed remaining credits {connection['openalex']['remaining']} of {connection['openalex']['limit']} at the preflight time. Provider-reported per-response credit data are retained in local raw manifests.
- Collection started: {collection['started_at_utc']}; completed: {collection.get('completed_at_utc', 'NOT COMPLETE')}.
- Source frame and selection checksums: local `plan.json`; raw response checksums: local `collection_manifest.json`.

Official access documentation: [Crossref](https://www.crossref.org/documentation/retrieve-metadata/rest-api/access-and-authentication/), [OpenAlex](https://help.openalex.org/api/authentication/).
"""
    current_retractions = int(canonical.is_retracted.eq(True).sum())
    cleaning = f"""# Dual-source cleaning — observed RQ7 pilot

Three stages use the same {len(canonical):,} Work IDs. No missing bibliometric values were imputed. OpenAlex inverted-index abstracts were reconstructed; Crossref markup is sanitized only for comparison and is not published.

{table}

Exact DOI matching is mandatory. Crossref 404 means not found in this registry at this snapshot, not an invalid DOI. The {eval_data['match_status'].get('IDENTIFIER_CONFLICT', 0):,} DOI-mismatched HTTP 200 responses remain raw evidence but are quarantined from canonical field merging; `provider_links.quarantine_reason` records the decision. Different publication years can reflect online versus print dates and are preserved as conflicts, not automatically fixed. Crossref `container-title` fills a missing *venue name* but does not establish a stable venue identity. OpenAlex remains the frame authority; a Crossref retraction relation does not silently alter original corpus membership.

Observed field-level disagreements: {len(conflicts):,}; snapshot-drifted works: {eval_data['snapshot_drift_work_count']:,}; duplicate/shared-DOI and drift audit rows: {len(duplicates):,}. Provider type labels use different taxonomies and account for {eval_data['conflicts_by_field'].get('work_type', 0):,} differences; these are **not** 944 proven work-type errors. Invalid ISSN values observed: OpenAlex {eval_data['invalid_openalex_issn_values']:,}; Crossref {eval_data['invalid_crossref_issn_values']:,}. Malformed OpenAlex abstract indexes: {eval_data['malformed_openalex_abstracts']:,}, flagged without inventing text. Current OpenAlex records outside the original frame definition: {eval_data['current_out_of_frame_count']:,}; non-disjoint reasons: {eval_data['current_out_of_frame_reasons_not_disjoint']}. Current retraction flags: {current_retractions:,}. These are flagged for review, not silently removed. Raw provider evidence remains immutable in the local run directory.
"""
    integration = f"""# Dual-source canonical integration — observed RQ7 pilot

Canonical grain: one row per selected original OpenAlex Work ID. The current OpenAlex ID is retained separately where an ID redirect occurred. Crossref records are linked only by exact normalized DOI.

| Provider linkage status | Works |
|---|---:|
""" + "\n".join(f"| {k} | {v:,} |" for k, v in sorted(eval_data["match_status"].items())) + f"""

Canonical rows: {len(canonical):,}; exact DOI matches: {matched:,}; field-level provenance rows: {len(provenance):,}; conflict rows: {len(conflicts):,}. Nine Parquet outputs are in the local Git-ignored `processed/` directory. Their full schemas and hashes are in `processing_manifest.json`.

{inventory_table}

Precedence: OpenAlex owns identity, study period, work type, title, publication date, citations, FWCI, OA, primary topic and retraction status. Crossref fills only missing publisher, venue name, valid ISSN and license metadata. A recovered venue name is not a verified journal/conference identity. Conflicting provider values are retained in `metadata_conflicts.parquet`; they are not silently overwritten. A DOI match proves identifier linkage, not correctness of every field.
"""
    quality = f"""# RQ7 — Dual-source data-quality evaluation

The experiment compares raw current OpenAlex, normalized current OpenAlex, and OpenAlex+Crossref on **the same** selected {len(canonical):,} works. Group B is intentionally enriched for missingness and is not representative of the OpenAlex population.

## Combined cohort

{table}

## Group A — general evaluation (n={group_a_n:,})

{group_a}

## Group B — targeted missingness (n={group_b_n:,})

{group_b}

## Per-field recovery

{recovery_table}

“Valid additions” means exact DOI linkage plus the field's basic parsing/identifier policy, **not** independent confirmation that a publisher, venue name or license is scientifically correct.

Matched Crossref records: {matched:,}; title/year/type/provider conflicts: {len(conflicts):,} field-level rows. Provider agreement is **not** independent correctness proof. Independent manual correctness assessment: **NOT VERIFIED**. Missing Crossref retraction evidence does not establish non-retraction.

The {eval_data['conflicts_by_field'].get('work_type', 0):,} work-type string differences largely reflect different provider taxonomies, not proven cataloguing mistakes. Crossref license arrays and OpenAlex license strings are not directly equivalent; coverage counts mean *some provider metadata exists*, not that rights have been independently adjudicated. The original-sample frame remains authoritative; {eval_data['current_out_of_frame_count']:,} fresh OpenAlex records no longer satisfy the original membership definition and are reported as snapshot drift rather than silently dropped. OpenAlex population prevalence and official RQ1–RQ6 estimates are unchanged.

Figures: [missingness](../figures/dual_source_etl/01_missingness_before_after.png), [match status](../figures/dual_source_etl/03_doi_match_status.png), [publisher recovery](../figures/dual_source_etl/04_publisher_recovery_year.png), [request efficiency](../figures/dual_source_etl/10_request_efficiency.png). Ten aggregate-only PNGs are available in `reports/figures/dual_source_etl/`.
"""
    # Rate and storage projections are arithmetic scenarios, not predictions of provider coverage.
    scenarios = []
    for n in (1500, 5000, 12000, 25000, 50000, 100000):
        multiplier = n / len(canonical)
        scenarios.append(f"| {n:,} | {int(round(fetched * multiplier)):,} | {int(round(source_bytes * multiplier / 1024**2)):,} MiB |")
    scenario_table = "\n".join(["| Cohort size | Fresh Crossref HTTP attempts at observed rate | Raw response storage at observed size |",
                                "|---:|---:|---:|", *scenarios])
    gain = sum(recovered[f]["validated_additions"] for f in ("publisher", "venue_name", "issns", "license"))
    verdict = "CONDITIONAL GO" if gain > 0 and verification["status"] == "PASS" else "NO-GO"
    scale = f"""# Dual-source ETL scale-up decision

Verdict: **{verdict}** for a bounded follow-on to the original 12,000-work sample; **no authorization for a new crawl**. Incremental metadata additions across publisher, venue, ISSN and license: {gain:,} field instances (not unique works). Exact linked works: {matched:,} / {len(canonical):,}. Independent correctness remains unverified, so full-scale enrichment should be preceded by a small human/official-source validation of recovered fields.

Measured new OpenAlex attempts: {collection['openalex_http_attempts']:,}; new Crossref attempts: {fetched:,}; cache hits: {cached:,}; raw bytes: {source_bytes:,}. These scenarios linearly scale observed request/storage rates from the mixed A+B pilot and do **not** predict match rate, representative missingness, rate limits, or fees:

{scenario_table}

At 12,000 works, expected calls depend on DOI availability, cache reuse, registry coverage and provider changes. Group A should be used for rough scenario planning, not targeted Group B. A full 937k-work dual-source crawl is out of scope.
"""
    main = f"""# Dual-source OpenAlex + Crossref ETL pilot — final RQ7 report

**Verdict: {verdict}.** This is a bounded data-engineering experiment, not a replacement for RQ1–RQ6 or the frozen topic classifier.

## Architecture and cohort

The original verified 2020–2024 OpenAlex analytical sample supplies {group_a_n:,} proportionally stratified general works and {group_b_n:,} disjoint DOI-bearing works with pre-specified metadata gaps. Newly retrieved OpenAlex metadata is the before/after baseline. Crossref is a secondary DOI-matched source. Current-versus-original OpenAlex differences are tracked separately as snapshot drift. The cohort is not a probability sample of the full originally defined AI/CV population.

## Collection and integration

{len(collection['openalex']):,} verified OpenAlex batch responses, {len(collection['crossref']):,} Crossref DOI tasks, {cached:,} verified cache hits, {matched:,} exact DOI matches. Crossref 404: {cross_404:,}. OpenAlex ID aliases verified by singleton probes: {len(collection.get('openalex_aliases', [])):,}. Canonical Work rows: {len(canonical):,}.

{table}

## Scientific interpretation

Crossref can fill some missing deposited publisher, venue-name, ISSN and license fields, but does not prove their scientific correctness or resolve all venue identities. It does not repair OpenAlex population estimates or make targeted pilot proportions population representative. Online/print dates and work-type taxonomies can disagree; both provider values remain in conflict records. Abstracts are never published. The existing 100-work retraction audit remains separate from this originally non-retracted main cohort; {current_retractions:,} current OpenAlex retraction flags require separate interpretation.

## Downstream usability

Publisher/venue/ISSN additions can improve pilot descriptive subgroup metadata. No official RQ1–RQ6 result is recomputed; no frozen model is retrained; no 2025 sealed label or reviewer file was opened. The dual-source dataset is not automatically substituted into the web app.

## Evidence

Collection: [report](experiments/DUAL_SOURCE_COLLECTION_REPORT.md). Cleaning: [report](experiments/DUAL_SOURCE_CLEANING_REPORT.md). Integration: [report](experiments/DUAL_SOURCE_INTEGRATION_REPORT.md). Quality: [report](experiments/RQ7_DUAL_SOURCE_DATA_QUALITY.md). Scale-up: [decision](experiments/DUAL_SOURCE_SCALE_UP_DECISION.md). Local record-level evidence and SHA-256 manifests: `{run}`. Final offline tests: {validation_summary}.
"""
    reports = {"DUAL_SOURCE_COLLECTION_REPORT.md": collected,
               "DUAL_SOURCE_CLEANING_REPORT.md": cleaning,
               "DUAL_SOURCE_INTEGRATION_REPORT.md": integration,
               "RQ7_DUAL_SOURCE_DATA_QUALITY.md": quality,
               "DUAL_SOURCE_SCALE_UP_DECISION.md": scale}
    for name, content in reports.items():
        (REPORT_DIR / name).write_text(content, encoding="utf-8")
    Path("reports/DUAL_SOURCE_ETL_PILOT_FINAL_REPORT.md").write_text(main, encoding="utf-8")
    handoff = f"""# Independent RQ7 review handoff

- Branch: `experiment/dual-source-etl-pilot-rq7`; source parent: `5af0729329f77bd58445ce289f1daddd56f9cfdb`.
- Local run: `{run}`. Selected/canonical Work IDs: {len(canonical):,}. Group A/B: {group_a_n:,}/{group_b_n:,}.
- OpenAlex attempts/batches/aliases: {collection['openalex_http_attempts']:,}/{len(collection['openalex']):,}/{len(collection.get('openalex_aliases', [])):,}.
- Crossref fresh attempts/cache hits/200/404/exact parsed matches: {fetched:,}/{cached:,}/{cross_200:,}/{cross_404:,}/{matched:,}.
- Local manifests: `plan.json`, `collection_manifest.json`, `processing_manifest.json`, `evaluation.json`; verifier: {verification['status']}.
- Redacted connection evidence: `connection_preflight.json`; SHA-256 `{file_sha256(run / 'connection_preflight.json')}`.
- Canonical schema: `{', '.join(canonical.columns)}`.
- SHA-256 verified: {verification['sha256_verified']:,} stored artifacts. Source frame, old raw snapshot and prior cache hashes are in local manifests.
- Offline validation: {validation_summary}. Deterministic Parquet rerun: {validation['deterministic_rerun'] if validation else 'NOT VERIFIED'}. Local validation-evidence SHA-256: {file_sha256(validation_path) if validation else 'NOT AVAILABLE'}.
- Environment diagnostic: {validation['diagnostic_note'] if validation else 'NOT VERIFIED'}
- Data-product inventory:\n\n{inventory_table}
- Reproduction: `openalex-dual-source verify --run {run}`; `openalex-report-dual-source --run {run}`. Collection is immutable once complete.
- Independent correctness check: NOT VERIFIED. Provider agreement is not ground truth. Never open sealed 2025 labels.
"""
    Path("reports/DUAL_SOURCE_ETL_REVIEW_HANDOFF.md").write_text(handoff, encoding="utf-8")
    figure_manifest = {"run_id": run.name, "source_evaluation_sha256": file_sha256(run / "evaluation.json"),
                       "figures": figures}
    (FIG_DIR / "manifest.json").write_text(json.dumps(figure_manifest, indent=2) + "\n", encoding="utf-8")
    return {"verdict": verdict, "reports": len(reports) + 2, "figures": len(figures),
            "figure_bytes": sum(x["bytes"] for x in figures.values()), "verification": verification}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, default=DEFAULT_RUN)
    args = parser.parse_args()
    print(json.dumps(generate(args.run), indent=2))


if __name__ == "__main__":
    main()
