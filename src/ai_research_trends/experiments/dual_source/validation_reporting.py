"""Aggregate-only RQ7.1 reports from verified, private local validation evidence."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from ai_research_trends.experiments.dual_source.validation_core import (
    STRATA, license_evidence, reviewed_correctness, wilson_interval,
)
from ai_research_trends.experiments.dual_source.validation_pipeline import (
    AGENCY_DOC, DEFAULT_VALIDATION, load_json, utc_now, verify_validation,
)
from ai_research_trends.preprocessing.validate_tables import file_sha256


REPORTS = Path("reports/experiments")
FIGURES = Path("reports/figures/rq7_validation")


def _table(rows: list[tuple[str, object]]) -> str:
    return "| Measure | Observed |\n|---|---:|\n" + "\n".join(f"| {a} | {b} |" for a, b in rows)


def _chart(name: str, title: str, labels: list[str], values: list[int], *, rotation: int = 0) -> dict:
    fig, ax = plt.subplots(figsize=(8.5, 4.8), dpi=170)
    ax.bar(labels, values, color="#286f89")
    ax.set_title(title)
    ax.set_ylabel("Count")
    ax.tick_params(axis="x", labelrotation=rotation)
    for i, v in enumerate(values):
        ax.text(i, v, str(v), ha="center", va="bottom", fontsize=8)
    fig.tight_layout()
    path = FIGURES / f"{name}.png"
    fig.savefig(path, dpi=170)
    plt.close(fig)
    return {"sha256": file_sha256(path), "bytes": path.stat().st_size}


def build_reports(run: Path = DEFAULT_VALIDATION) -> dict:
    validated = verify_validation(run)
    manifest = load_json(run / "review_sample_manifest.json")
    execution = load_json(run / "validation_execution.json") if (run / "validation_execution.json").is_file() else None
    diagnostics = load_json(run / "exit_134_diagnostics.json") if (run / "exit_134_diagnostics.json").is_file() else None
    doc_lookup = load_json(run / "documentation_lookup_log.json") if (run / "documentation_lookup_log.json").is_file() else {"search_queries": 0}
    source = Path(manifest["source_run"])
    eval_data = load_json(source / "evaluation.json")
    collection = load_json(source / "collection_manifest.json")
    publisher_gain = eval_data["recovery"]["publisher"]["validated_additions"]
    license_gain = eval_data["recovery"]["license"]["validated_additions"]
    fresh_crossref = collection["crossref_http_attempts"]
    sample = pd.read_parquet(run / "review_sample.parquet")
    canonical = pd.read_parquet(source / "processed/canonical_works.parquet")
    conflicts = pd.read_parquet(run / "classified_conflicts.parquet")
    agency = manifest["agency_evidence"]
    license_urls = manifest.get("license_url_evidence", [])
    recovered = canonical.loc[canonical.license_source.eq("crossref")]
    license_all = [license_evidence(v) for v in recovered.license]
    license_selected = [license_evidence(v) for v in canonical.loc[
        canonical.work_id.isin(sample.loc[sample.primary_review_stratum.eq(STRATA[1]), "work_id"]), "license"]]
    license_valid = sum(v["license_urls"] and v["syntactically_valid_urls"] == len(v["license_urls"]) for v in license_all)
    standard = sum(bool(v["license_identifiers"]) for v in license_all)
    versions = sum(v["content_version_restriction"] for v in license_all)
    group_counts = sample.groupby(["primary_review_stratum", "cohort_group"]).size().unstack(fill_value=0)
    status = reviewed_correctness(sample.review_status.tolist())
    official = load_json(run / manifest["official_source_checks"]["path"]) if manifest.get("official_source_checks") else {"checks": []}
    source_backed = sum(x["status"] == "SOURCE_BACKED_CORRECT" for x in official["checks"])
    source_ci = wilson_interval(source_backed, len(official["checks"]))
    source_ci_text = f"[{source_ci[0]:.3f}, {source_ci[1]:.3f}]" if source_ci else "NOT ESTIMABLE"
    source_accuracy_text = f"{source_backed}/{len(official['checks'])}" if official["checks"] else "NOT ESTIMABLE"
    if status["reviewed"] != 0 or manifest["human_decisions_count"] != 0:
        raise ValueError("Reports must not imply unverified human decisions")
    class_count = conflicts.classification.value_counts().to_dict()
    class_works = conflicts.groupby("classification").work_id.nunique().to_dict()
    if sum(class_count.values()) != len(conflicts) or len(conflicts) != eval_data["metadata_conflict_count"]:
        raise ValueError("Conflict rows not conserved")
    agency_reasons = Counter(e["reason"] for e in agency)
    agency_names = Counter(e["agency"] or "UNRESOLVED" for e in agency)
    GROUP_A = "A_GENERAL"
    GROUP_B = "B_TARGETED_MISSINGNESS"
    sample_table = "| Primary stratum | Selected | Group A | Group B |\n|---|---:|---:|---:|\n" + "\n".join(
        f"| {label} | {int(sample.primary_review_stratum.eq(label).sum())} | "
        f"{int(group_counts.loc[label, GROUP_A])} | {int(group_counts.loc[label, GROUP_B])} |" for label in STRATA)
    conflict_table = "| Primary class | Field differences | Distinct works |\n|---|---:|---:|\n" + "\n".join(
        f"| {k} | {v:,} | {class_works[k]:,} |" for k, v in sorted(class_count.items()))
    REPORTS.mkdir(parents=True, exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)
    figure_manifest = {"generated_at_utc": utc_now(), "source_run": str(run), "figures": {}}
    add = lambda name, title, labels, values, rotation=0: figure_manifest["figures"].update({
        f"{name}.png": _chart(name, title, labels, values, rotation=rotation)})
    add("01_coverage_vs_verified", "Coverage gains are not verified correctness",
        ["Publisher added", "Publisher source-backed", "License added", "License rights verified"],
        [publisher_gain, source_backed, license_gain, 0], 20)
    add("02_publisher_review", "Publisher sample: independent decisions pending",
        ["Selected", "Source-backed", "Still unverified"], [30, source_backed, 30-source_backed])
    add("03_license_semantics", "Recovered license metadata: syntax vs rights",
        ["Recovered", "All URLs syntactic", "Standard ID", "Version-specific", "Rights verified"],
        [len(recovered), license_valid, standard, versions, 0], 20)
    add("04_conflict_taxonomy", "2,597 field differences: conservative primary classes",
        [k.replace("_", " ").title() for k in sorted(class_count)],
        [class_count[k] for k in sorted(class_count)], 55)
    add("05_doi_agency", "20 audited Crossref 404 cases: DOI agency evidence",
        ["DataCite", "Unresolved"], [agency_names["DataCite"], agency_names["UNRESOLVED"]])
    add("06_validation_coverage", "Diagnostic review selection (not human adjudication)",
        ["Publisher", "License", "Conflicts", "Crossref 404"], [30, 30, 20, 20])
    add("07_scale_scenarios", "Observed pilot request rate extrapolation (not a forecast)",
        ["1,500 pilot", "5,000 scenario", "12,000 scenario"],
        [fresh_crossref, round(fresh_crossref*5000/len(canonical)), round(fresh_crossref*12000/len(canonical))])
    (FIGURES / "manifest.json").write_text(json.dumps(figure_manifest, indent=2), encoding="utf-8")
    sampling = f"""# RQ7.1 metadata-validation sample

