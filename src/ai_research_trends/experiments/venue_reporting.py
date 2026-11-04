"""Publish aggregate-only venue feasibility reports and figures from verified local metrics."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml

from ai_research_trends.experiments.venue_inventory import ORIGINAL_RAW, EXPANSION_RAW
from ai_research_trends.preprocessing.validate_tables import file_sha256


def _read(path: Path) -> dict:
    return json.loads(path.read_text())


def _pct(number: float, denominator: float) -> str:
    return f"{100 * number / denominator:.1f}%" if denominator else "n/a"


def _write(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body.rstrip() + "\n", encoding="utf-8")


def _figures(root: Path, report_dir: Path, inv: dict, integration: dict,
             retrieval: dict, cross: dict, sources: dict) -> list[str]:
    out = report_dir.parent / "figures" / "venue_experiment"
    out.mkdir(parents=True, exist_ok=True)
    names = []
    def save(name: str) -> None:
        plt.tight_layout()
        plt.savefig(out / name, dpi=170, bbox_inches="tight")
        plt.close()
        names.append(name)
    before, after = integration["before"], integration["after"]
    keys = ["resolved_identifier", "rankable_journal_or_conference", "missing_name", "missing_publisher_both_providers", "missing_issn"]
    x = np.arange(len(keys))
    plt.figure(figsize=(9, 4))
    plt.bar(x - .18, [before[k] for k in keys], width=.36, label="Local OpenAlex")
    plt.bar(x + .18, [after[k] for k in keys], width=.36, label="OpenAlex + Crossref")
    plt.xticks(x, [v.replace("_", "\n") for v in keys], fontsize=8)
    plt.ylabel(f"Records in matched cohort (n={integration['selected_cohort']})")
    plt.legend()
    save("before_after_completeness.png")
    years = sorted(inv["by_year"])
    heat = np.array([[1 - inv["by_year"][y][field] / inv["by_year"][y]["records"]
                      for field in ("doi", "primary_source", "any_source", "resolved_journal")]
                     for y in years])
    plt.figure(figsize=(7, 4))
    plt.imshow(heat, vmin=0, vmax=1, cmap="YlOrRd")
    plt.colorbar(label="Missing/unresolved share")
    plt.yticks(range(len(years)), years)
    plt.xticks(range(4), ["DOI", "Primary source", "Any source", "Journal venue"], rotation=20)
    save("missingness_by_year.png")
    links = pd.read_parquet(root / "paper_venue_links.parquet")
    counts = links.match_status.value_counts()
    plt.figure(figsize=(6, 4))
    plt.bar(counts.index.astype(str), counts.values)
    plt.ylabel("Unique historical Work IDs")
    plt.xticks(rotation=20, ha="right")
    save("match_status.png")
    plt.figure(figsize=(6, 4))
    labels = ["ISSN", "Venue type", "Publication year", "Identity"]
    values = [integration["issn_conflicts"], integration["type_conflicts"],
              integration["publication_year_conflicts"], integration["identity_conflicts"]]
    plt.bar(labels, values)
    plt.ylabel("Selected-cohort records")
    save("provider_conflicts.png")
    types = integration["venue_types"]
    plt.figure(figsize=(6, 4))
    plt.bar(list(types), list(types.values()))
    plt.ylabel("Canonical venue identities")
    save("venue_type_distribution.png")
    plt.figure(figsize=(7, 4))
    labels = ["Crossref venue ID gain", "OpenAlex Source publisher gain", "Crossref publisher available"]
    values = [after["resolved_identifier"] - before["resolved_identifier"],
              integration["source_api_publisher_recovered"],
              integration["crossref_publisher_available_where_local_missing"]]
    plt.bar(labels, values)
    plt.ylabel("Records in the paired selected cohort")
    plt.xticks(rotation=15, ha="right")
    save("enrichment_yield.png")
    plt.figure(figsize=(6, 4))
    plt.bar(["Crossref DOI", "OpenAlex Source", "OpenAlex retraction"],
            [cross["http_attempts"], sources["http_attempts"], 1])
    plt.ylabel("HTTP requests; bounded pilot")
    save("request_efficiency.png")
    return names


def publish(inventory_dir: Path, report_dir: Path) -> dict:
    inv = _read(inventory_dir / "inventory_metrics.json")
    integration = _read(inventory_dir / "integration_metrics.json")
    retrieval = _read(inventory_dir / "retrieval_metrics.json")
    breakdown = _read(inventory_dir / "retrieval_breakdown.json")
    cross = _read(inventory_dir / "crossref" / "crossref_request_manifest.json")
    sources = _read(inventory_dir / "openalex_sources_api" / "openalex_source_request_manifest.json")
    retract = _read(inventory_dir / "retractions" / "openalex_retraction_manifest.json")
    retract_cross = _read(inventory_dir / "retractions" / "crossref_retractions" / "crossref_request_manifest.json")
    retframe = pd.read_parquet(inventory_dir / "retractions" / "retraction_comparison.parquet")
    validation = _read(inventory_dir / "validation_results.json")
    head = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False).stdout.strip()
    figure_names = _figures(inventory_dir, report_dir, inv, integration, retrieval, cross, sources)
    figures = "\n".join(f"![{name}](../figures/venue_experiment/{name})" for name in figure_names)
    overall = inv["overall"]
    inventory = f"""# Venue Data Inventory — 2020–2024 only

