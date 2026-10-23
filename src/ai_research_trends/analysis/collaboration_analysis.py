"""RQ4: tri-state collaboration and deduplicated co-affiliation networks."""

from __future__ import annotations

from collections import Counter, defaultdict
from itertools import combinations

import pandas as pd


def pair_edges(bridge: pd.DataFrame, entity_col: str, *, complete_work_ids: set[str] | None = None) -> pd.DataFrame:
    """One unordered entity-pair contribution per work; never one per author."""
    required = {"work_id", entity_col}
    if not required.issubset(bridge):
        raise ValueError(f"Missing required pair-bridge columns: {required - set(bridge)}")
    frame = bridge.dropna(subset=[entity_col])
    if complete_work_ids is not None:
        frame = frame.loc[frame["work_id"].isin(complete_work_ids)]
    pairs: Counter[tuple[str, str]] = Counter()
    work_support: dict[tuple[str, str], set[str]] = defaultdict(set)
    for work_id, group in frame.groupby("work_id", sort=False):
        entities = sorted(set(group[entity_col].astype(str)))
        for left, right in combinations(entities, 2):
            if left == right:
                raise ValueError("Self-loop in collaboration pairs")
            if work_id not in work_support[(left, right)]:
                pairs[(left, right)] += 1
                work_support[(left, right)].add(work_id)
    return pd.DataFrame(
        [{"source": left, "target": right, "weight_works": count,
          "supporting_unique_works": len(work_support[(left, right)])}
         for (left, right), count in sorted(pairs.items())],
        columns=["source", "target", "weight_works", "supporting_unique_works"],
    )


def graph_summary(edges: pd.DataFrame, all_nodes: set[str], graph_name: str) -> dict:
    """Compute connectedness without treating sample graph centrality as global impact."""
    nodes = {str(node) for node in all_nodes}
    parent = {node: node for node in nodes}
    degree: Counter[str] = Counter()

    def find(node: str) -> str:
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    for row in edges.itertuples(index=False):
        left, right, weight = str(row.source), str(row.target), int(row.weight_works)
        if left == right or left not in nodes or right not in nodes or weight < 1:
            raise ValueError("Network edge has invalid endpoints, self-loop or weight")
        parent[find(left)] = find(right)
        degree[left] += weight
        degree[right] += weight
    n = len(nodes)
    components = len({find(node) for node in nodes})
    return {"network": graph_name, "nodes": n, "edges": len(edges),
            "connected_components": components,
            "density": 2 * len(edges) / (n * (n - 1)) if n > 1 else 0.0,
            "top_weighted_degree_node": degree.most_common(1)[0][0] if degree else None,
            "top_weighted_degree": degree.most_common(1)[0][1] if degree else 0,
            "scope": "observed sampled-work co-affiliation graph; not global influence"}


def collaboration_tables(
    works: pd.DataFrame, countries: pd.DataFrame, institutions: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    summary = []
    for group_by in ("all", "publication_year", "work_type"):
        groups = [("all", works)] if group_by == "all" else list(works.groupby(group_by, observed=True))
        for label, cohort in groups:
            n = len(cohort)
            known_country = cohort["international_collaboration"].notna()
            known_institution = cohort["institutional_collaboration"].notna()
            summary.append({"group_by": group_by, "group": str(label), "sample_works": n,
                            "mean_authorships": float(cohort["authorship_count"].mean()),
                            "median_authorships": float(cohort["authorship_count"].median()),
                            "mean_unique_institutions": float(cohort["unique_institution_count"].mean()),
                            "median_unique_institutions": float(cohort["unique_institution_count"].median()),
                            "mean_unique_countries": float(cohort["unique_country_count"].mean()),
                            "median_unique_countries": float(cohort["unique_country_count"].median()),
                            "zero_observed_institutions": int(cohort["unique_institution_count"].eq(0).sum()),
                            "single_observed_institution": int(cohort["unique_institution_count"].eq(1).sum()),
                            "multi_observed_institution": int(cohort["unique_institution_count"].ge(2).sum()),
                            "zero_observed_countries": int(cohort["unique_country_count"].eq(0).sum()),
                            "single_observed_country": int(cohort["unique_country_count"].eq(1).sum()),
                            "multi_observed_country": int(cohort["unique_country_count"].ge(2).sum()),
                            "country_affiliation_available": int(cohort["has_country_affiliation"].sum()),
                            "institution_affiliation_available": int(cohort["has_institution_affiliation"].sum()),
                            "international_true": int((cohort["international_collaboration"] == True).sum()),
                            "international_false": int((cohort["international_collaboration"] == False).sum()),
                            "international_unknown": int((~known_country).sum()),
                            "international_known_denominator": int(known_country.sum()),
                            "international_rate_known_percent": 100 * int((cohort["international_collaboration"] == True).sum()) / known_country.sum() if known_country.sum() else float("nan"),
                            "institutional_true": int((cohort["institutional_collaboration"] == True).sum()),
                            "institutional_false": int((cohort["institutional_collaboration"] == False).sum()),
                            "institutional_unknown": int((~known_institution).sum()),
                            "institutional_known_denominator": int(known_institution.sum())})
    if countries.duplicated(["work_id", "country_code"]).any() or institutions.duplicated(["work_id", "institution_id"]).any():
        raise ValueError("Phase 3 affiliation bridges must be unique per work/entity")
    country_edges = pair_edges(countries, "country_code")
    complete_ids = set(works.loc[works["country_affiliation_complete"], "work_id"])
    complete_edges = pair_edges(countries, "country_code", complete_work_ids=complete_ids)
    country_edges = country_edges.rename(columns={"source": "country_a", "target": "country_b"})
    complete_edges = complete_edges.rename(columns={"source": "country_a", "target": "country_b", "weight_works": "complete_coverage_works"})
    country_edges = country_edges.merge(
        complete_edges[["country_a", "country_b", "complete_coverage_works"]],
        on=["country_a", "country_b"], how="left", validate="one_to_one"
    )
    country_edges["complete_coverage_works"] = country_edges["complete_coverage_works"].fillna(0).astype(int)
    institution_edges = pair_edges(institutions, "institution_id").rename(
        columns={"source": "institution_a", "target": "institution_b"}
    )
    institution_meta = institutions.drop_duplicates("institution_id").set_index("institution_id")
    for side in ("a", "b"):
        ids = institution_edges[f"institution_{side}"]
        institution_edges[f"name_{side}"] = ids.map(institution_meta["institution_name"])
        institution_edges[f"country_{side}"] = ids.map(institution_meta["country_code"])
    a, b = institution_edges["country_a"], institution_edges["country_b"]
    institution_edges["pair_geography"] = "unknown"
    known = a.notna() & b.notna()
    institution_edges.loc[known & (a == b), "pair_geography"] = "same_country"
    institution_edges.loc[known & (a != b), "pair_geography"] = "cross_country"
    country_nodes = set(countries["country_code"].dropna().astype(str))
    institution_nodes = set(institutions["institution_id"].dropna().astype(str))
    network = pd.DataFrame([
        graph_summary(country_edges.rename(columns={"country_a": "source", "country_b": "target"}), country_nodes, "country_all_observed"),
        graph_summary(complete_edges.rename(columns={"country_a": "source", "country_b": "target", "complete_coverage_works": "weight_works"}),
                      set(countries.loc[countries["work_id"].isin(complete_ids), "country_code"].astype(str)), "country_complete_affiliation"),
        graph_summary(institution_edges.rename(columns={"institution_a": "source", "institution_b": "target"}), institution_nodes, "institution_all_observed"),
    ])
    return pd.DataFrame(summary), country_edges, institution_edges, network