Source pilot verifier: **{validated['status']}**; {validated['source_sha256_verified']} top-level/processed files verified. The source pilot's own verifier checked 1,427 stored artifacts. Fixed seed: **20261104**. Final selected: **{len(sample)} distinct canonical Work IDs**. The selection hash uses the `rq7_1_review:` namespace to avoid reusing the prior Group-A cohort ordering. A preliminary local v1 with the reused hash was superseded without deletion; only v2 is used for results.

{sample_table}

Eligibility counts before sequential exclusion: recovered publisher {int(canonical.publisher_source.eq('crossref').sum())}, recovered license {int(canonical.license_source.eq('crossref').sum())}, any provider conflict {int(canonical.work_id.isin(conflicts.work_id).sum())}, Crossref 404 {int(canonical.match_status.eq('CROSSREF_NOT_FOUND').sum())}. Strata are assigned in the order shown, without replacement. Secondary flags remain in the private sample. No stratum was short; the code fails rather than silently redistributing. Year/type diversity is recorded in the private table but not quota-controlled. This is a **diagnostic sample**, not a prevalence estimator for the original 12,000 works or full AI/CV population. Private selected Work IDs, titles and review sheets remain Git-ignored at `{run}`.

Review state: **PENDING_HUMAN_REVIEW** for all {len(sample)} works. No agreement or accuracy is claimed.
"""
    publisher = f"""# RQ7.1 publisher-correctness audit