Source: verified original Phase 2 raw JSONL and verified targeted expansion; 2025 sealed records/labels excluded. The inventory is **not** a population-prevalence estimate.

| Measure | Observed count |
|---|---:|
| Source records | {overall['records']:,} |
| Unique Work IDs | {inv['unique_work_ids']:,} |
| DOI-bearing records | {overall['doi']:,} |
| Primary OpenAlex source | {overall['primary_source']:,} |
| Any hosting source | {overall['any_source']:,} |
| Multiple hosting sources | {overall['multiple_hosting_sources']:,} |
| Resolved journal-type source | {overall['resolved_journal']:,} |
| Resolved conference-type source | {overall['resolved_conference']:,} |
| Repository host (not a journal) | {overall['repository_host']:,} |
| Ambiguous published locations | {overall['ambiguous']:,} |
| No eligible published venue | {overall['unmatched']:,} |
| Distinct source IDs in any location | {inv['distinct_source_ids']:,} |

The 11,539 source records consist of {inv['origins']['original_analytical_sample']:,} original 2020–24 records and {inv['origins']['targeted_ml_expansion']:,} targeted 2020–23 records. There are {overall['records']-inv['unique_work_ids']} duplicated Work IDs across origins; later paper–venue links select one deterministic record and retain a row-level audit. The original 12,000-work research sample is not redefined by this experiment.

## By publication year

| Year | Records | DOI | Primary source | Journal venue | Conference venue | Unmatched |
|---|---:|---:|---:|---:|---:|---:|
"""
    for year, m in inv["by_year"].items():
        inventory += f"| {year} | {m['records']:,} | {m['doi']:,} | {m['primary_source']:,} | {m['resolved_journal']:,} | {m['resolved_conference']:,} | {m['unmatched']:,} |\n"
    inventory += "\n## By work type\n\n| Type | Records | Journal | Conference | Unmatched |\n|---|---:|---:|---:|---:|\n"
    for kind, m in inv["by_work_type"].items():
        inventory += f"| {kind} | {m['records']:,} | {m['resolved_journal']:,} | {m['resolved_conference']:,} | {m['unmatched']:,} |\n"
    catalogue = yaml.safe_load(Path("config/phase6b_catalogue.yaml").read_text())
    inventory += "\n## Fourteen selected OpenAlex topics (descriptive)\n\n| Topic ID | Records | Journal | Conference | Unmatched |\n|---|---:|---:|---:|---:|\n"
    for short in catalogue["catalogue_b"]:
        m = inv["by_primary_topic"].get("https://openalex.org/" + short)
        if m:
            inventory += f"| {short} | {m['records']:,} | {m['resolved_journal']:,} | {m['resolved_conference']:,} | {m['unmatched']:,} |\n"
    inventory += """

Topic-specific breakdowns are stored in `inventory_metrics.json` (local, Git-ignored); they are descriptive because the targeted expansion is topic-enriched. OpenAlex `locations` may contain repositories and published versions. We count one paper, not one paper per hosting location. A generic proceedings series is not automatically one annual conference.

**Answer:** substantial journal metadata already exist without further work crawling, but conference-series evidence is sparse. No current-venue suitability or acceptance inference follows from historical appearance.
"""
    _write(report_dir / "VENUE_DATA_INVENTORY.md", inventory)

    collection = f"""# Multi-Source Collection Report

Pilot design: 500 distinct DOI values selected deterministically across year × local venue-presence strata (seed 20261104). This intentionally enriches missing cases and is **not population-representative**. Responses are stored byte-for-byte under `{inventory_dir}` with per-response SHA-256 and checkpoint manifests. No original raw file was modified.

