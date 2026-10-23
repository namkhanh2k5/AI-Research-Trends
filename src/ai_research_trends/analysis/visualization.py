"""Deterministic, source-labeled Phase 4 figures (PNG 300 DPI and SVG)."""

from __future__ import annotations

import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


COLORS = ["#21618C", "#D35400", "#148F77", "#7D3C98", "#A93226", "#7F8C8D"]
OA_ORDER = ["closed", "hybrid", "bronze", "diamond", "green", "gold"]


def _finish(fig, ax, directory: Path, name: str, *, question: str, source: str,
            denominator: str, note: str, inventory: list[dict]) -> None:
    title = ax.get_title()
    ax.set_title("")
    ax.set_title(title, loc="left", fontsize=12, weight="bold", pad=12)
    ax.grid(axis="y", alpha=0.18)
    fig.text(0.02, 0.015, f"Source: {source} | {denominator} | {note}", fontsize=7,
             va="bottom", ha="left", wrap=True)
    fig.subplots_adjust(bottom=0.18, left=0.12, right=0.98, top=0.86)
    for extension, dpi in (("png", 300), ("svg", 150)):
        fig.savefig(directory / f"{name}.{extension}", dpi=dpi, bbox_inches="tight",
                    metadata={"Date": None} if extension == "svg" else {"Software": "AI Research Trends Phase 4"})
    plt.close(fig)
    inventory.append({"figure": name, "research_question": question, "source": source,
                      "denominator": denominator, "interpretation": note,
                      "png": f"{name}.png", "svg": f"{name}.svg"})


def _axis():
    fig, ax = plt.subplots(figsize=(8, 5))
    return fig, ax


def _network(ax, edges: pd.DataFrame, left: str, right: str, *, top_nodes: int = 14,
             min_weight: int = 2) -> int:
    """Display only high-weight edges among top weighted-degree nodes."""
    degree: dict[str, int] = {}
    for row in edges.itertuples(index=False):
        a, b, weight = str(getattr(row, left)), str(getattr(row, right)), int(row.weight_works)
        degree[a] = degree.get(a, 0) + weight
        degree[b] = degree.get(b, 0) + weight
    nodes = sorted(degree, key=lambda node: (-degree[node], node))[:top_nodes]
    positions = {node: (math.cos(2 * math.pi * i / len(nodes)),
                        math.sin(2 * math.pi * i / len(nodes))) for i, node in enumerate(nodes)} if nodes else {}
    visible = edges.loc[
        edges[left].isin(nodes) & edges[right].isin(nodes) & (edges["weight_works"] >= min_weight)
    ].sort_values("weight_works", ascending=False).head(35)
    max_weight = max(1, int(visible["weight_works"].max())) if len(visible) else 1
    for row in visible.itertuples(index=False):
        x1, y1 = positions[str(getattr(row, left))]
        x2, y2 = positions[str(getattr(row, right))]
        ax.plot([x1, x2], [y1, y2], color=COLORS[0],
                linewidth=0.5 + 3 * row.weight_works / max_weight, alpha=0.35, zorder=1)
    for node, (x, y) in positions.items():
        ax.scatter(x, y, s=80 + 15 * math.sqrt(degree[node]), color=COLORS[1], zorder=2)
        ax.text(x, y + 0.07, node.rsplit("/", 1)[-1], fontsize=8, ha="center", va="bottom")
    ax.set_xlim(-1.35, 1.35)
    ax.set_ylim(-1.35, 1.35)
    ax.set_aspect("equal")
    ax.axis("off")
    return len(visible)