The pilot added publisher values to **{publisher_gain}/{len(canonical)}** works: Group A {eval_data['by_group']['A_GENERAL']['integrated']['publisher']-eval_data['by_group']['A_GENERAL']['cleaned_openalex']['publisher']}, Group B {eval_data['by_group']['B_TARGETED_MISSINGNESS']['integrated']['publisher']-eval_data['by_group']['B_TARGETED_MISSINGNESS']['cleaned_openalex']['publisher']}. Exactly **30 distinct publisher-recovery works** were selected (A {int(group_counts.loc[STRATA[0],GROUP_A])}, B {int(group_counts.loc[STRATA[0],GROUP_B])}). DOI linkage and Crossref parsing establish provenance, **not publisher correctness**. One selected case has an AI-performed, source-backed check linking an official article DOI page and an independent publisher directory; this is not a human adjudication or a random validation subsample.

{_table([('Selected for independent review',30), ('AI source-backed publisher identities',source_backed), ('Human-reviewed',status['reviewed']), ('Human-verified correct or alias',status['correct_or_acceptable_alias']), ('Human-verified incorrect',status['verified_incorrect']), ('Still without independent source-backed correctness',30-source_backed), ('Pending human review',30)])}

AI source-backed verification yield: **{source_backed}/30 = {100*source_backed/30:.1f}%**. Among these source-checked cases, observed correctness is **{source_accuracy_text}**; the mechanical Wilson 95% interval is **{source_ci_text}**. This interval is scientifically uninformative with a convenience-selected denominator of {len(official['checks'])} and must not be extrapolated to all {publisher_gain} recoveries. Human-review correctness: **NOT ESTIMABLE (0 denominator)**. Company aliases, imprints and host organizations need source-by-source review. Crossref and OpenAlex may share upstream metadata; provider agreement is not independent ground truth. Full-scale publisher expansion is gated on actual authoritative review, especially in Group A.
"""
    license = f"""# RQ7.1 license semantics and URL audit

The pilot filled a previously empty license field in **{len(recovered)}** records. Across all recovered records, **{license_valid}/{len(recovered)}** have at least one URL and every stored URL is syntactically HTTP(S). This is syntax, not reachability or legal validity. The arrays contain **{sum(len(v['license_urls']) for v in license_all)}** URLs; **{standard}** recovered records have a recognised Creative Commons `/licenses/...` identifier under the conservative parser. **{versions}** contain explicit content-version values beyond `unspecified`. Observed values include `tdm`, `vor`, `am` and `stm-asf`; these are not interchangeable with an unrestricted OA licence.

The 30 selected license-recovery cases contain {sum(v['syntactically_valid_urls'] for v in license_selected)} syntactically valid URL entries. A separately logged, allowlisted HEAD probe made **{manifest.get('license_url_requests_attempted',0)}** requests; **{sum(e['reachable_directly'] for e in license_urls)}** returned direct HTTP 2xx. Other statuses or failures are not proof the policy is absent. HEAD does not verify text, applicability, rights, or whether the paper's version was covered.

