"""Private localhost-only blind reviewer interface; run separately from public app."""

from pathlib import Path
import os

import pandas as pd
import streamlit as st

from ai_research_trends.web.review import load_blind, ratings_path, save_rating

st.set_page_config(page_title="Blind Topic Review", layout="wide")
st.title("Independent blind topic review")
st.warning("Local use only. Do not expose this reviewer interface on a public network or deploy rating files.")
reviewer = os.environ.get("AI_TRENDS_REVIEWER")
if reviewer not in {"reviewer_a", "reviewer_b"}:
    st.error("Set AI_TRENDS_REVIEWER to reviewer_a or reviewer_b before starting this local app.")
    st.stop()
package = Path(os.environ.get("AI_TRENDS_REVIEW_PACKAGE", "data/analysis/finalization_p2_human_review_20261101_v1"))
output = Path(os.environ.get("AI_TRENDS_REVIEW_OUTPUT", "data/analysis/finalization_p4_human_ratings"))
sheet = st.radio("Review batch", ["calibration", "evaluation"], horizontal=True)
try:
    blind = load_blind(package, reviewer, sheet)
except (OSError, ValueError, KeyError) as exc:
    st.error(f"Verified reviewer package unavailable: {exc}")
    st.stop()
path = ratings_path(output, reviewer, sheet)
ratings = pd.read_csv(path, keep_default_na=False) if path.exists() else None
completed = 0 if ratings is None else int(ratings.best_topic.ne("").sum())
st.progress(completed / len(blind), text=f"{completed}/{len(blind)} rated")
example_id = st.selectbox("Blind example", blind.example_id.tolist())
row = blind.loc[blind.example_id.eq(example_id)].iloc[0]
st.subheader(row.title)
st.write(row.abstract)
options = [part.strip() for part in row.randomized_topic_options.split(" | ")]
topic_ids = [part.split(" — ", 1)[0] for part in options]
names = {item.split(" — ", 1)[0]: item for item in options}
names.update({"NONE": "NONE — outside all listed topics", "UNCLEAR": "UNCLEAR — insufficient information"})
current = None if ratings is None else ratings.loc[ratings.example_id.eq(example_id)].iloc[0]
previous = "" if current is None else current.best_topic
choice = st.selectbox("One primary choice", ["", *topic_ids, "NONE", "UNCLEAR"],
                      index=(["", *topic_ids, "NONE", "UNCLEAR"].index(previous) if previous in ["", *topic_ids, "NONE", "UNCLEAR"] else 0),
                      format_func=lambda x: "Select one" if not x else names[x])
second = st.selectbox("Optional plausible alternative", ["", *topic_ids, "NONE", "UNCLEAR"],
                      format_func=lambda x: "None" if not x else names[x])
note = st.text_area("Review note", value="" if current is None else current.reviewer_note)
if st.button("Save this rating", disabled=not choice):
    try:
        save_rating(output, reviewer, sheet, blind, example_id, choice, second, note)
        st.success("Saved locally. Rerun or select the next example.")
    except ValueError as exc:
        st.error(str(exc))
if path.exists():
    st.download_button("Export my rating sheet", path.read_bytes(), file_name=f"{reviewer}_{sheet}_ratings.csv", mime="text/csv")
st.caption("The sheet contains no source labels or model predictions. Export does not imply completed or genuine human validation; run the existing rating validator after all examples are rated.")