def make_figures(t: dict[str, pd.DataFrame], directory: Path) -> pd.DataFrame:
    """Create 22 prespecified figures and an interpretation/provenance inventory."""
    directory.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.family": "DejaVu Sans", "svg.hashsalt": "ai-research-trends-phase4",
                         "axes.spines.top": False,
                         "axes.spines.right": False, "figure.facecolor": "white"})
    inventory: list[dict] = []
    growth, native, emerging = t["publication_trends"], t["native_topic_trends"], t["emerging_topic_sample_trends"]
    works, oa, coeff = t["works"], t["oa_descriptives"], t["oa_regression_results"]
    collab, country, institution = t["collaboration_descriptives"], t["country_collaboration_edges"], t["institution_collaboration_edges"]
    population_note = "AI/CV primary-subfield corpus; non-retracted"
    sample_note = "12,000 sampled works; not population prevalence"

    fig, ax = _axis(); ax.plot(growth.year, growth.work_count, marker="o", color=COLORS[0]); ax.set(title="Annual AI/CV publications", xlabel="Publication year", ylabel="OpenAlex works (count)", xticks=growth.year)
    _finish(fig, ax, directory, "rq1_population_counts", question="RQ1", source="complete OpenAlex aggregates", denominator=population_note, note="Six complete calendar years", inventory=inventory)
    fig, ax = _axis(); bars = growth.dropna(subset=["yoy_growth_percent"]); ax.bar(bars.year.astype(str), bars.yoy_growth_percent, color=COLORS[0]); ax.axhline(0, color="black", lw=0.8); ax.set(title="Year-over-year publication growth", xlabel="Publication year", ylabel="YoY change (%)")
    _finish(fig, ax, directory, "rq1_yoy_growth", question="RQ1", source="complete OpenAlex aggregates", denominator=population_note, note="2020 has no 2019 baseline", inventory=inventory)
    fig, ax = _axis(); ax.plot(growth.year, growth.index_2020_100, marker="o", color=COLORS[0]); ax.axhline(100, ls="--", color="gray"); ax.set(title="Publication count index", xlabel="Publication year", ylabel="Index (2020 = 100)", xticks=growth.year)
    _finish(fig, ax, directory, "rq1_population_index", question="RQ1", source="complete OpenAlex aggregates", denominator=population_note, note="Population count index, not citation impact", inventory=inventory)
    fig, ax = _axis()
    for i, (name, group) in enumerate(native.groupby("series")):
        ax.plot(group.year, group.work_count, marker="o", label=name.replace("_primary_non_retracted", "").replace("_", " "), color=COLORS[i % len(COLORS)])
    ax.legend(fontsize=7, ncol=2); ax.set(title="OpenAlex-native topic trajectories", xlabel="Publication year", ylabel="Works with topic (count)", xticks=growth.year)
    _finish(fig, ax, directory, "rq1_native_topic_trends", question="RQ1", source="complete OpenAlex topic aggregates", denominator="overlapping memberships within primary corpus", note="Selected topics do not partition AI/CV", inventory=inventory)
    fig, ax = _axis()
    for i, (name, group) in enumerate(emerging.groupby("category")):
        ax.plot(group.year, group.matched_sample_works, marker="o", label=name.replace("_", " "), color=COLORS[i])
    ax.legend(fontsize=8); ax.set(title="Emerging-technology text matches", xlabel="Publication year", ylabel="Matched sampled works (count)", xticks=growth.year)
    _finish(fig, ax, directory, "rq1_emerging_sample_trends", question="RQ1", source="12,000-work sample; title/abstract rules", denominator="year-stratum sample n; abstract coverage varies", note="Exploratory matches, not population totals", inventory=inventory)

    fig, ax = _axis(); ax.hist(np.log1p(works.cited_by_count), bins=45, color=COLORS[0]); ax.set(title="Citation distribution (log1p scale)", xlabel="ln(1 + observed citations)", ylabel="Sampled works (count)")
    _finish(fig, ax, directory, "rq2_citation_distribution", question="RQ2", source="Phase 3 detailed sample", denominator=sample_note, note="Zeroes and outliers retained", inventory=inventory)
    fig, ax = _axis(); years = sorted(works.publication_year.unique()); ax.boxplot([np.log1p(works.loc[works.publication_year == year, "cited_by_count"]) for year in years], tick_labels=[str(y) for y in years], showfliers=False); ax.set(title="Citations by publication cohort", xlabel="Publication year", ylabel="ln(1 + citations)")
    _finish(fig, ax, directory, "rq2_citations_by_year", question="RQ2", source="Phase 3 detailed sample", denominator=sample_note, note="Box hides plotted outlier symbols only; data retained", inventory=inventory)
    eligible = works.loc[works.fwci.notna()]
    fig, ax = _axis(); ax.hist(np.log1p(eligible.fwci), bins=45, color=COLORS[2]); ax.set(title="FWCI distribution where observed", xlabel="ln(1 + FWCI)", ylabel="Eligible articles/reviews (count)")
    _finish(fig, ax, directory, "rq2_fwci_distribution", question="RQ2", source="Phase 3 detailed sample", denominator=f"FWCI-observed articles/reviews, n={len(eligible):,}", note="All preprints have missing FWCI", inventory=inventory)
    fig, ax = _axis(); subfields = sorted(eligible.primary_subfield_id.unique()); ax.boxplot([np.log1p(eligible.loc[eligible.primary_subfield_id == sub, "fwci"]) for sub in subfields], tick_labels=[str(v) for v in subfields], showfliers=False); ax.set(title="FWCI by primary subfield", xlabel="Primary subfield ID", ylabel="ln(1 + FWCI)")
    _finish(fig, ax, directory, "rq2_fwci_by_subfield", question="RQ2", source="Phase 3 detailed sample", denominator=f"FWCI-observed articles/reviews, n={len(eligible):,}", note="1702 AI; 1707 CV/Pattern Recognition", inventory=inventory)
    fig, ax = _axis(); ax.hexbin(works.publication_age_years, np.log1p(works.cited_by_count), gridsize=32, mincnt=1, cmap="Blues"); ax.set(title="Citation accumulation and observation age", xlabel="Publication age at common collection snapshot (years)", ylabel="ln(1 + citations)")
    _finish(fig, ax, directory, "rq2_citation_age", question="RQ2", source="Phase 3 detailed sample", denominator=sample_note, note="Association does not remove all cohort confounding", inventory=inventory)
    grouped = works.groupby("work_type").cited_by_count.agg(["mean", "median"])
    fig, ax = _axis(); x = np.arange(len(grouped)); ax.bar(x - .18, grouped["mean"], width=.36, label="Mean", color=COLORS[0]); ax.bar(x + .18, grouped["median"], width=.36, label="Median", color=COLORS[1]); ax.set(xticks=x, xticklabels=grouped.index, title="Citation summaries by work type", xlabel="Work type", ylabel="Observed citations per work"); ax.legend()
    _finish(fig, ax, directory, "rq2_citations_by_type", question="RQ2", source="Phase 3 detailed sample", denominator=sample_note, note="Mean–median gap reflects skewness", inventory=inventory)

    oa = oa.set_index("oa_status").reindex(OA_ORDER).reset_index()
    fig, ax = _axis(); ax.bar(oa.oa_status, oa.n, color=COLORS[0]); ax.set(title="Open Access status distribution", xlabel="OA status", ylabel="Sampled works (count)")
    _finish(fig, ax, directory, "rq3_oa_distribution", question="RQ3", source="Phase 3 detailed sample", denominator=f"OA-observed works, n={int(oa.n.sum()):,}", note="Six statuses remain distinct", inventory=inventory)
    fig, ax = _axis(); ax.boxplot([np.log1p(works.loc[works.oa_status == status, "cited_by_count"]) for status in OA_ORDER], tick_labels=OA_ORDER, showfliers=False); ax.set(title="Citation distributions by OA status", xlabel="OA status", ylabel="ln(1 + citations)")
    _finish(fig, ax, directory, "rq3_citations_by_oa", question="RQ3", source="Phase 3 detailed sample", denominator=f"OA-observed works, n={int(oa.n.sum()):,}", note="Unadjusted observational comparison", inventory=inventory)
    fig, ax = _axis(); ax.bar(oa.oa_status, oa.median_citations, color=COLORS[1]); ax.set(title="Median citations by OA status", xlabel="OA status", ylabel="Median observed citations")
    _finish(fig, ax, directory, "rq3_median_citations_oa", question="RQ3", source="Phase 3 detailed sample", denominator=f"OA-observed works, n={int(oa.n.sum()):,}", note="Unadjusted; cohort/type mix differs", inventory=inventory)
    primary = coeff.loc[(coeff.model == "adjusted_status_year") & coeff.term.str.startswith("oa_")].copy()
    fig, ax = _axis(); x = np.arange(len(primary)); ax.errorbar(primary.estimate_log1p, x, xerr=[primary.estimate_log1p - primary.ci95_low, primary.ci95_high - primary.estimate_log1p], fmt="o", color=COLORS[0], capsize=3); ax.axvline(0, ls="--", color="gray"); ax.set(yticks=x, yticklabels=primary.term.str.replace("oa_", "", regex=False), title="Adjusted OA-status associations (HC3 95% CI)", xlabel="Coefficient on ln(1 + citations); closed reference", ylabel="OA status")
    _finish(fig, ax, directory, "rq3_adjusted_coefficients", question="RQ3", source="Phase 3 sample; prespecified OLS/HC3", denominator=f"Complete cases n={int(primary.n_complete_cases.iloc[0]):,}", note="Adjusted for year, type, subfield; not causal", inventory=inventory)
    fig, ax = _axis(); ax.boxplot([np.log1p(eligible.loc[eligible.oa_status == status, "fwci"]) for status in OA_ORDER], tick_labels=OA_ORDER, showfliers=False); ax.set(title="FWCI by OA status where available", xlabel="OA status", ylabel="ln(1 + FWCI)")
    _finish(fig, ax, directory, "rq3_fwci_by_oa", question="RQ3", source="Phase 3 detailed sample", denominator=f"FWCI-observed articles/reviews, n={len(eligible):,}", note="Descriptive only; preprints excluded", inventory=inventory)

    fig, ax = _axis(); ax.hist(np.minimum(works.authorship_count, 20), bins=np.arange(0, 22), alpha=.7, label="Authorships", color=COLORS[0]); ax.hist(np.minimum(works.unique_institution_count, 20), bins=np.arange(0, 22), alpha=.6, label="Unique institutions", color=COLORS[1]); ax.set(title="Authorship and institution counts per work", xlabel="Count (20 means ≥20)", ylabel="Sampled works"); ax.legend()
    _finish(fig, ax, directory, "rq4_author_institution_counts", question="RQ4", source="Phase 3 detailed sample", denominator=sample_note, note="Display cap only; original counts retained", inventory=inventory)
    overall = collab.loc[(collab.group_by == "all") & (collab.group == "all")].iloc[0]
    fig, ax = _axis(); ax.bar(["International", "Known domestic", "Unknown"], [overall.international_true, overall.international_false, overall.international_unknown], color=[COLORS[2], COLORS[0], COLORS[5]]); ax.set(title="International co-affiliation status", xlabel="Tri-state status", ylabel="Sampled works (count)")
    _finish(fig, ax, directory, "rq4_international_status", question="RQ4", source="Phase 3 detailed sample", denominator=sample_note, note="Unknown is not domestic", inventory=inventory)
    fig, ax = _axis(); shown = _network(ax, country, "country_a", "country_b", min_weight=3); ax.set_title("Country co-affiliation network (filtered)")
    _finish(fig, ax, directory, "rq4_country_network", question="RQ4", source="Phase 3 country bridge", denominator="one country pair per sampled work", note=f"Top 14 nodes; edges ≥3 works; {shown} edges drawn", inventory=inventory)
    top = country.nlargest(12, "weight_works").iloc[::-1]
    fig, ax = _axis(); ax.barh(top.country_a + "–" + top.country_b, top.weight_works, color=COLORS[0]); ax.set(title="Top observed country co-affiliation pairs", xlabel="Supporting sampled works", ylabel="Unordered affiliation-country pair")
    _finish(fig, ax, directory, "rq4_top_country_pairs", question="RQ4", source="Phase 3 country bridge", denominator="one pair contribution per sampled work", note="Sample network, not global country rank", inventory=inventory)
    fig, ax = _axis(); shown = _network(ax, institution, "institution_a", "institution_b", min_weight=2); ax.set_title("Institution co-affiliation network (filtered)")
    _finish(fig, ax, directory, "rq4_institution_network", question="RQ4", source="Phase 3 institution bridge", denominator="one institution pair per sampled work", note=f"Top 14 nodes; edges ≥2 works; {shown} edges drawn", inventory=inventory)
    by_year = collab.loc[collab.group_by == "publication_year"].sort_values("group")
    fig, ax = _axis(); x = np.arange(len(by_year)); ax.bar(x - .18, by_year.country_affiliation_available / by_year.sample_works * 100, width=.36, label="Country", color=COLORS[0]); ax.bar(x + .18, by_year.institution_affiliation_available / by_year.sample_works * 100, width=.36, label="Institution", color=COLORS[1]); ax.set(xticks=x, xticklabels=by_year.group, title="Affiliation metadata coverage by year", xlabel="Publication year", ylabel="Sample works with metadata (%)", ylim=(0, 100)); ax.legend()
    _finish(fig, ax, directory, "rq4_affiliation_coverage", question="RQ4", source="Phase 3 detailed sample", denominator="each year-stratum sample n", note="Missingness may be nonrandom", inventory=inventory)

    if len(inventory) != 22:
        raise ValueError(f"Expected 22 declared figures, created {len(inventory)}")
    return pd.DataFrame(inventory)