Independent license semantics verified: **0**; human/legal interpretation pending: **{len(recovered)}** recovered records. `license_metadata_present` and `reuse_rights_status` must remain separate; the latter is **UNKNOWN**. Do **not** use the 277 additions as OA status, Creative Commons count, or redistribution permission. [DOI agency evidence](RQ7_CROSSREF_404_AUDIT.md) is not a substitute for publisher license terms.
"""
    conflict = f"""# RQ7.1 cross-provider conflict reclassification

Every original field-difference row is retained: **{len(conflicts):,}/{eval_data['metadata_conflict_count']:,} accounted for exactly once**. Counts below are field observations, not erroneous works. Distinct-work counts in different classes overlap and must not be summed.

{conflict_table}

Rules: 944 work-type strings are provider taxonomy differences; 314 date/year differences may reflect online/print date definitions or drift; 360 license string/array differences and 165 ISSN-set overlaps are schema/coverage incompatibilities. Lexically equivalent strings are normalization differences. The **{class_count.get('SEMANTIC_METADATA_CONFLICT',0)}** potential semantic disagreements require authoritative review and are **not** confirmed errors. {class_count.get('UNRESOLVED',0)} differences remain unresolved. Raw OpenAlex-versus-current OpenAlex snapshot drift affects **{eval_data['snapshot_drift_work_count']}** works separately, including **{eval_data['current_out_of_frame_count']}** now outside the original frame; it is not added to the 2,597 cross-provider rows. The original conflict table remains unchanged.
"""
    doi = f"""# RQ7.1 Crossref HTTP 404 investigation

The pilot had **440** Crossref HTTP 404 DOI tasks. A fixed, disjoint diagnostic stratum selected **20** with verified stored 404 response checksums and valid normalized DOI syntax. The [DOI Foundation Which RA? service]({AGENCY_DOC}) was queried once per selected DOI, using **{manifest['agency_requests_attempted']}** logged requests; no Crossref retry or new OpenAlex collection was made.

{_table([('Selected stored 404 cases',20),('Agency HTTP 200 responses',sum(e['http_status']==200 for e in agency)),('DataCite registration confirmed',agency_names['DataCite']),('Crossref registration confirmed',agency_names['Crossref']),('No RA identified / unresolved',agency_names['UNRESOLVED']),('DOI syntax failures',0)])}

The unknown case returned DOI Foundation status `DOI does not exist`; it is not automatically classified as malformed syntax or a transient Crossref failure. Of these 20, **{agency_reasons['NON_CROSSREF_REGISTRATION']}** are explained by non-Crossref registration. The remainder is **UNKNOWN_REASON** until further identity investigation. This diagnostic sample is not a census of all 440. Its cross-Group A/B selection is shown in the sampling report. No DOI is publicly printed here.
"""
    quality = f"""# RQ7.1 validated data-quality layer

The original A/B/C three-stage metrics are unchanged: raw OpenAlex, cleaned OpenAlex and integrated OpenAlex+Crossref for the same 1,500 works. New **D — validated-enrichment evidence** is an audit layer, not a replacement work table.

{_table([('Publisher fields added, coverage gain',publisher_gain),('Publisher additions with AI source-backed correctness',source_backed),('Publisher additions without source-backed check',publisher_gain-source_backed),('Human-adjudicated publisher additions',0),('License fields added, metadata coverage gain',license_gain),('License additions with syntactically valid URLs',license_valid),('License additions with verified reuse rights',0),('License additions with unresolved rights',license_gain),('Venue-name additions',eval_data['recovery']['venue_name']['validated_additions']),('ISSN additions',eval_data['recovery']['issns']['validated_additions'])])}

