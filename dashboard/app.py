"""Local, read-only OpenAlex research explorer. Run: streamlit run dashboard/app.py"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from ai_research_trends.web.service import (
    artifact_paths, classify, discovery_path, doi_url, draft_fingerprint, load_discovery,
    load_model, load_research, suggestion_message, topic_brief,
)
from ai_research_trends.web.evidence import ROOT, load_published_evidence

st.set_page_config(page_title="AI/CV Research Landscape", page_icon="🔭", layout="wide")
st.markdown("""<style>
.block-container {max-width: 1180px; padding-top: 2rem}
[data-testid="stMetric"] {background:#f1f5f9;border-radius:12px;padding:12px}
.stMarkdown, .stCaption {overflow-wrap:anywhere}
</style>""", unsafe_allow_html=True)


@st.cache_resource(show_spinner="Verifying local research data…")
def research(path: str):
    return load_research(Path(path))


@st.cache_resource(show_spinner="Verifying local model…")
def model(model_path: str, web_path: str):
    return load_model(Path(model_path), Path(web_path))


@st.cache_resource(show_spinner="Verifying local paper-discovery index…")
def paper_discovery(path: str):
    return load_discovery(Path(path))


def caption(scope: str, detail: str = "") -> None:
    st.caption(f"Source: {scope}. {detail}")


def header(title: str, subtitle: str) -> None:
    st.title(title)
    st.write(subtitle)


def published_figure(relative_path: str, description: str) -> None:
    """Display only a tracked, previously published figure; never synthesize results."""
    path = ROOT / relative_path
    if path.is_file():
        st.image(str(path), width="stretch")
        st.caption(description)
    else:
        st.warning(f"Published figure unavailable locally: {path.name}")


def home(data) -> None:
    overview = data.get_research_overview()
    header("Explore AI & Computer Vision Research", "An evidence-based research landscape and assisted topic explorer, 2020–2025.")
    a, b, c = st.columns(3)
    a.metric("Detailed sampled works", f"{overview['detailed_sample_works']:,}")
    b.metric("OpenAlex topics in catalogue", overview["selected_topics"])
    c.metric("Abstracts unavailable", f"{overview['sample_abstract_missing']:,}")
    caption("Verified OpenAlex population aggregates and separate 12,000-work detailed sample", overview["population_scope"])
    st.subheader("What this site can help you do")
    st.write("Explore publication trends, citation and OA context, collaboration, fourteen native topics, and original sampled papers. A trained model can suggest topics for your own title and abstract; it never assigns one automatically.")
    frame = pd.DataFrame(data.get_publication_trends())
    st.plotly_chart(px.line(frame, x="year", y="work_count", markers=True,
                            title="Annual publication counts — complete defined AI/CV corpus"), width="stretch")
    st.info("OpenAlex labels are machine-assigned silver labels. Human semantic validation is pending; the 2025 ML test remains sealed. This corpus is not all global AI research.")


def landscape(data) -> None:
    header("Research Landscape", "Six questions; population aggregates, original-sample analyses and ML diagnostics remain distinct.")
    evidence = load_published_evidence()
    tabs = st.tabs(["RQ1 · Publications", "RQ2 · Citations", "RQ3 · Open Access",
                    "RQ4 · Collaboration", "RQ5 · References", "RQ6 · Topic labels"])
    with tabs[0]:
        frame = pd.DataFrame(data.get_publication_trends())
        st.plotly_chart(px.bar(frame, x="year", y="work_count", title="Complete non-retracted AI/CV primary-subfield population"), width="stretch")
        st.dataframe(frame[["year", "work_count", "yoy_growth_percent"]], hide_index=True)
        caption("Complete OpenAlex aggregation, 2020–2025", "Defined primary subfields 1702/1707, article/review/preprint; not the detailed sample.")
        published_figure("reports/figures/phase4/rq1_native_topic_trends.png",
                         "Overlapping native-topic aggregate series within the defined AI/CV corpus; counts cannot be summed.")
    with tabs[1]:
        frame = pd.DataFrame(data.get_citation_summary())
        yearly = frame[(frame.group_by == "publication_year") & (frame.metric == "cited_by_count")].copy()
        st.plotly_chart(px.bar(yearly, x="group", y="median", title="Median citations by publication year — original detailed sample"), width="stretch")
        st.dataframe(frame[frame.group_by == "all"], hide_index=True)
        caption("Original 12,000-work sample", "Citations depend on publication age and do not measure scientific quality. FWCI is unavailable for all sampled preprints.")
        published_figure("reports/figures/phase4/rq2_fwci_by_subfield.png",
                         "FWCI among observed complete cases in the original sample; all sampled preprints lack FWCI.")
    with tabs[2]:
        frame = pd.DataFrame(data.get_oa_summary())
        st.plotly_chart(px.bar(frame, x="oa_status", y="n", title="Observed OA statuses — original detailed sample"), width="stretch")
        st.dataframe(frame[["oa_status", "n", "median_citations", "fwci_coverage_percent"]], hide_index=True)
        caption("Original 12,000-work sample", "The adjusted Phase 4 analysis finds associations, not causal OA effects; groups differ in year/type composition.")
        published_figure("reports/figures/phase4/rq3_adjusted_coefficients.png",
                         "Phase 4 adjusted six-status OLS on ln(1 + citations), HC3 95% intervals; original sample, not a causal effect.")
        st.write("Gold versus closed: β = +0.463, HC3 95% CI [0.396, 0.531]. Green versus closed: β = +0.178, CI [0.087, 0.269]. The unadjusted binary model instead pools all OA statuses (β = −0.330); these are different contrasts. Green contains many preprints and all sampled preprints lack FWCI.")
    with tabs[3]:
        info = data.get_collaboration_summary()
        frame = pd.DataFrame(info["collaboration_descriptives"])
        st.dataframe(frame[frame.group_by == "all"], hide_index=True)
        pairs = pd.DataFrame(info["country_collaboration_edges"])
        st.dataframe(pairs.head(20), hide_index=True)
        caption("Sampled co-affiliation network", "Country means affiliation geography, not nationality. Missing affiliations must not be interpreted as no collaboration.")
        published_figure("reports/figures/phase4/rq4_country_network.png",
                         "Sampled country co-affiliation links, not a complete global AI collaboration network.")
    with tabs[4]:
        reference = evidence["reference_context"]
        st.subheader("Historical reference context, not a recommender evaluation")
        a, b, c = st.columns(3)
        a.metric("Reference edges in original sample", f"{reference['reference_edges']:,}")
        b.metric("Distinct referenced Work IDs", f"{reference['unique_referenced_work_ids']:,}")
        c.metric("2023 evaluation queries", f"{reference['evaluation_queries']:,}")
        st.write(f"With at least {reference['minimum_historical_citers']} distinct 2020–{reference['historical_cutoff_year']} citing works, the original *eligible-query* pool had {reference['original_pool_candidate_ids']:,} IDs and median 2023 ID overlap {reference['original_pool_median_id_overlap']:.1%}. Allowing all historical edge-bearing works gave {reference['all_historical_pool_candidate_ids']:,} IDs and {reference['all_historical_pool_median_id_overlap']:.1%}. These are different pool definitions, not retrieval accuracy.")
        published_figure("reports/figures/phase5/pool_saturation_2023.png",
                         "Historical 2020–2022 sampled citing-work subsets versus 2023 reference-ID overlap; no extrapolated population claim.")
        st.warning(f"A bounded metadata-subset retrieval diagnostic reached only {reference['bounded_retrieval_end_to_end_recall_at_20']:.2%} mean end-to-end Recall@20. The project therefore rejected citation-aware literature recommendation as its main ML task; this does not measure semantic relevance for uncited papers.")
        caption("Verified Phase 5 historical-pool audit", reference["source"])
    with tabs[5]:
        st.subheader("Reliability limits of fourteen OpenAlex primary-topic silver labels")
        support_path = ROOT / evidence["rq6"]["source"]
        support = pd.read_csv(support_path)
        st.dataframe(support[["short_id", "official_name", "integrated_train_usable",
                              "validation_2024_usable", "missing_abstract_rate"]], hide_index=True)
        published_figure("reports/finalization_p2/figures/rq6_topic_cooccurrence.png",
                         "Top-three OpenAlex topic memberships can overlap in the original sample; overlap is not label error.")
        published_figure("reports/finalization_p2/figures/rq6_score_gaps.png",
                         "OpenAlex top-one/top-two score gaps are model outputs, not calibrated probabilities or quality scores.")
        st.warning("Independent human semantic validation has not been completed. Missing abstracts vary by topic; no website metric establishes the true accuracy of OpenAlex labels.")
        caption("Verified RQ6 aggregate audit, original sample and integrated train", evidence["rq6"]["source"])


def show_brief(brief: dict) -> None:
    st.subheader(brief["official_name"])
    st.caption(f"OpenAlex {brief['topic_id']} · primary subfield {brief['parent_subfield']} · scope {brief['scope_status']}")
    st.write(brief["official_description"])
    a, b = st.columns(2)
    a.metric("Primary-topic sample works", brief["sample_primary_topic_works"])
    b.metric("Any-topic sample works", brief["sample_any_topic_works"])
    st.caption("These are different, overlapping membership definitions in the original 12,000-work sample; neither is a population prevalence estimate.")
    frame = pd.DataFrame({"year": list(brief["population_topic_year_counts"]),
                          "count": list(brief["population_topic_year_counts"].values())})
    st.plotly_chart(px.line(frame, x="year", y="count", markers=True, title="OpenAlex native-topic population aggregates"), width="stretch")
    caption("Native OpenAlex topic aggregate", f"Snapshot {brief['population_topic_snapshot_utc']}; topic overlaps other topics. Not custom text-derived labels.")
    st.subheader("Original-sample context")
    years = pd.DataFrame({"year": list(brief["sample_year_counts"]),
                          "primary_topic_sample_works": list(brief["sample_year_counts"].values())})
    st.dataframe(years, hide_index=True)
    st.metric("Median observed citations · primary-topic sample", brief["sample_citation_median"])
    st.caption("Citation counts depend on publication age and are not a measure of scientific quality.")
    oa = pd.DataFrame({"oa_status": list(brief["sample_oa_counts"]),
                       "primary_topic_sample_works": list(brief["sample_oa_counts"].values())})
    st.plotly_chart(px.bar(oa, x="oa_status", y="primary_topic_sample_works",
                            title="OA status among primary-topic sampled works"), width="stretch")
    st.caption("Descriptive original-sample OA counts; no causal OA inference or population prevalence estimate.")
    st.subheader("Related native topics")
    related = pd.DataFrame(brief["related_native_topics"])
    if not related.empty:
        st.dataframe(related, hide_index=True)
        st.caption("Shared top-three topic memberships in the original sample, not a recommendation or semantic validation.")
    else:
        st.caption("No related-topic relationships are available in this package.")
    st.write("Representative works (recent primary-topic papers from the original sample; not a quality ranking)")
    st.caption(f"Selection rule: {brief['representative_rule']}")
    for paper in brief["representative_papers"]:
        st.write(f"{paper['title']} · {paper['publication_date']} · {paper['cited_by_count']} observed citations")
        st.link_button("Open OpenAlex record", paper["work_id"], key=f"brief_{brief['topic_id']}_{paper['work_id']}")
    for warning in brief["warnings"]:
        st.caption(warning)


def topics(data) -> None:
    header("Topic Explorer", "Browse native OpenAlex topics directly—no model or draft required.")
    items = data.get_topics()
    selected = st.selectbox("Choose a topic", items, format_func=lambda t: f"{t['official_name']} ({t['topic_id']})")
    show_brief(topic_brief(data, selected["topic_id"]))
    with st.expander("Compare two topics"):
        other = st.selectbox("Second topic", [t for t in items if t != selected], format_func=lambda t: t["official_name"])
        first = topic_brief(data, selected["topic_id"])
        second = topic_brief(data, other["topic_id"])
        comparison = pd.DataFrame([
            {"topic": item["official_name"], "primary_topic_sample_works": item["sample_primary_topic_works"],
             "any_topic_sample_works": item["sample_any_topic_works"],
             "sample_median_citations": item["sample_citation_median"]}
            for item in (first, second)
        ])
        st.dataframe(comparison, hide_index=True)
        counts = pd.DataFrame({"year": list(first["population_topic_year_counts"]),
                               first["official_name"]: list(first["population_topic_year_counts"].values()),
                               second["official_name"]: list(second["population_topic_year_counts"].values())})
        st.plotly_chart(px.line(counts, x="year", y=[first["official_name"], second["official_name"]],
                                markers=True, title="OpenAlex native-topic population series"), width="stretch")
        st.caption("Compatible native-topic aggregate definition, but snapshot times may differ and topic memberships overlap. Sample counts and citation medians are descriptive only; no topic quality ranking.")


def classify_page(data, web_path: Path, model_path: Path) -> None:
    header("Classify My Research", "Explore possible topics and similar papers from your research title and abstract.")
    def clear_draft_result() -> None:
        for key in ("suggestion", "suggestion_fingerprint", "confirmed_topic", "manual_topic_choice",
                    "discovery_result", "discovery_fingerprint"):
            st.session_state.pop(key, None)

    title = st.text_input("Research title", max_chars=500, key="draft_title", on_change=clear_draft_result)
    abstract = st.text_area("Abstract", height=220, max_chars=20000, key="draft_abstract",
                            on_change=clear_draft_result)
    fingerprint = draft_fingerprint(title, abstract)
    if st.session_state.get("active_draft_fingerprint") not in (None, fingerprint):
        clear_draft_result()
    st.session_state["active_draft_fingerprint"] = fingerprint
    if st.button("Suggest topics", type="primary"):
        clear_draft_result()
        try:
            service = model(str(model_path), str(web_path))
            st.session_state["suggestion"] = classify(service, title, abstract)
            st.session_state["suggestion_fingerprint"] = fingerprint
        except (ValueError, FileNotFoundError, KeyError, OSError) as exc:
            st.error(f"Suggestion unavailable: {exc}")
    result = (st.session_state.get("suggestion")
              if st.session_state.get("suggestion_fingerprint") == fingerprint else None)
    if result:
        st.info(suggestion_message(result["status"]))
        st.caption(f"Model status: {result['status']} · version {result['model_version']}")
        for prediction in result["predictions"]:
            st.write(f"{prediction['rank']}. {prediction['topic_name']} ({prediction['topic_id']}) · margin {prediction['score']:.3f}")
        st.caption("SVM margins rank model candidates; they are not probabilities. OpenAlex labels are silver labels, and outside-catalogue drafts may still receive a false suggestion.")
    choices = {x["topic_id"]: x["official_name"] for x in data.get_topics()}
    def clear_confirmed_topic() -> None:
        st.session_state.pop("confirmed_topic", None)

    choice = st.selectbox("Choose a topic yourself (optional, independent of model status)",
                          [None, *choices], format_func=lambda x: "No selection" if x is None else choices[x],
                          key="manual_topic_choice", on_change=clear_confirmed_topic)
    if st.button("Confirm my topic choice", disabled=choice is None):
        st.session_state["confirmed_topic"] = choice
    if st.session_state.get("confirmed_topic"):
        st.success("Your choice is confirmed for this session only; no OpenAlex record is changed.")
        try:
            show_brief(topic_brief(data, st.session_state["confirmed_topic"]))
        except KeyError:
            st.error("The selected Topic Brief is unavailable in this verified data package.")
    st.divider()
    st.subheader("Discover papers with similar text")
    st.write("This searches titles and abstracts in the original sampled OpenAlex corpus. It is not a comprehensive literature search, plagiarism check, or novelty detector. A high score does not verify relevance.")
    st.caption("Paper discovery works independently of the classifier, including when it finds no confident topic match. Title-only indexed papers are marked explicitly.")
    left, middle, right = st.columns(3)
    top_k = left.selectbox("Results", [5, 10, 20], index=1)
    years = middle.slider("Publication years", 2020, 2025, (2020, 2025))
    work_type = right.selectbox("Work type", [None, "article", "review", "preprint"],
                                format_func=lambda x: x or "All types")
    topic_filter = st.selectbox("Primary OpenAlex topic filter", [None, *choices],
                                format_func=lambda x: "All topics" if x is None else choices[x])
    include_title_only = st.checkbox("Include title-only papers (scores are less comparable)", value=False)
    search_fingerprint = draft_fingerprint(fingerprint, repr((top_k, years, work_type, topic_filter, include_title_only)))
    if st.button("Find similar papers"):
        st.session_state.pop("discovery_result", None)
        try:
            with st.spinner("Searching the verified local text index…"):
                index = paper_discovery(str(discovery_path()))
                st.session_state["discovery_result"] = index.search(
                    title, abstract, top_k=top_k, year_min=years[0], year_max=years[1],
                    topic_id=topic_filter, work_type=work_type,
                    include_title_only=include_title_only)
                st.session_state["discovery_fingerprint"] = search_fingerprint
        except (FileNotFoundError, ValueError, OSError, KeyError) as exc:
            st.error(f"Paper discovery unavailable: {exc}")
            st.caption("If the index has not been built, run `openalex-paper-discovery build` from the repository root after fetching the original works LFS file.")
    found = (st.session_state.get("discovery_result")
             if st.session_state.get("discovery_fingerprint") == search_fingerprint else None)
    if found:
        st.caption(f"{found['eligible_matches']:,} positive-score matches after filters · search {found['latency_ms']:.1f} ms · original sample only")
        if not found["items"]:
            st.info("No sampled papers match this text and filter combination. Try broader wording or remove a filter.")
        for rank, paper in enumerate(found["items"], 1):
            topic_name = choices.get(paper["primary_topic_id"].rsplit("/", 1)[-1], "Other native OpenAlex topic") if paper.get("primary_topic_id") else "Topic unavailable"
            with st.container(border=True):
                st.markdown(f"**{rank}. {paper['title']}**")
                st.caption(f"{paper['publication_year']} · {paper['work_type']} · {topic_name} · textual cosine similarity {paper['similarity']:.3f} · {paper['text_status'].replace('_', ' ')}")
                st.write(f"Observed citations: {paper['cited_by_count']:,} (descriptive, not a quality score)")
                st.link_button("Open OpenAlex record", paper["work_id"], key=f"discovery_openalex_{rank}")
                if url := doi_url(paper.get("doi")):
                    st.link_button("Open DOI", url, key=f"discovery_doi_{rank}")
    st.caption("For trend charts and manual catalogue browsing, use Research Landscape and Topic Explorer in the sidebar.")


def papers(data) -> None:
    header("Paper Explorer", "Search original sampled works. This is not the complete OpenAlex population.")
    def reset_paper_page() -> None:
        st.session_state["paper_page"] = 1

    a, b, c = st.columns(3)
    keyword = a.text_input("Title keyword", on_change=reset_paper_page)
    year = b.selectbox("Year", [None, *range(2020, 2026)],
                       format_func=lambda x: "All years" if x is None else str(x), on_change=reset_paper_page)
    topic_names = {x["topic_id"]: x["official_name"] for x in data.get_topics()}
    topic_id = c.selectbox("Native topic membership", [None, *topic_names],
                           format_func=lambda x: "All topics" if x is None else topic_names[x],
                           on_change=reset_paper_page)
    d, e, f = st.columns(3)
    work_type = d.selectbox("Work type", [None, "article", "review", "preprint"],
                            format_func=lambda x: x or "All types", on_change=reset_paper_page)
    oa = e.selectbox("OA status", [None, "closed", "bronze", "diamond", "gold", "green", "hybrid"],
                     format_func=lambda x: x or "All statuses", on_change=reset_paper_page)
    sort = f.selectbox("Sort", ["publication_date_desc", "citations_desc"], on_change=reset_paper_page)
    first = data.search_papers(keyword=keyword, topic_id=topic_id, year=year, work_type=work_type,
                               oa_status=oa, sort=sort, page=1, page_size=20)
    max_page = max(1, (first["total"] + 19) // 20)
    if "paper_page" not in st.session_state:
        st.session_state["paper_page"] = 1
    if st.session_state.get("paper_page", 1) > max_page:
        st.session_state["paper_page"] = max_page
    page = st.number_input("Page", min_value=1, max_value=max_page, key="paper_page")
    result = data.search_papers(keyword=keyword, topic_id=topic_id, year=year, work_type=work_type,
                                oa_status=oa, sort=sort, page=int(page), page_size=20)
    st.caption(f"{result['total']:,} matching sampled works · page {result['page']} of {max_page} · 20 per page")
    if not result["items"]:
        st.info("No sampled works match these filters. Try a different keyword or clear a filter.")
    for paper in result["items"]:
        full_title = paper.get("title") or "[Title unavailable]"
        display_title = full_title if len(full_title) <= 150 else f"{full_title[:147]}…"
        with st.expander(f"{display_title} · {paper['publication_year']}"):
            st.write(full_title)
            st.write({key: paper.get(key) for key in ("work_id", "publication_date", "work_type", "language", "cited_by_count", "oa_status", "doi")})
            st.link_button("Open OpenAlex record", paper["work_id"])
            if url := doi_url(paper.get("doi")):
                st.link_button("Open DOI", url)
    caption("Original 12,000-work detailed sample", "Title search is literal and case-insensitive; citation sorting is descriptive, not a quality ranking.")


def methodology(data, model_path: Path) -> None:
    header("Methodology & Model Evaluation", "Research design, evidence boundaries, and honest model limitations.")
    evidence = load_published_evidence()
    comparison = evidence["model_comparison"]
    open_set = evidence["open_set"]
    st.subheader("Collection and preprocessing")
    st.write("The approved population is non-retracted OpenAlex article/review/preprint works dated 2020–2025 with primary subfield 1702 or 1707. Complete OpenAlex aggregates answer publication-count questions. The separate 12,000-work year-stratified detailed sample supports bibliometric descriptions; its nominal weights are not certified inverse inclusion probabilities.")
    st.write("Nested work records were normalized into eight Parquet tables, preserving unique Work IDs, multi-valued topic/affiliation/reference relationships, missing metadata and source checksums. The targeted 2,515-work expansion contributes only to historical ML training, never to population prevalence or the original paper index.")
    st.subheader("Temporal split, features and fitted models")
    st.write("The fourteen-topic supervised task predicts OpenAlex machine-assigned primary-topic silver labels from title and abstract only. Version groups are isolated: 2020–2023 historical train, original-sample 2024 development, 2025 final test sealed. TF-IDF is fit inside historical training folds. Candidate models are ComplementNB, Logistic Regression and Linear SVM; the selected saved model is TF-IDF plus LinearSVC(C=1).")
    st.subheader("Closed-set model comparison · 2024 development")
    st.dataframe(pd.DataFrame(comparison["methods"]), hide_index=True)
    st.caption(f"Same {comparison['validation_in_catalogue']} original-sample 2024 in-catalogue works; macro-F1 and accuracy measure agreement with OpenAlex silver labels, not independent topic truth. Source SHA-256 {comparison['source_sha256']}.")
    published_figure("reports/figures/finalization_p3/model_comparison.png",
                     "Published model comparison on the same 681 in-catalogue 2024 development works.")
    st.subheader("Training expansion ablation and classwise errors")
    original_svm = next(item for item in comparison["methods"] if item["name"] == "Linear SVM · original only")
    expanded_svm = next(item for item in comparison["methods"] if item["name"] == "Linear SVM · expanded")
    st.write(f"The expanded training set has {comparison['training_original_selected']:,} original plus {comparison['training_expansion_selected']:,} targeted selected-topic examples. Original-only SVM macro-F1 was {original_svm['macro_f1']:.4f} versus {expanded_svm['macro_f1']:.4f} with expansion on the same development denominator. A paired 500-resample bootstrap interval for the difference was [{comparison['ablation_bootstrap_macro_f1_difference_95'][0]:.4f}, {comparison['ablation_bootstrap_macro_f1_difference_95'][1]:.4f}]. It does not address silver-label error or future-year generalization.")
    published_figure("reports/figures/finalization_p3/per_class_f1.png",
                     "Per-class F1 against OpenAlex primary-topic labels; class denominators vary.")
    published_figure("reports/figures/finalization_p3/confusion.png",
                     "Confusion matrix on the 2024 in-catalogue development set; disagreements may reflect overlapping labels.")
    st.subheader("Open-set rejection · 2024 development only")
    a, b, c = st.columns(3)
    a.metric("In-catalogue acceptance", f"{open_set['in_catalogue_acceptance']:.1%}")
    b.metric("Outside false acceptance", f"{open_set['outside_false_acceptance']:.1%}")
    c.metric("AUROC", f"{open_set['auroc']:.3f}")
    st.write(f"Threshold calibration used {open_set['calibration_n']} works; a separate version-group evaluation used {open_set['evaluation_n']} works ({open_set['evaluation_in_catalogue']} in-catalogue, {open_set['evaluation_outside_catalogue']} outside). The frozen SVM-margin threshold is {open_set['threshold']:.6f}; margins are not probabilities. Correct accepted placement across all eligible evaluation works was {open_set['end_to_end_correct_placement']:.1%}.")
    published_figure("reports/figures/finalization_p3/open_set_roc.png",
                     "Development open-set ROC; not a 2025 final-test or human-semantic validation result.")
    st.warning(f"The 20% outside false-acceptance calibration target was not met on the 2024 evaluation group (observed {open_set['outside_false_acceptance']:.2%}). Model selection also used 2024 development results; the 2024 open-set check is not fully external. Never place a topic automatically.")
    st.subheader("Governance and research limits")
    try:
        config = json.loads((model_path / "frozen_config.json").read_text())
        st.caption(f"Verified local model: {config.get('model_version')} · {config.get('model_family')} · {config.get('score_method')}")
    except OSError:
        st.warning("Local model bundle unavailable; research explorer remains usable.")
    st.write("Human semantic validation is pending. The 2025 final test remains SEALED. Citation counts are age-dependent, FWCI is missing for every sampled preprint, affiliation coverage is incomplete, and OA comparisons are observational rather than causal. The app is a local research prototype; private artifacts and redistribution rights prevent a public deployment claim.")
    reports = (
        ("Download academic report (PDF)", ROOT / "deliverables/report/FINAL_ACADEMIC_REPORT.pdf", "application/pdf"),
        ("Download Phase 3 ML report (Markdown)", ROOT / "reports/machine_learning/FINALIZATION_P3_FINAL_ML_REPORT.md", "text/markdown"),
    )
    for label, path, mime in reports:
        if path.is_file():
            st.download_button(label, path.read_bytes(), file_name=path.name, mime=mime)
        else:
            st.warning(f"Optional report unavailable locally: {path.name}")


def main() -> None:
    web_path, model_path = artifact_paths()
    try:
        data = research(str(web_path))
    except (OSError, ValueError, KeyError) as exc:
        st.error(f"Verified local web-data package unavailable: {exc}")
        st.stop()
    st.sidebar.title("AI/CV Research")
    page = st.sidebar.radio("Navigate", ["Home", "Research Landscape", "Topic Explorer", "Classify My Research", "Paper Explorer", "Methodology & Model Evaluation"])
    st.sidebar.caption("Local verified artifacts · No OpenAlex API request")
    {"Home": home, "Research Landscape": landscape, "Topic Explorer": topics,
     "Classify My Research": lambda d: classify_page(d, web_path, model_path),
     "Paper Explorer": papers,
     "Methodology & Model Evaluation": lambda d: methodology(d, model_path)}[page](data)


if __name__ == "__main__":
    main()