| Provider/action | HTTP attempts | Valid 200 | 404 | Bytes |
|---|---:|---:|---:|---:|
| Crossref selected DOI details | {cross['http_attempts']} | {cross['successful']} | {cross['not_found']} | {cross['response_bytes']:,} |
| OpenAlex unique Source details | {sources['http_attempts']} | {sources['successful']} | {sources['not_found']} | {sources['response_bytes']:,} |
| OpenAlex retracted-work sample | 1 | {retract['returned_records']} works | 0 | {retract['raw_bytes']:,} |
| Crossref retraction DOI details | {retract_cross['http_attempts']} | {retract_cross['successful']} | {retract_cross['not_found']} | {retract_cross['response_bytes']:,} |

The selected-DOI Crossref manifest is **incomplete by quality status** despite all 500 requests being stored: one HTTP 200 response carried a DOI different from the requested DOI and was quarantined, not merged. {cross['not_found']} 404s are expected registry misses, not claims that the DOI is invalid. Crossref DOI registration is not universal. The other two provider manifests are complete.

Observed Crossref request rate: {cross['http_attempts']/cross['elapsed_seconds_this_invocation']:.2f} HTTP/s over {cross['elapsed_seconds_this_invocation']:.1f} seconds. The response advertised a public-single rate limit of 5/s and concurrency 1; requests were sequential with 0.3-second minimum spacing. OpenAlex rate-limit preflight reported 10,000 daily credits remaining; 30 source singleton lookups were 0 credits in observed headers, and the retraction list request cost 1 credit. A separate preflight rate-limit request and one Crossref HEAD probe were made; these are not counted in the table above. No DBLP calls were made because the development set has no resolved conference target and a broad conference lookup would not establish reliable evaluation.