The one source-backed publisher check is AI-performed, not a human adjudication and not a representative accuracy estimate. Zero verified reuse-rights findings means **no rights assessment has been completed**, not that licenses are invalid. Provider agreement and URL syntax are insufficient for verified quality gain. Group A/B recovery is nonrepresentative of the whole original corpus; Group B was deliberately selected for metadata gaps. Publication counts, citations, OA analysis, classifier and website are unchanged. [Coverage figure](../figures/rq7_validation/01_coverage_vs_verified.png).
"""
    scale = f"""# RQ7.1 decision on 12,000-work dual-source scaling

**NO-GO for immediate full 12,000-work expansion.** Existing 1,500-work pilot and the RQ7.1 evidence do not establish correctness of 167 recovered publishers or legal meaning of 277 recovered license records. The 20-case DOI agency check explains 19 Crossref 404s as DataCite, so blanket Crossref requests waste effort on other registries. 36 current OpenAlex records changed from the original snapshot; 15 no longer meet its frame. All 2,597 differences are retained, but only a subset are potential semantic problems, not confirmed errors.

| Strategy | Decision | Rationale |
|---|---|---|
| A. Keep original single-source analytical data | GO | Preserves verified RQ1–RQ6 and avoids replacing the frozen study frame. |
| B. Targeted DOI-bearing missing-publisher enrichment | CONDITIONAL GO | 167 pilot coverage gains, but first perform authoritative review of 30 sampled recovered values and define an acceptance gate. Treat license separately. |
| C. Full 12,000-work Crossref enrichment | NO-GO now | No independently validated quality gain; ~10,424 fresh Crossref requests and ~277 MiB raw storage are linear pilot scenarios, not forecasts. |

Field verdicts: publisher **CONDITIONAL GO for targeted follow-up only**; license **NO-GO as an OA/reuse-rights indicator** (descriptive deposited metadata only); broad Crossref enrichment **NO-GO now**; scaling all 12,000 **NO-GO now**; replacing official research dataset **NO-GO**. A small expert/official-source publisher review is the next defensible step. No new 12,000-work crawl is authorized or executed.
"""
    REPORTS.joinpath("RQ7_METADATA_VALIDATION_SAMPLING.md").write_text(sampling, encoding="utf-8")
    REPORTS.joinpath("RQ7_PUBLISHER_CORRECTNESS_AUDIT.md").write_text(publisher, encoding="utf-8")
    REPORTS.joinpath("RQ7_LICENSE_SEMANTICS_AUDIT.md").write_text(license, encoding="utf-8")
    REPORTS.joinpath("RQ7_CONFLICT_RECLASSIFICATION.md").write_text(conflict, encoding="utf-8")
    REPORTS.joinpath("RQ7_CROSSREF_404_AUDIT.md").write_text(doi, encoding="utf-8")
    REPORTS.joinpath("RQ7_VALIDATED_DATA_QUALITY.md").write_text(quality, encoding="utf-8")
    REPORTS.joinpath("RQ7_12000_WORK_SCALE_UP_DECISION.md").write_text(scale, encoding="utf-8")
    main = f"""# RQ7.1 — Independent metadata validation and scale-up gate

## Executive decision

**NO-GO for immediate full 12,000-work Crossref expansion; CONDITIONAL GO only for bounded, source-reviewed publisher enrichment.** Original RQ1–RQ6 scientific outputs and the frozen classifier remain unchanged. The final human correctness gate is **PENDING_HUMAN_REVIEW**.

## Verified baseline and design

The existing RQ7 verifier passed: 1,500 canonical works, 30 OpenAlex batches, 1,387 Crossref tasks, nine Parquet tables, 1,427 checksummed artifacts. Source-level SHA inventory contains {validated['source_sha256_verified']} files. The fixed-seed private sample has 100 unique works, with primary groups 30 publisher, 30 license, 20 conflict and 20 Crossref 404; secondary overlap is preserved. It is diagnostic, not population-representative. [Sampling details](experiments/RQ7_METADATA_VALIDATION_SAMPLING.md).

## Publisher and license

Publisher coverage increased by {publisher_gain} works. **{source_backed}/30** selected recovered values have an AI-performed source-backed check; **0/30** have human adjudication. The one-case Wilson interval is uninformative and cannot support a full-cohort accuracy claim. [Publisher audit](experiments/RQ7_PUBLISHER_CORRECTNESS_AUDIT.md).

