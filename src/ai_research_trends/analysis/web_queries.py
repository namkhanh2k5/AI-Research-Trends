"""Read-only local query interface; never confuses sample and population scopes."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


class ResearchData:
    def __init__(self, run_dir: Path):
        from ai_research_trends.analysis.web_data import verify
        verify(run_dir)
        self.run_dir=run_dir

    def get_research_overview(self) -> dict:
        return json.loads((self.run_dir/"overview.json").read_text())

    def get_publication_trends(self, series: str="study_population_primary_non_retracted") -> list[dict]:
        frame=pd.read_csv(self.run_dir/"publication_trends.csv")
        if series not in set(frame.series): raise ValueError("Unknown population series")
        return frame.loc[frame.series.eq(series)].to_dict("records")

    def get_topics(self) -> list[dict]:
        return [{"topic_id":p.stem,"official_name":json.loads(p.read_text())["official_name"]}
                for p in sorted((self.run_dir/"topic_briefs").glob("*.json"))]

    def get_topic_brief(self, topic_id: str) -> dict:
        if not topic_id.startswith("T") or not topic_id[1:].isdigit(): raise ValueError("Invalid topic ID")
        path=self.run_dir/"topic_briefs"/f"{topic_id}.json"
        if not path.is_file(): raise KeyError(topic_id)
        return json.loads(path.read_text())

    def search_papers(self, *, keyword: str|None=None, topic_id: str|None=None,
                      year: int|None=None, work_type: str|None=None, oa_status: str|None=None,
                      sort: str="publication_date_desc", page: int=1, page_size: int=20) -> dict:
        if page<1 or page_size<1 or page_size>100: raise ValueError("Invalid pagination")
        frame=pd.read_parquet(self.run_dir/"paper_index.parquet")
        if keyword: frame=frame.loc[frame.title.fillna("").str.contains(keyword,case=False,regex=False)]
        if topic_id:
            full=topic_id if topic_id.startswith("https://openalex.org/") else f"https://openalex.org/{topic_id}"
            frame=frame.loc[frame.topic_ids.fillna("").str.split("|").map(lambda ids:full in ids)]
        if year is not None: frame=frame.loc[frame.publication_year.eq(year)]
        if work_type: frame=frame.loc[frame.work_type.eq(work_type)]
        if oa_status: frame=frame.loc[frame.oa_status.eq(oa_status)]
        if sort=="publication_date_desc": frame=frame.sort_values(["publication_date","work_id"],ascending=[False,True])
        elif sort=="citations_desc": frame=frame.sort_values(["cited_by_count","work_id"],ascending=[False,True])
        else: raise ValueError("Unsupported sort")
        total=len(frame)
        frame=frame.iloc[(page-1)*page_size:page*page_size].copy()
        return {"scope":"original_12000_detailed_sample_not_population","total":total,
                "page":page,"page_size":page_size,"items":frame.where(pd.notna(frame),None).to_dict("records")}

    def get_citation_summary(self) -> list[dict]:
        return pd.read_csv(self.run_dir/"citation_descriptives.csv").to_dict("records")

    def get_oa_summary(self) -> list[dict]:
        return pd.read_csv(self.run_dir/"oa_descriptives.csv").to_dict("records")

    def get_collaboration_summary(self) -> dict:
        return {name:pd.read_csv(self.run_dir/f"{name}.csv").to_dict("records") for name in
                ("collaboration_descriptives","country_collaboration_edges","institution_collaboration_edges")}
