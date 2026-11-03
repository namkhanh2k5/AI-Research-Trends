"""Local, read-only OpenAlex research explorer. Run: streamlit run dashboard/app.py"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from ai_research_trends.web.service import artifact_paths, classify, load_model, load_research, topic_brief

st.set_page_config(page_title="AI/CV Research Landscape", page_icon="🔭", layout="wide")
st.markdown("""<style>
.block-container {max-width: 1180px; padding-top: 2rem}
[data-testid="stMetric"] {background:#f1f5f9;border-radius:12px;padding:12px}
</style>""", unsafe_allow_html=True)


@st.cache_resource(show_spinner="Verifying local research data…")
def research(path: str):
    return load_research(Path(path))


@st.cache_resource(show_spinner="Verifying local model…")
def model(model_path: str, web_path: str):
    return load_model(Path(model_path), Path(web_path))


def caption(scope: str, detail: str = "") -> None:
    st.caption(f"Source: {scope}. {detail}")


def header(title: str, subtitle: str) -> None:
    st.title(title)
    st.write(subtitle)


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
    header("Research Landscape", "RQ1–RQ4 use explicitly distinguished population and sample evidence.")
    tabs = st.tabs(["RQ1 · Publications", "RQ2 · Citations", "RQ3 · Open Access", "RQ4 · Collaboration"])
    with tabs[0]:
        frame = pd.DataFrame(data.get_publication_trends())
        st.plotly_chart(px.bar(frame, x="year", y="work_count", title="Complete non-retracted AI/CV primary-subfield population"), width="stretch")
        st.dataframe(frame[["year", "work_count", "yoy_growth_percent"]], hide_index=True)
        caption("Complete OpenAlex aggregation, 2020–2025", "Defined primary subfields 1702/1707, article/review/preprint; not the detailed sample.")
    with tabs[1]:
        frame = pd.DataFrame(data.get_citation_summary())
        yearly = frame[(frame.group_by == "publication_year") & (frame.metric == "cited_by_count")].copy()
        st.plotly_chart(px.bar(yearly, x="group", y="median", title="Median citations by publication year — original detailed sample"), width="stretch")
        st.dataframe(frame[frame.group_by == "all"], hide_index=True)
        caption("Original 12,000-work sample", "Citations depend on publication age and do not measure scientific quality. FWCI is unavailable for all sampled preprints.")
    with tabs[2]:
        frame = pd.DataFrame(data.get_oa_summary())
        st.plotly_chart(px.bar(frame, x="oa_status", y="n", title="Observed OA statuses — original detailed sample"), width="stretch")
        st.dataframe(frame[["oa_status", "n", "median_citations", "fwci_coverage_percent"]], hide_index=True)
        caption("Original 12,000-work sample", "The adjusted Phase 4 analysis finds associations, not causal OA effects; groups differ in year/type composition.")
    with tabs[3]:
        info = data.get_collaboration_summary()
        frame = pd.DataFrame(info["collaboration_descriptives"])
        st.dataframe(frame[frame.group_by == "all"], hide_index=True)
        pairs = pd.DataFrame(info["country_collaboration_edges"])
        st.dataframe(pairs.head(20), hide_index=True)
        caption("Sampled co-affiliation network", "Country means affiliation geography, not nationality. Missing affiliations must not be interpreted as no collaboration.")


def show_brief(brief: dict) -> None:
    st.subheader(brief["official_name"])
    st.caption(f"OpenAlex {brief['topic_id']} · primary subfield {brief['parent_subfield']} · scope {brief['scope_status']}")
    st.write(brief["official_description"])
    a, b = st.columns(2)
    a.metric("Primary-topic sample works", brief["sample_primary_topic_works"])
    b.metric("Any-topic sample works", brief["sample_any_topic_works"])
    frame = pd.DataFrame({"year": list(brief["population_topic_year_counts"]),
                          "count": list(brief["population_topic_year_counts"].values())})
    st.plotly_chart(px.line(frame, x="year", y="count", markers=True, title="OpenAlex native-topic population aggregates"), width="stretch")
    caption("Native OpenAlex topic aggregate", f"Snapshot {brief['population_topic_snapshot_utc']}; topic overlaps other topics. Not custom text-derived labels.")
    st.write("Representative works (recent primary-topic papers from the original sample; not a quality ranking)")
    for paper in brief["representative_papers"]:
        st.write(f"{paper['title']} · {paper['publication_date']}")
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
        second = topic_brief(data, other["topic_id"])
        st.write(f"{selected['official_name']}: {topic_brief(data, selected['topic_id'])['sample_primary_topic_works']} primary-topic sampled works; {other['official_name']}: {second['sample_primary_topic_works']}.")
        st.caption("Descriptive counts use the same original sample. Native topic memberships can overlap.")


def classify_page(data, web_path: Path, model_path: Path) -> None:
    header("Classify My Research", "A tentative topic suggestion, never an automatic or validated assignment.")
    title = st.text_input("Research title", max_chars=500)
    abstract = st.text_area("Abstract", height=220, max_chars=20000)
    if st.button("Suggest topics", type="primary"):
        try:
            service = model(str(model_path), str(web_path))
            st.session_state["suggestion"] = classify(service, title, abstract)
            st.session_state["confirmed_topic"] = None
        except (ValueError, FileNotFoundError, KeyError) as exc:
            st.error(f"Suggestion unavailable: {exc}")
    result = st.session_state.get("suggestion")
    if result:
        st.info(f"Status: {result['status'].replace('_', ' ')} · model {result['model_version']}")
        for prediction in result["predictions"]:
            st.write(f"{prediction['rank']}. {prediction['topic_name']} ({prediction['topic_id']})")
        st.caption("SVM margins are ranking scores, not probabilities. Silver OpenAlex labels; human validation pending. Out-of-catalogue drafts may receive a false in-catalogue suggestion.")
        choices = {x["topic_id"]: x["topic_name"] for x in data.get_topics()}
        choice = st.selectbox("Your own topic choice (you may select any catalogue topic)", [None, *choices], format_func=lambda x: "No selection" if x is None else choices[x])
        if st.button("Confirm my selection", disabled=choice is None):
            st.session_state["confirmed_topic"] = choice
        if st.session_state.get("confirmed_topic"):
            st.success("Your manual selection is confirmed for this session only; no OpenAlex record is changed.")
            show_brief(topic_brief(data, st.session_state["confirmed_topic"]))
    st.divider()
    st.write("Prefer to browse without an ML suggestion? Open the Topic Explorer page.")


def papers(data) -> None:
    header("Paper Explorer", "Search original sampled works. This is not the complete OpenAlex population.")
    a, b, c = st.columns(3)
    keyword = a.text_input("Title keyword")
    year = b.selectbox("Year", [None, *range(2020, 2026)], format_func=lambda x: "All years" if x is None else str(x))
    topic_names = {x["topic_id"]: x["official_name"] for x in data.get_topics()}
    topic_id = c.selectbox("Native topic membership", [None, *topic_names], format_func=lambda x: "All topics" if x is None else topic_names[x])
    d, e, f = st.columns(3)
    work_type = d.selectbox("Work type", [None, "article", "review", "preprint"], format_func=lambda x: x or "All types")
    oa = e.selectbox("OA status", [None, "closed", "bronze", "diamond", "gold", "green", "hybrid"], format_func=lambda x: x or "All statuses")
    sort = f.selectbox("Sort", ["publication_date_desc", "citations_desc"])
    page = st.number_input("Page", min_value=1, value=1)
    result = data.search_papers(keyword=keyword, topic_id=topic_id, year=year, work_type=work_type,
                                oa_status=oa, sort=sort, page=int(page), page_size=20)
    st.caption(f"{result['total']:,} matching sampled works · page {result['page']} · 20 per page")
    for paper in result["items"]:
        with st.expander(f"{paper.get('title') or '[Title unavailable]'} · {paper['publication_year']}"):
            st.write({key: paper.get(key) for key in ("work_id", "publication_date", "work_type", "language", "cited_by_count", "oa_status", "doi")})
            st.link_button("Open OpenAlex record", paper["work_id"])
    caption("Original 12,000-work detailed sample", "Title search is literal and case-insensitive; citation sorting is descriptive, not a quality ranking.")


def methodology(data, model_path: Path) -> None:
    header("Methodology & Model Evaluation", "Research design, evidence boundaries, and honest model limitations.")
    st.write("Population: OpenAlex works published 2020–2025, types article/review/preprint, primary subfield 1702 or 1707, non-retracted. Complete aggregates answer publication-count questions. The separate 12,000-work year-stratified detailed sample supports descriptive impact, OA and collaboration analyses; nominal weights have no guaranteed inclusion-probability interpretation.")
    st.write("The 14-topic model uses OpenAlex machine-assigned primary-topic silver labels. Historical 2020–2023 works train the model; original-sample 2024 is development validation. The 2025 test is sealed. Independent human semantic validation is pending.")
    try:
        config = json.loads((model_path / "frozen_config.json").read_text())
        st.write({key: config.get(key) for key in ("model_version", "model_family", "score_method", "training_source", "validation_source", "human_validation", "final_2025_test")})
    except OSError:
        st.warning("Local model bundle unavailable; research explorer remains usable.")
    st.warning("2024 closed-set and open-set results are development diagnostics, not 2025 final-test estimates. Out-of-catalogue false acceptance remains a material risk; suggestions need user review.")
    st.markdown("See the [full academic report](../reports/FINALIZATION_P4_ACADEMIC_REPORT.md) and [Phase 3 ML report](../reports/FINALIZATION_P3_FINAL_ML_REPORT.md) in the repository.")


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