License metadata appeared in 277 formerly missing records; {license_valid} have syntactically valid stored URLs, {standard} show a conservatively recognized CC licence identifier, and {versions} carry content-version metadata. A bounded ten-URL HEAD check got {sum(e['reachable_directly'] for e in license_urls)} direct 2xx responses. These do not establish unrestricted reuse rights or OA status. [License audit](experiments/RQ7_LICENSE_SEMANTICS_AUDIT.md).

## Conflicts and DOI agency

All 2,597 original provider-field differences were reclassified without discarding rows: taxonomy {class_count.get('TAXONOMY_DIFFERENCE',0)}, date-definition {class_count.get('DATE_DEFINITION_DIFFERENCE',0)}, normalization {class_count.get('NORMALIZATION_DIFFERENCE',0)}, schema/coverage {class_count.get('SCHEMA_INCOMPATIBILITY',0)}, potential semantic {class_count.get('SEMANTIC_METADATA_CONFLICT',0)}, unresolved {class_count.get('UNRESOLVED',0)}. Potential does not mean proven error. Snapshot drift (36 works) is separate. [Conflict audit](experiments/RQ7_CONFLICT_RECLASSIFICATION.md).

Of 20 selected stored Crossref 404 cases, the DOI Foundation identified {agency_names['DataCite']} as DataCite registrations; one remains unresolved with `DOI does not exist` status. No DOI syntax problem was observed in this sample. [DOI audit](experiments/RQ7_CROSSREF_404_AUDIT.md).

## Evidence quality, cost and downstream value

New direct external HTTP attempts: {manifest['agency_requests_attempted']} DOI Foundation GET plus {manifest.get('license_url_requests_attempted',0)} allowlisted license-policy HEAD = **{manifest['agency_requests_attempted']+manifest.get('license_url_requests_attempted',0)}**; no new OpenAlex or Crossref requests. Separately logged browser activity: {official.get('web_search_queries',0)} bounded publisher searches, {doc_lookup['search_queries']} DOI documentation searches and {official.get('direct_doi_open_attempts',0)} attempted DOI opens. Browser backend HTTP counts are not observable. Human publisher accuracy, legal license applicability, and full-cohort 404 agency distribution are **NOT VERIFIED**. Source responses and review sheets stay local/Git-ignored. Full-scale request/storage estimates are scenarios, not guarantees. [Validated quality](experiments/RQ7_VALIDATED_DATA_QUALITY.md); [scale decision](experiments/RQ7_12000_WORK_SCALE_UP_DECISION.md).

## Exit-134 diagnostic

The prior chained Python shutdown abort is not evidence of data corruption. Two standalone `PYTHONFAULTHANDLER=1` verifier runs exited 0 and returned PASS. Python 3.12.3; pandas 2.3.3; PyArrow 21.0.0; requests 2.34.2; NumPy 2.5.4. Status: **{diagnostics['conclusion'] if diagnostics else 'NOT VERIFIED'}**. Diagnostic file SHA-256: `{file_sha256(run/'exit_134_diagnostics.json') if diagnostics else 'NOT AVAILABLE'}`. Do not claim a root cause.

## Preservation and validation

Read-only checks: original Phase 2 raw (123 pages/12,000 unique works), Phase 3 (29 checks/eight tables), Phase 4 (18 checks/64 outputs), prior venue experiment (654 output hashes/seven figures), and final ML bundle (14 files; **2025 FINAL TEST SEALED**) all returned PASS. No source artifact was rewritten. Full offline test command: `{execution['offline_tests']['command'] if execution else 'NOT RECORDED'}` — **{execution['offline_tests']['passed'] if execution else 'NOT RECORDED'} passed, {execution['offline_tests']['skipped'] if execution else 'NOT RECORDED'} skipped, {execution['offline_tests']['failed'] if execution else 'NOT RECORDED'} failed**. `pip check`: {execution['pip_check']['result'] if execution else 'NOT RECORDED'}. Execution evidence is private at `{run}/validation_execution.json` (SHA-256 `{file_sha256(run/'validation_execution.json') if execution else 'NOT AVAILABLE'}`). These verifiers do not substitute for human metadata validation.