Official API references: [OpenAlex authentication/rate limits](https://help.openalex.org/api/authentication/), [OpenAlex pricing](https://help.openalex.org/access/pricing/), [Crossref REST API](https://www.crossref.org/documentation/retrieve-metadata/rest-api/).
"""
    _write(report_dir / "MULTI_SOURCE_COLLECTION_REPORT.md", collection)

    retraction = f"""# Retraction Metadata Quality Audit

Separate seeded OpenAlex convenience sample: **{len(retframe)} explicitly retracted works**, 2020–2024, primary subfields 1702|1707, article|review|preprint. Exact query: `{retract['query']['filter']}`; `sample={retract['query']['sample']}`, `seed={retract['query']['seed']}`. This does not change the approved non-retracted analytical corpus and is not a prevalence estimate.

All {len(retframe)} sampled works had DOI values and Crossref metadata were retrieved for {retract_cross['successful']} of them. Explicit Crossref `update-to` retraction evidence was parsed for **{int(retframe.crossref_retraction_evidence.eq(True).sum())}** records. For the other **{int(retframe.status_unknown.sum())}**, the correct status is **unknown from this Crossref field**, not 'Crossref says not retracted'. Corrections, expressions of concern and withdrawals are not counted as retractions by substring-independent status logic; provider data are retained separately. No independent retraction reference standard or human adjudication was performed; agreement/accuracy cannot be estimated from these data. Notice DOI linkage and status conflicts require manual follow-up.

Raw evidence: `{inventory_dir / 'retractions'}`. OpenAlex sample SHA-256: `{retract['raw_sha256']}`. Crossref per-DOI hashes: `crossref_request_manifest.json`. Original research data remain unchanged.
"""
    _write(report_dir / "RETRACTION_QUALITY_AUDIT.md", retraction)

    before, after = integration["before"], integration["after"]
    rq7 = f"""# RQ7 — Multi-Source Metadata Integration

**Question:** Does adding Crossref and bounded OpenAlex Source detail to locally saved OpenAlex works improve venue metadata completeness and identity resolution? The paired cohort is **{integration['selected_cohort']} paper records carrying 500 selected distinct DOI values**; two selected DOIs occur on two source records. Selection deliberately balances publication year and local venue missingness, so its yield is not a population rate.

| Metric, same {integration['selected_cohort']}-record cohort | Local OpenAlex | Enriched | Change |
|---|---:|---:|---:|
"""
    for key, label in (("resolved_identifier", "Stable venue ID"),
                       ("rankable_journal_or_conference", "Journal/conference ID"),
                       ("missing_name", "Missing venue name"),
                       ("missing_publisher_both_providers", "Missing publisher"),
                       ("missing_issn", "Missing ISSN"),
                       ("ambiguous_or_conflict", "Ambiguous/conflicting identity")):
        rq7 += f"| {label} | {before[key]} | {after[key]} | {after[key]-before[key]:+d} |\n"
    rq7 += f"""

Crossref yielded {integration['crossref_successful_distinct_dois']} parseable DOI matches; {sources['successful']} unique OpenAlex Source records were fetched once each. Among selected paper records, OpenAlex Source API detail filled {integration['source_api_publisher_recovered']} previously missing local publisher fields, while Crossref supplied publisher values for {integration['crossref_publisher_available_where_local_missing']} records missing the local value; these sets may overlap, so do not add them. Provider comparison flagged {integration['publication_year_conflicts']} publication-year differences; these may reflect online/print date conventions, not necessarily incorrect metadata. ISSN conflicts: {integration['issn_conflicts']}; source-type conflicts: {integration['type_conflicts']}. The audit retains original and provider-specific values. {integration['duplicate_work_id_records_resolved']} repeated Work-ID records across origins were deterministically reduced to one paper link while retaining source-record decisions.

The identity gain was **only {after['resolved_identifier']-before['resolved_identifier']} record**. Missing publisher decreased by {before['missing_publisher_both_providers']-after['missing_publisher_both_providers']} records, a meaningful descriptive completeness gain for this intentionally selected cohort. More metadata and provider agreement do **not** prove correctness: no independent publisher/venue human adjudication was completed. Crossref does not independently validate OpenAlex when OpenAlex already ingested similar provider metadata.

Canonical model: `canonical_venues.parquet` has {integration['canonical_venues']:,} stable source/ISSN-backed identities. `paper_venue_links.parquet` has {integration['all_historical_links']:,} unique Work IDs. `venue_conflict_audit.parquet` preserves every source-record/provider decision. Repositories never enter the rankable journal/conference pool. Names are aliases, not sole identity keys.

**Decision: CONDITIONAL GO for metadata enrichment**, chiefly publisher completeness and provenance; **NO-GO for broad DOI-by-DOI Crossref harvesting as a venue-identity rescue strategy** on current evidence.

{figures}
"""
    _write(report_dir / "RQ7_MULTI_SOURCE_DATA_INTEGRATION.md", rq7)

    table = "| Method | Recall@1 | Recall@3 | Recall@5 | Recall@10 | MRR@10 |\n|---|---:|---:|---:|---:|---:|\n"
    for name, m in retrieval["results"].items():
        table += f"| {name} | {m['recall_at_1']:.3f} | {m['recall_at_3']:.3f} | {m['recall_at_5']:.3f} | {m['recall_at_10']:.3f} | {m['mrr_at_10']:.3f} |\n"
    ci = breakdown["paired_bootstrap_v3_minus_v0_recall5"]
    subgroup = "| Historical support of observed venue | 2024 queries | Candidate coverage | V3 Recall@5 |\n|---|---:|---:|---:|\n"
    for bucket in ("0", "1", "2", "3-4", "5-9", "10+"):
        part = breakdown["groups"]["support_bucket"].get(bucket)
        if part:
            subgroup += f"| {bucket} | {part['queries']} | {part['candidate_coverage']:.1%} | {part['v3_venue_profiles_recall5']:.1%} |\n"
    rq8 = f"""# RQ8 — Historical Publication-Venue Discovery Feasibility

Input is a manuscript title and abstract. Output is a **historically evidenced venue shortlist for investigation**, not acceptance prediction, quality ranking or a currently-open call. Temporal index: 2020–2023; evaluation: 2024 development (not an independent final test). Sealed 2025 labels/records were not used. Version groups are disjoint.

The verified integrated dataset contains {retrieval['training_works']:,} eligible historical training papers and {retrieval['development_queries']:,} 2024 development queries. With minimum two historical papers per rankable venue, the common pool contains {retrieval['indexed_works']:,} papers, {retrieval['candidate_venues']} venues ({retrieval['candidate_journals']} journals, **{retrieval['candidate_conferences']} conference**). Only {round(retrieval['oracle_candidate_coverage']*retrieval['development_queries'])} of {retrieval['development_queries']} historical query venues appear in this pool: oracle candidate ceiling **{retrieval['oracle_candidate_coverage']:.1%}**. The 2024 development set contains no resolved conference target, so conference ranking is **not evaluated**.

All methods share this identical candidate universe and all 1,843 queries remain in the end-to-end denominator, including missing/unsupported historical venue labels. V1 uses the **frozen title+abstract classifier** only when its threshold is met ({retrieval['route']['routed_queries']} queries), otherwise falls back to historical popularity; the query's true OpenAlex topic is never used for ranking. V2 fits TF-IDF only on historical text and aggregates the 100 nearest papers; V3 compares query text with historical venue profiles.

{table}

V3 improves Recall@5 over popularity by {ci['estimate']:.3f} absolute ({ci['ci_95_percentile'][0]:.3f}–{ci['ci_95_percentile'][1]:.3f} paired-bootstrap 95% development interval, seed {ci['seed']}). However, **{retrieval['results']['v3_venue_profiles']['recall_at_5']:.1%}** end-to-end Recall@5 is low; conditional Recall@5 among the {round(retrieval['oracle_candidate_coverage']*retrieval['development_queries'])} represented historical venues is **{retrieval['results']['v3_venue_profiles']['conditional_recall_at_5']:.1%}**. Historical venue is only one observed publication outcome; another venue could also be reasonable.

Candidate ceiling by minimum historical support (same 2024 denominator, diagnostic only): threshold 1 = 826/1843 (44.8%); 2 = 653/1843 (35.4%); 3 = 551/1843 (29.9%); 5 = 451/1843 (24.5%); 10 = 332/1843 (18.0%). At threshold 1, most extra venues are singletons, weakening evidence per suggestion. More data might help candidate coverage, but may not fix venue ambiguity or ranking.

## Failure and support analysis

{subgroup}

The observed venue is missing or outside the candidate pool for {retrieval['development_queries']-round(retrieval['oracle_candidate_coverage']*retrieval['development_queries'])} of {retrieval['development_queries']} queries. Among 2024 development papers, {breakdown['groups']['actual_venue_type']['unknown']['queries']} have no resolved journal/conference target; the other {breakdown['groups']['actual_venue_type']['journal']['queries']} resolve to journals. **There is no resolved conference target**, so this pilot cannot justify conference recommendations. Popularity favors large historical journals; thin-tail venues are poorly represented. Provider naming, publication-year differences, evolving venue scope and OpenAlex source taxonomy remain unresolved. Group-specific topic counts are recorded in the local `retrieval_breakdown.json`, not interpreted as population prevalence.

The local `venue_retrieval_index.joblib` powers a **no-network CLI**; it does not imply that venue aims, scope, APCs, deadlines, indexing, or acceptance likelihood are known. Topic routing uses OpenAlex silver labels and must not be presented as validated human truth. Manual topic selection is available. Abstract availability in this eligible subset is 100% by construction; missing-abstract papers remain in the inventory but not the query benchmark. Subgroup metrics and predictions are local, Git-ignored (`retrieval_breakdown.json`, `venue_benchmark_predictions.parquet`).

**Decision: CONDITIONAL GO only for a narrowly scoped journal discovery research prototype with abstention and explicit historical-evidence warnings; NO-GO for a broad journal-and-conference recommender or acceptance predictor.** An independently judged relevance study and more historical journal support are needed before user-facing claims.
"""
    _write(report_dir / "RQ8_VENUE_DISCOVERY_FEASIBILITY.md", rq8)

    # Measured rates; storage and timing projections are deliberately rough.
    original_work_bytes = ORIGINAL_RAW.stat().st_size / 12000
    parquet_bytes = sum(p.stat().st_size for p in Path("data/processed/openalex_stratified/stratified_20261019T155909Z").glob("*.parquet")) / 12000
    cross_seconds = cross["elapsed_seconds_this_invocation"] / cross["http_attempts"]
    original_manifest = _read(ORIGINAL_RAW.parent / "manifest.json")
    phase2_seconds = (datetime.fromisoformat(original_manifest["completed_at_utc"].replace("Z", "+00:00")) -
                      datetime.fromisoformat(original_manifest["created_at_utc"].replace("Z", "+00:00"))).total_seconds()
    observed_doi_fraction = overall["doi"] / overall["records"]
    cost = "| Scenario | OpenAlex work pages (100/page) | Indicative list credits / USD | Raw work GiB | Phase-3 Parquet GiB | OpenAlex retrieval hours* | Crossref DOI requests† | Crossref serial days† |\n|---|---:|---:|---:|---:|---:|---:|---:|\n"
    for label, n in (("Existing local", 0), ("20k new works", 20000), ("50k new works", 50000),
                     ("100k new works", 100000), ("Full historical 937,493-work snapshot", 937493)):
        requests = math.ceil(n / 100)
        dois = round(n * observed_doi_fraction)
        cost += (f"| {label} | {requests:,} | {requests:,} / ${requests*0.0001:.2f} | "
                 f"{n*original_work_bytes/2**30:.2f} | {n*parquet_bytes/2**30:.2f} | "
                 f"{n*phase2_seconds/12000/3600:.2f} | {dois:,} | {dois*cross_seconds/86400:.1f} |\n")
    source_table = pd.read_parquet(inventory_dir / "openalex_sources.parquet")
    source_missing = int((source_table.publisher.isna() | source_table.source_type.eq("unknown")).sum())
    source_seconds = (datetime.fromisoformat(sources["requests"][-1]["retrieved_at_utc"]) -
                      datetime.fromisoformat(sources["requests"][0]["retrieved_at_utc"])).total_seconds()
    costs = f"""# Full-Corpus Collection Cost Estimate — NOT authorization to crawl

Observed local work raw size: {original_work_bytes:,.0f} bytes/work (original 12,000-work run). Eight original Parquet tables: {parquet_bytes:,.0f} bytes/work. Original 12,000-work collection duration: {phase2_seconds:.0f} seconds (timestamp difference, including rate limits and overhead). Crossref pilot: {cross_seconds:.3f} seconds per HTTP request, {cross['response_bytes']/cross['http_attempts']:,.0f} response bytes/request. Historical inventory DOI-bearing fraction: {observed_doi_fraction:.1%}, **not a full-population estimate**.

{cost}

*Retrieval duration is a crude linear scaling of one 12,000-work run. It omits changing quota, retries, cursor behavior, server load, network and preprocessing. †Crossref numbers apply the nonrepresentative observed DOI fraction and sequential pilot rate; no full-coverage requirement is justified. Source metadata: this local inventory has {inv['distinct_source_ids']:,} unique source IDs, of which {source_missing:,} lack a publisher or known type; the 30-singleton pilot spanned {source_seconds:.1f} seconds between its first and last saved responses. A local-only scenario needs **0** new Source requests; exhaustive enrichment of *these already observed missing IDs* would need at most {source_missing:,} singleton requests, before deduplication and failed lookups. For new work cohorts the unique missing-ID count is **not estimable reliably** by linear scaling because venue reuse is heavy-tailed. DBLP requests are zero in this pilot and excluded. Deduplication/integration and checksum throughput were not separately timed, so their large-scale durations are **NOT VERIFIED**; the local 11,539-record full-source inventory plus existing verifiers took 33.815 seconds on this host, not an independent full-corpus benchmark. OpenAlex list pricing is estimated from the observed rate-limit endpoint (1 credit / $0.0001 per list call on 2026-11-04), subject to provider changes; singleton source lookups were observed at 0 credits. Crossref public REST API requires rate-limit courtesy and may return 404 for non-Crossref DOI registrants.

**Recommendation:** do not crawl the full historical population for venue discovery. First consider a targeted, transparent journal-history sample and independently judged shortlist relevance. Crossref identity recovery of one venue ID in 502 selected records does not justify hundreds of thousands of DOI lookups.
"""
    _write(report_dir / "FULL_CORPUS_COLLECTION_COST_ESTIMATE.md", costs)

    main = f"""# Multi-Source Venue Discovery Experiment — Final Decision

## Executive summary

**RQ7: CONDITIONAL GO** for bounded provenance/publisher enrichment, but not broad Crossref harvesting to repair venue identity. **RQ8: CONDITIONAL GO only for an explicitly limited journal-focused *research* prototype; NO-GO for broad journal/conference recommendation.** This experiment does not change RQ1–RQ6, the frozen classifier, website, or the sealed 2025 test.

The historical local data already have {overall['resolved_journal']:,} journal-type source records and only {overall['resolved_conference']} conference-type source records. Crossref recovered only {after['resolved_identifier']-before['resolved_identifier']} additional stable venue identity in the 502-record selected cohort, while reducing missing publisher from {before['missing_publisher_both_providers']} to {after['missing_publisher_both_providers']}. In 2024 development, {retrieval['candidate_venues']} historically supported venues yield an oracle candidate coverage of {retrieval['oracle_candidate_coverage']:.1%}. The best simple baseline (venue TF-IDF profiles) reaches Recall@5 = {retrieval['results']['v3_venue_profiles']['recall_at_5']:.1%}, versus {retrieval['results']['v0_popularity']['recall_at_5']:.1%} popularity, with no conference evaluation target.

## Evidence and decision

1. **Local data:** {overall['records']:,} historical source records, {inv['unique_work_ids']:,} unique IDs, {inv['distinct_source_ids']:,} hosting source IDs. Repositories are not journal/conference labels.
2. **Bounded new collection:** {cross['http_attempts']} Crossref DOI lookups, {sources['http_attempts']} OpenAlex Source singletons, one OpenAlex retraction sample request and {retract_cross['http_attempts']} Crossref retraction DOI lookups. One mismatched Crossref DOI quarantined. No DBLP or full-corpus crawl.
3. **Cleaning:** DOI/ISSN/source IDs normalized; {integration['duplicate_work_id_records_resolved']} repeated Work IDs deterministically resolved for paper links with full row-level audit. {integration['publication_year_conflicts']} provider-year differences retained, not silently overwritten. Canonical IDs use stable identifiers, not names alone.
4. **Retractions:** {int(retframe.crossref_retraction_evidence.eq(True).sum())}/100 have explicit Crossref `update-to` retraction evidence; absence for the rest is unknown status, not a contradiction or accuracy score.
5. **Retrieval:** temporal train 2020–23 ({retrieval['training_works']:,} eligible works), 2024 development ({retrieval['development_queries']:,} queries); common {retrieval['candidate_venues']}-venue pool; no true query venue/topic leakage. The existing frozen classifier routes {retrieval['route']['routed_queries']} queries. Results are development-only, and human venue-suitability validation is NOT VERIFIED.
6. **Scaling:** full-corpus work metadata and especially DOI-by-DOI Crossref enrichment have significant request/storage/time cost for little demonstrated venue-ID gain. See cost report; no broad crawl is authorized.

**Next smallest step:** obtain a bounded independent human relevance assessment of journal shortlists for a predeclared journal-only query set, then decide whether targeted journal-history expansion is worthwhile. Do not modify the final website or treat this pilot as an accepted venue recommender.

## Validation and preservation

`{validation['offline_pytest_command']}`: **{validation['offline_pytest_passed']} passed, {validation['offline_pytest_skipped']} skipped, {validation['offline_pytest_failed']} failed**. `python -m pip check`: {validation['pip_check']}. Read-only source verifiers passed for the original {validation['original_phase2_unique_work_ids']:,}-work Phase 2 collection, the {validation['targeted_expansion_records']:,}-record targeted expansion, integrated Phase 2 tables, {validation['phase4_output_files_verified']} Phase 4 outputs, and {validation['phase3_closed_set_ml_verified_files']} closed-set plus {validation['phase3_open_set_ml_verified_files']} open-set ML output files. The frozen model bundle was loaded with checksum checks. **2025 FINAL TEST: SEALED**, neither opened nor evaluated. Browser tests and the opt-in live sampling test are among the skips; this is an experiment, not a website test.

## Supporting reports

- [Local inventory](experiments/VENUE_DATA_INVENTORY.md)
- [API collection and provenance](experiments/MULTI_SOURCE_COLLECTION_REPORT.md)
- [Retraction audit](experiments/RETRACTION_QUALITY_AUDIT.md)
- [RQ7 integration](experiments/RQ7_MULTI_SOURCE_DATA_INTEGRATION.md)
- [RQ8 retrieval](experiments/RQ8_VENUE_DISCOVERY_FEASIBILITY.md)
- [Cost estimate](experiments/FULL_CORPUS_COLLECTION_COST_ESTIMATE.md)

Original Phase 2/3 evidence remains checksum-verifiable. Record-level experiment files, API bodies, query text and model index stay Git-ignored. A successful code test is not independent correctness validation.
"""
    _write(report_dir.parent / "EXPERIMENT_MULTI_SOURCE_VENUE_FINAL_REPORT.md", main)

    outputs = {str(p.relative_to(inventory_dir)): {"sha256": file_sha256(p), "bytes": p.stat().st_size}
               for p in inventory_dir.rglob("*") if p.is_file() and p.name != "experiment_manifest.json"}
    published_figures = {name: {"sha256": file_sha256(report_dir.parent / "figures" / "venue_experiment" / name),
                                "bytes": (report_dir.parent / "figures" / "venue_experiment" / name).stat().st_size}
                         for name in figure_names}
    code_digest = hashlib.sha256()
    for source in sorted(Path(__file__).parent.glob("*.py")):
        code_digest.update(source.name.encode())
        code_digest.update(source.read_bytes())
    dependencies = {name: importlib.metadata.version(name) for name in
        ("requests", "pandas", "pyarrow", "scikit-learn", "matplotlib", "numpy")}
    run_manifest = {"status": "complete_with_quarantined_crossref_mismatch", "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "run_id": inventory_dir.name, "git_head_at_report_generation": head,
        "experiment_code_sha256": code_digest.hexdigest(), "dependency_versions": dependencies,
        "random_seed": 20261104,
        "scope": "2020-2024 historical venue metadata; 2025 sealed test excluded",
        "input_sha256": {"original_raw": file_sha256(ORIGINAL_RAW), "expansion_raw": file_sha256(EXPANSION_RAW)},
        "output_files": outputs, "published_figures": published_figures,
        "api_attempts": {"crossref_main": cross["http_attempts"],
            "crossref_retraction": retract_cross["http_attempts"],
            "openalex_sources": sources["http_attempts"], "openalex_retraction_list": 1},
        "evaluation_queries": retrieval["development_queries"],
        "warnings": ["One Crossref DOI-identity mismatch quarantined", "No independent human venue correctness review",
                     "2024 reused for development", "No conference evaluation target", "2025 remains sealed"]}
    _write(inventory_dir / "experiment_manifest.json", json.dumps(run_manifest, indent=2))
    handoff = f"""# Independent Review Handoff — Venue Experiment

Branch: `experiment/venue-discovery-data-poc`; base/current report-generation HEAD: `{head}`. The final pushed SHA must be checked in GitHub after delivery. Source manifests and row-level outputs are local only at `{inventory_dir}`; they are intentionally Git-ignored and cannot be reconstructed by cloning alone without restoring the original local Phase 2/3 artifacts.

Input SHA-256: original raw `{run_manifest['input_sha256']['original_raw']}`; expansion raw `{run_manifest['input_sha256']['expansion_raw']}`. Experiment manifest: `{inventory_dir / 'experiment_manifest.json'}`. Canonical venue table: {integration['canonical_venues']:,} rows; one-per-Work paper links: {integration['all_historical_links']:,} rows. Crossref main: {cross['successful']} valid, {cross['not_found']} 404, one DOI mismatch; retraction: {retract_cross['successful']} valid DOI responses. RQ7 paired cohort: {integration['selected_cohort']} source records; venue IDs {before['resolved_identifier']}→{after['resolved_identifier']}. RQ8: {retrieval['development_queries']} 2024 queries, {retrieval['candidate_venues']} candidates, oracle ceiling {retrieval['oracle_candidate_coverage']:.1%}, V3 Recall@5 {retrieval['results']['v3_venue_profiles']['recall_at_5']:.1%}, MRR@10 {retrieval['results']['v3_venue_profiles']['mrr_at_10']:.3f}. Full details are in the six experiment reports and local manifest.

Validation: {validation['offline_pytest_passed']} offline tests passed, {validation['offline_pytest_skipped']} intentionally skipped; `pip check` clean. Original Phase 2, expansion, integrated data, Phase 4 outputs and frozen ML experiments passed their read-only verifiers. The experiment verifier checks input, output, figure and code hashes. No 2025 final-test labels were read.

Reproduction (requires private local artifacts; **do not repeat API collection unless needed**):

```bash
python -m ai_research_trends.experiments.venue_inventory --output-dir data/analysis/venue_discovery_experiment/new_run --doi-limit 500
python -m ai_research_trends.experiments.venue_enrichment crossref --selection data/analysis/venue_discovery_experiment/new_run/crossref_selection.parquet --output-dir data/analysis/venue_discovery_experiment/new_run/crossref --cap 600
python -m ai_research_trends.experiments.venue_retraction --output-dir data/analysis/venue_discovery_experiment/new_run/retractions
python -m ai_research_trends.experiments.venue_verify data/analysis/venue_discovery_experiment/venue_poc_20261104_v1
pytest -q -ra -o addopts=''
python -m pip check
```

The two collection commands above are dry runs without `--execute`. To inspect completed evidence instead, verify all SHA-256 entries in `experiment_manifest.json` and provider checkpoint manifests. Findings are development-only; neither human correctness nor 2025 final-test evaluation was performed. Verdict: RQ7 CONDITIONAL GO; RQ8 journal-only CONDITIONAL GO, general venue recommender NO-GO.
"""
    _write(report_dir.parent / "EXPERIMENT_MULTI_SOURCE_VENUE_REVIEW_HANDOFF.md", handoff)
    return {"reports": 8, "figures": figure_names, "manifest": str(inventory_dir / "experiment_manifest.json"),
            "branch": "experiment/venue-discovery-data-poc", "head_at_generation": head}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory-dir", type=Path, required=True)
    parser.add_argument("--report-dir", type=Path, default=Path("reports/experiments"))
    args = parser.parse_args(argv)
    print(json.dumps(publish(args.inventory_dir, args.report_dir), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
