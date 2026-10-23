"""Read-only Phase 4 result, denominator, edge and provenance validation."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from ai_research_trends.preprocessing.validate_tables import file_sha256


def validate_analytical_results(t: dict[str, pd.DataFrame], plan: dict) -> dict[str, dict]:
    """Return PASS checks; fail loudly if any research-critical invariant breaks."""
    checks: dict[str, dict] = {}

    def check(name: str, condition: bool, detail: str) -> None:
        checks[name] = {"status": "PASS" if condition else "FAIL", "detail": detail}

    works = t["works"]
    growth = t["publication_trends"]
    native = t["native_topic_trends"]
    emerging = t["emerging_topic_sample_trends"]
    citations = t["citation_descriptives"]
    fwci = t["fwci_descriptives"]
    oa = t["oa_descriptives"]
    models = t["oa_regression_results"]
    diagnostics = t["oa_model_diagnostics"]
    collab = t["collaboration_descriptives"]
    countries = t["country_collaboration_edges"]
    institutions = t["institution_collaboration_edges"]
    check("work_grain", len(works) == plan["allocated_sample_size"] and works.work_id.is_unique,
          "unique detailed-sample Work IDs")
    check("population_exact_total", int(growth.work_count.sum()) == int(plan["population_total"]),
          "complete primary aggregate equals approved sampling-frame total")
    check("population_year_allocation", growth.year.tolist() == list(range(2020, 2026)) and
          all(int(works.publication_year.eq(row.publication_year).sum()) == row.sample_size for row in
              pd.DataFrame(plan["strata"]).itertuples()), "sample years match approved plan")
    expected_abs = growth.work_count.diff()
    observed_abs = growth.absolute_yoy_change.astype(float)
    check("growth_formula", bool(np.allclose(expected_abs.iloc[1:], observed_abs.iloc[1:])) and
          pd.isna(growth.iloc[0].yoy_growth_percent) and
          bool(np.allclose(growth.iloc[1:].yoy_growth_percent,
                           100 * growth.work_count.pct_change(fill_method=None).iloc[1:])),
          "YoY and 2020 missing baseline are exact")
    check("native_topic_scope", len(native) == 30 and
          not native.duplicated(["series", "year"]).any() and
          bool((native.work_count <= native.primary_population_count).all()) and
          bool(native.methodology.str.contains("overlapping").all()),
          "five overlapping native-topic series, not a partition")
    year_sizes = works.groupby("publication_year").size().to_dict()
    check("custom_sample_denominators", all(
        row.sample_year_denominator == year_sizes[row.year] and
        0 <= row.matched_sample_works <= row.sample_year_denominator and
        "sample" in row.scope for row in emerging.itertuples(index=False)),
        "custom text labels use per-year sampled-work denominators")
    all_cite = citations.loc[(citations.group_by == "all") & (citations.metric == "cited_by_count")]
    check("citation_zero_outlier_retained", len(all_cite) == 1 and
          int(all_cite.iloc[0]["n"]) == len(works) and
          int(all_cite.iloc[0]["max"]) == int(works.cited_by_count.max()) and
          math.isclose(all_cite.iloc[0]["zero_percent"], 100 * works.cited_by_count.eq(0).mean()),
          "all observed zeros and citation maximum are retained")
    eligible = works.loc[works.fwci.notna()]
    all_fwci = fwci.loc[fwci.group_by == "all_eligible"]
    check("fwci_complete_cases", len(all_fwci) == 1 and
          int(all_fwci.iloc[0]["n"]) == len(eligible) and
          not eligible.work_type.eq("preprint").any() and
          works.loc[works.work_type.eq("preprint"), "fwci"].isna().all(),
          "FWCI excludes missing preprints rather than zero-imputing")
    check("oa_category_denominator", int(oa.n.sum()) == int(works.has_oa_metadata.sum()) and
          len(oa) == 6 and oa.oa_status.is_unique,
          "six OA categories sum to observed OA metadata denominator")
    binary = t["oa_binary_descriptives"]
    check("oa_binary_denominator", len(binary) == 2 and binary.is_oa.nunique() == 2 and
          int(binary.n.sum()) == int(oa.n.sum()),
          "binary OA is an additional, denominator-consistent view")
    check("model_complete_cases", all(
        int(row.complete_cases) + int(row.excluded_works) == len(works) and
        int(row.rank) == int(row.parameters) and int(row.complete_cases) >= 100
        for row in diagnostics.itertuples(index=False)) and
        all(models.groupby("model").n_complete_cases.nunique() == 1),
        "all model denominators equal actual retained observations")
    check("model_estimates_finite", bool(np.isfinite(models[["estimate_log1p", "se_hc3", "ci95_low", "ci95_high", "p_value"]].to_numpy(dtype=float)).all()) and
          bool((models.se_hc3 > 0).all()) and
          bool((models.ci95_low <= models.estimate_log1p).all()) and
          bool((models.estimate_log1p <= models.ci95_high).all()),
          "all reported conditional estimates and intervals are finite")
    known = works.international_collaboration.notna()
    overall = collab.loc[collab.group_by == "all"]
    check("unknown_collaboration", len(overall) == 1 and
          int(overall.iloc[0].international_unknown) == int((~known).sum()) and
          int(overall.iloc[0].international_known_denominator) == int(known.sum()),
          "unknown affiliation state is not domestic")
    check("observed_affiliation_bins", len(overall) == 1 and
          int(overall.iloc[0].zero_observed_institutions + overall.iloc[0].single_observed_institution + overall.iloc[0].multi_observed_institution) == len(works) and
          int(overall.iloc[0].zero_observed_countries + overall.iloc[0].single_observed_country + overall.iloc[0].multi_observed_country) == len(works),
          "zero/single/multi observed entities partition sampled works without implying known status")
    for name, edge, left, right in (("country", countries, "country_a", "country_b"),
                                    ("institution", institutions, "institution_a", "institution_b")):
        check(f"{name}_pair_integrity", not edge.duplicated([left, right]).any() and
              bool((edge[left] < edge[right]).all()) and
              bool((edge.weight_works > 0).all()) and
              bool((edge.weight_works == edge.supporting_unique_works).all()),
              "one unordered pair contribution per supporting work")
    check("figure_inventory", len(t["figure_inventory"]) == 22 and
          t["figure_inventory"].figure.is_unique, "all prespecified labeled figures")
    audit = t["analytical_subset_audit"]
    check("subset_audit_denominators", not audit.duplicated(["subset", "group_by", "group"]).any() and
          bool((audit.included_works + audit.excluded_works == audit.total_sample_works).all()) and
          bool(audit.loc[audit.group_by == "all", "total_sample_works"].eq(len(works)).all()),
          "every restricted subset records included, excluded and total works")
    failed = [key for key, value in checks.items() if value["status"] != "PASS"]
    if failed:
        raise ValueError(f"Critical Phase 4 validation failed: {failed}")
    return checks


def verify_run(directory: Path, compare_dir: Path | None = None) -> dict:
    """Verify a completed run and optionally compare deterministic result artifacts."""
    manifest = json.loads((directory / "manifest.json").read_text())
    if manifest.get("status") != "complete" or manifest.get("complete") is not True:
        raise ValueError("Phase 4 run is incomplete")
    if not manifest.get("validation") or any(item.get("status") != "PASS" for item in manifest["validation"].values()):
        raise ValueError("Phase 4 run records a failed analytical check")
    for name, item in manifest["inputs"].items():
        if file_sha256(Path(item["path"])) != item["sha256"]:
            raise ValueError(f"Phase 4 source changed: {name}")
    for name, item in manifest["outputs"].items():
        path = directory / item["path"]
        if file_sha256(path) != item["sha256"]:
            raise ValueError(f"Phase 4 output checksum mismatch: {name}")
        if name.endswith(".csv") and len(pd.read_csv(path)) != item["rows"]:
            raise ValueError(f"Phase 4 output row count mismatch: {name}")
    if compare_dir is not None:
        comparison = json.loads((compare_dir / "manifest.json").read_text())
        if comparison["inputs"] != manifest["inputs"] or comparison.get("status") != "complete":
            raise ValueError("Comparison run differs in inputs or completeness")
        for name, item in manifest["outputs"].items():
            if comparison["outputs"][name]["sha256"] != item["sha256"] or file_sha256(
                compare_dir / comparison["outputs"][name]["path"]
            ) != item["sha256"]:
                raise ValueError(f"Deterministic analytical output differs: {name}")
    return {"valid": True, "checks_passed": len(manifest["validation"]),
            "output_files": len(manifest["outputs"]),
            "matching_all_outputs_rerun": compare_dir is not None}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only verification of Phase 4 output manifests")
    parser.add_argument("analysis_dir", type=Path)
    parser.add_argument("--compare-dir", type=Path)
    args = parser.parse_args(argv)
    print(json.dumps(verify_run(args.analysis_dir, args.compare_dir), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