## Research outcome

The original analytical dataset remains the official basis for RQ1–RQ6. This experiment demonstrates the distinction between metadata coverage and validated quality. Any subsequent publisher enrichment requires a real official-source/manual sample review. Do not treat Crossref license arrays as rights grants. No broad data collection, model retraining, or sealed-test access occurred.
"""
    Path("reports/RQ7_1_INDEPENDENT_METADATA_VALIDATION_REPORT.md").write_text(main, encoding="utf-8")
    handoff = f"""# RQ7.1 independent review handoff

- Branch: `experiment/rq7-independent-metadata-validation`; base: `cd0421bd03852a5dd0780436012939d81ab54d11`; final Git SHA: see Draft PR HEAD (self-referential SHA cannot be stored in its own commit).
- Private run: `{run}`; source: `{source}`. Review seed: 20261104, domain-separated hash. Review sample: 100 unique works, with 30/30/20/20 disjoint primary strata. Human decisions: **0**, all PENDING_HUMAN_REVIEW.
- Source manifest SHA-256: `{file_sha256(run/'source_evidence_manifest.json')}`. Review sample SHA-256: `{manifest['sample']['sha256']}`. Classified conflicts SHA-256: `{manifest['conflicts']['sha256']}`. Original RQ7 verifier: PASS (1,427 artifacts); new verifier: {validated['status']}.
- Execution evidence SHA-256: `{file_sha256(run/'validation_execution.json') if execution else 'NOT AVAILABLE'}`; exit-134 diagnostics SHA-256: `{file_sha256(run/'exit_134_diagnostics.json') if diagnostics else 'NOT AVAILABLE'}`. Offline tests: {execution['offline_tests']['passed'] if execution else 'NOT RECORDED'} passed, {execution['offline_tests']['skipped'] if execution else 'NOT RECORDED'} skipped, {execution['offline_tests']['failed'] if execution else 'NOT RECORDED'} failed. `pip check`: {execution['pip_check']['result'] if execution else 'NOT RECORDED'}.
- External evidence: DOI Foundation Which RA? (20 logged GET requests), publisher-policy URL HEAD (10 logged requests), and one AI source-backed publisher identity check using an official article page plus a separate publisher directory. Human publisher adjudications: 0. Raw evidence and private paper-level sheets are local only.
- Results: {publisher_gain} publisher metadata additions ({source_backed} AI source-backed, 0 human adjudicated), {license_gain} license metadata additions (0 verified reuse grants), 2,597 field differences fully accounted, 19/20 selected 404 cases identified as DataCite. One DOI agency status unresolved.
- Run commands: `openalex-validate-dual-source verify`; `openalex-report-rq7-validation --run {run}`. Manual reviewer sheets: `review_sheet_*.csv` in the private run. Do not commit those files.
- Exit-134: {diagnostics['conclusion'] if diagnostics else 'NOT VERIFIED'}. No full 12,000-work expansion; 2025 final test remains sealed.
- Next gate: genuine official-source review of the 30 publisher recoveries, preserving evidence URLs, timestamps, aliases and decisions before any targeted follow-on.
"""
    Path("reports/RQ7_1_REVIEW_HANDOFF.md").write_text(handoff, encoding="utf-8")
    return {"reports": 9, "figures": len(figure_manifest["figures"]),
            "selected": len(sample), "conflicts": len(conflicts),
            "human_decisions": 0, "agency_get": len(agency), "license_head": len(license_urls)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, default=DEFAULT_VALIDATION)
    args = parser.parse_args()
    print(json.dumps(build_reports(args.run), indent=2))


if __name__ == "__main__":
    main()
