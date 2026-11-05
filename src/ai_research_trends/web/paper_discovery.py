"""Offline, checksum-verified text discovery over the original OpenAlex sample.

This is content similarity, not citation recommendation, novelty detection, or
an estimate of relevance against human judgments. No OpenAlex requests occur.
"""

from __future__ import annotations

import argparse
import json
import re
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.feature_extraction.text import TfidfTransformer, TfidfVectorizer

from ai_research_trends.analysis.web_data import verify as verify_web_data
from ai_research_trends.artifact_paths import application_artifacts
from ai_research_trends.preprocessing.validate_tables import file_sha256

DEFAULT_WORKS = Path("data/processed/openalex_stratified/stratified_20261019T155909Z/works.parquet")
_APPLICATION = application_artifacts()
DEFAULT_WEB = _APPLICATION["web_data"]
DEFAULT_INDEX = _APPLICATION["paper_discovery"]
WORK_ID = re.compile(r"https://openalex\.org/W[1-9][0-9]*\Z")
TOPIC_ID = re.compile(r"(?:https://openalex\.org/)?T[1-9][0-9]*\Z")
REQUIRED = ("work_id", "title", "abstract", "publication_date", "publication_year",
            "work_type", "doi", "primary_topic_id", "cited_by_count")


def clean_text(value: object) -> str:
    """Whitespace-only normalization; original source columns remain unchanged."""
    return " ".join(value.split()) if isinstance(value, str) else ""


def prepare_papers(works: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Select one representative per exact DOI or exact normalized text.

    Title-only papers require five words; short/absent abstracts are not
    hallucinated. Duplicate groups use earliest publication date then Work ID.
    No fuzzy deduplication or inferred version linkage is attempted.
    """
    missing = set(REQUIRED) - set(works.columns)
    if missing:
        raise ValueError(f"Missing source columns: {sorted(missing)}")
    if works.work_id.isna().any() or not works.work_id.map(lambda x: isinstance(x, str) and bool(WORK_ID.fullmatch(x))).all():
        raise ValueError("Noncanonical Work ID in source")
    if works.work_id.duplicated().any():
        raise ValueError("Duplicate Work IDs in source")
    rows = works.loc[:, REQUIRED].copy()
    rows["title"] = rows.title.map(clean_text)
    rows["abstract"] = rows.abstract.map(clean_text)
    rows["text_status"] = np.where(rows.abstract.str.split().str.len().ge(8), "title_and_abstract", "title_only")
    eligible = rows.title.str.split().str.len().ge(5) & rows.title.str.len().ge(20)
    rows = rows.loc[eligible].copy()
    rows.loc[rows.text_status.eq("title_only"), "abstract"] = ""
    rows = rows.sort_values(["publication_date", "work_id"], kind="stable")
    doi = rows.doi.map(lambda x: x.strip().lower() if isinstance(x, str) and x.strip() else "")
    text_key = rows.title.str.casefold() + "\0" + rows.abstract.str.casefold()
    # Exact DOI duplicates and exact text duplicates are resolved independently.
    duplicate_doi = doi.ne("") & doi.duplicated(keep="first")
    rows = rows.loc[~duplicate_doi].copy()
    text_key = text_key.loc[rows.index]
    duplicate_text = text_key.duplicated(keep="first")
    rows = rows.loc[~duplicate_text].copy()
    rows["document"] = rows.title + " " + rows.title + " " + rows.abstract
    rows = rows.sort_values("work_id", kind="stable").reset_index(drop=True)
    stats = {"source_works": int(len(works)), "excluded_insufficient_title": int((~eligible).sum()),
             "excluded_exact_doi_duplicates": int(duplicate_doi.sum()),
             "excluded_exact_text_duplicates": int(duplicate_text.sum()),
             "indexed_works": int(len(rows)),
             "title_only": int(rows.text_status.eq("title_only").sum()),
             "title_and_abstract": int(rows.text_status.eq("title_and_abstract").sum())}
    return rows, stats


def _validate_source(works_path: Path, web_dir: Path) -> dict:
    source_manifest = works_path.parent / "manifest.json"
    manifest = json.loads(source_manifest.read_text(encoding="utf-8"))
    expected = manifest["tables"]["works"]
    actual = file_sha256(works_path)
    if manifest.get("status") != "complete" or expected["sha256"] != actual:
        raise ValueError("Original processed works do not match completed Phase 3 manifest")
    verify_web_data(web_dir)
    return {"source_works_sha256": actual, "source_works_count": expected["rows"],
            "source_manifest_sha256": file_sha256(source_manifest),
            "web_manifest_sha256": file_sha256(web_dir / "manifest.json")}


def _vectorizer_record(vectorizer: TfidfVectorizer) -> dict:
    """Portable, deterministic fitted TF-IDF state, without Python pickle."""
    return {"vocabulary": {term: int(index) for term, index in sorted(vectorizer.vocabulary_.items())},
            "idf": [float(value) for value in vectorizer.idf_],
            "configuration": {"lowercase": True, "stop_words": "english", "ngram_range": [1, 2],
                              "sublinear_tf": True, "dtype": "float32"}}


def _load_vectorizer(path: Path) -> TfidfVectorizer:
    record = json.loads(path.read_text(encoding="utf-8"))
    vocabulary = record["vocabulary"]
    if (record["configuration"] != {"lowercase": True, "stop_words": "english",
                                    "ngram_range": [1, 2], "sublinear_tf": True, "dtype": "float32"}
            or not isinstance(vocabulary, dict)
            or sorted(vocabulary.values()) != list(range(len(vocabulary)))
            or len(record["idf"]) != len(vocabulary)):
        raise ValueError("Invalid fitted vectorizer state")
    vectorizer = TfidfVectorizer(vocabulary=vocabulary, lowercase=True, strip_accents=None,
                                 stop_words="english", ngram_range=(1, 2),
                                 sublinear_tf=True, dtype=np.float32)
    vectorizer.vocabulary_ = vocabulary
    vectorizer.fixed_vocabulary_ = True
    vectorizer._tfidf = TfidfTransformer(sublinear_tf=True)
    vectorizer._tfidf.idf_ = np.asarray(record["idf"], dtype=np.float32)
    if not np.isfinite(vectorizer.idf_).all() or (vectorizer.idf_ <= 0).any():
        raise ValueError("Invalid inverse-document-frequency values")
    return vectorizer


def build_index(works_path: Path, web_dir: Path, output_dir: Path, *, min_df: int = 2) -> dict:
    """Create a new immutable directory; never overwrite an existing index."""
    if output_dir.exists():
        raise FileExistsError(output_dir)
    if min_df < 1:
        raise ValueError("min_df must be positive")
    provenance = _validate_source(works_path, web_dir)
    works = pd.read_parquet(works_path)
    if len(works) != provenance["source_works_count"]:
        raise ValueError("Source row count differs from Phase 3 manifest")
    papers, stats = prepare_papers(works)
    if papers.empty:
        raise ValueError("No eligible paper text")
    vectorizer = TfidfVectorizer(lowercase=True, strip_accents=None, stop_words="english",
                                 ngram_range=(1, 2), min_df=min_df, max_features=50000,
                                 sublinear_tf=True, dtype=np.float32)
    matrix = vectorizer.fit_transform(papers.document).tocsr()
    if matrix.shape[0] != len(papers) or matrix.shape[1] == 0:
        raise ValueError("Invalid TF-IDF matrix")
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".paper_discovery_", dir=output_dir.parent) as temp:
        stage = Path(temp)
        # Keep queryable/display metadata only: indexed paper abstracts are not
        # needed at serving time and should not be duplicated in the package.
        papers.drop(columns=["document", "abstract"]).to_parquet(stage / "papers.parquet", index=False)
        sparse.save_npz(stage / "matrix.npz", matrix, compressed=True)
        (stage / "vectorizer.json").write_text(
            json.dumps(_vectorizer_record(vectorizer), ensure_ascii=False, sort_keys=True,
                       separators=(",", ":")) + "\n", encoding="utf-8")
        files = {path.name: {"sha256": file_sha256(path), "bytes": path.stat().st_size}
                 for path in sorted(stage.iterdir())}
        manifest = {"status": "complete", "version": 1,
                    "created_at_utc": datetime.now(timezone.utc).isoformat(),
                    "scope": "original_12000_work_detailed_sample_only",
                    "source": provenance, "source_paths": {"works": str(works_path), "web": str(web_dir)},
                    "stats": stats, "matrix_shape": list(matrix.shape), "matrix_nnz": int(matrix.nnz),
                    "configuration": {"method": "tfidf_cosine", "min_df": min_df,
                        "ngram_range": [1, 2], "max_features": 50000, "sublinear_tf": True,
                        "title_weight": 2, "abstract_min_words": 8, "title_min_words": 5,
                        "deduplication": "exact DOI, then exact normalized title+abstract"},
                    "files": files}
        (stage / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        stage.rename(output_dir)
    return manifest


def verify_index(directory: Path, *, works_path: Path | None = None, web_dir: Path | None = None) -> dict:
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("status") != "complete" or manifest.get("version") != 1 or manifest.get("scope") != "original_12000_work_detailed_sample_only":
        raise ValueError("Incomplete or unsupported paper-discovery manifest")
    if set(manifest.get("files", {})) != {"papers.parquet", "matrix.npz", "vectorizer.json"}:
        raise ValueError("Missing or unexpected index artifacts")
    for name, record in manifest["files"].items():
        path = directory / name
        if not path.is_file() or path.stat().st_size != record["bytes"] or file_sha256(path) != record["sha256"]:
            raise ValueError(f"Paper-discovery artifact checksum mismatch: {name}")
    if works_path is not None and file_sha256(works_path) != manifest["source"]["source_works_sha256"]:
        raise ValueError("Source works changed")
    if web_dir is not None and file_sha256(web_dir / "manifest.json") != manifest["source"]["web_manifest_sha256"]:
        raise ValueError("Web package changed")
    papers = pd.read_parquet(directory / "papers.parquet")
    matrix = sparse.load_npz(directory / "matrix.npz")
    vectorizer = _load_vectorizer(directory / "vectorizer.json")
    if len(papers) != manifest["stats"]["indexed_works"] or list(matrix.shape) != manifest["matrix_shape"]:
        raise ValueError("Index dimensions disagree with manifest")
    if matrix.shape[1] != len(vectorizer.vocabulary_) or not set(REQUIRED).difference({"abstract"}).issubset(papers.columns) or "text_status" not in papers:
        raise ValueError("Index metadata/vectorizer schema disagree")
    if papers.work_id.duplicated().any() or not papers.work_id.map(lambda x: isinstance(x, str) and bool(WORK_ID.fullmatch(x))).all():
        raise ValueError("Invalid indexed Work IDs")
    if not sparse.isspmatrix_csr(matrix) or matrix.data.size != manifest["matrix_nnz"] or not np.isfinite(matrix.data).all():
        raise ValueError("Invalid sparse matrix")
    return manifest


class PaperDiscovery:
    """Verified local sparse index; one query allocates only O(number of papers)."""

    def __init__(self, directory: Path, *, works_path: Path | None = None, web_dir: Path | None = None):
        self.manifest = verify_index(directory, works_path=works_path, web_dir=web_dir)
        self.vectorizer = _load_vectorizer(directory / "vectorizer.json")
        self.matrix = sparse.load_npz(directory / "matrix.npz")
        self.papers = pd.read_parquet(directory / "papers.parquet")
        if self.matrix.shape[1] != len(self.vectorizer.vocabulary_):
            raise ValueError("Vectorizer vocabulary and matrix disagree")

    def search(self, title: str, abstract: str = "", *, top_k: int = 10,
               year_min: int | None = None, year_max: int | None = None,
               topic_id: str | None = None, work_type: str | None = None,
               exclude_work_id: str | None = None, include_title_only: bool = False) -> dict:
        if not isinstance(top_k, int) or isinstance(top_k, bool) or not 1 <= top_k <= 20:
            raise ValueError("top_k must be 1–20")
        if year_min is not None and (not isinstance(year_min, int) or isinstance(year_min, bool) or year_min < 1900):
            raise ValueError("Invalid minimum year")
        if year_max is not None and (not isinstance(year_max, int) or isinstance(year_max, bool) or year_max < 1900):
            raise ValueError("Invalid maximum year")
        if year_min is not None and year_max is not None and year_min > year_max:
            raise ValueError("Year range is reversed")
        if topic_id is not None and (not isinstance(topic_id, str) or not TOPIC_ID.fullmatch(topic_id)):
            raise ValueError("Invalid OpenAlex topic ID")
        if work_type is not None and work_type not in {"article", "review", "preprint"}:
            raise ValueError("Invalid work type")
        if exclude_work_id is not None and (not isinstance(exclude_work_id, str) or not WORK_ID.fullmatch(exclude_work_id)):
            raise ValueError("Invalid excluded Work ID")
        if not isinstance(include_title_only, bool):
            raise ValueError("include_title_only must be boolean")
        if not isinstance(title, str) or not isinstance(abstract, str):
            raise ValueError("Title and abstract must be text")
        title, abstract = clean_text(title), clean_text(abstract)
        if "\x00" in title + abstract or len(title) > 500 or len(abstract) > 20000:
            raise ValueError("Invalid query text")
        if len(title.split()) < 5 or len(title) < 20:
            raise ValueError("A descriptive title of at least five words is required")
        if abstract and (len(abstract) < 50 or len(abstract.split()) < 8):
            raise ValueError("Abstract must have 50 characters and eight words, or be empty")
        started = time.perf_counter()
        query = self.vectorizer.transform([title + " " + title + " " + abstract])
        if query.nnz == 0:
            return {"scope": self.manifest["scope"], "items": [], "eligible_matches": 0,
                    "latency_ms": (time.perf_counter() - started) * 1000}
        scores = (query @ self.matrix.T).toarray().ravel()
        frame = self.papers
        mask = scores > 0
        if not include_title_only: mask &= frame.text_status.eq("title_and_abstract").to_numpy()
        if year_min is not None: mask &= frame.publication_year.to_numpy() >= year_min
        if year_max is not None: mask &= frame.publication_year.to_numpy() <= year_max
        if topic_id is not None:
            full = topic_id if topic_id.startswith("https://") else f"https://openalex.org/{topic_id}"
            mask &= frame.primary_topic_id.eq(full).to_numpy()
        if work_type is not None: mask &= frame.work_type.eq(work_type).to_numpy()
        if exclude_work_id is not None: mask &= frame.work_id.ne(exclude_work_id).to_numpy()
        indices = np.flatnonzero(mask)
        ranked = sorted(indices, key=lambda idx: (-float(scores[idx]), frame.work_id.iat[idx]))[:top_k]
        items = []
        for idx in ranked:
            record = frame.iloc[idx]
            items.append({"work_id": record.work_id, "title": record.title,
                          "publication_year": int(record.publication_year),
                          "doi": record.doi if isinstance(record.doi, str) else None,
                          "work_type": record.work_type, "primary_topic_id": record.primary_topic_id,
                          "cited_by_count": int(record.cited_by_count),
                          "text_status": record.text_status, "similarity": float(scores[idx])})
        return {"scope": self.manifest["scope"], "items": items,
                "eligible_matches": int(len(indices)),
                "latency_ms": (time.perf_counter() - started) * 1000}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build", help="Build a new immutable index from verified original works")
    build.add_argument("--works", type=Path, default=DEFAULT_WORKS)
    build.add_argument("--web-dir", type=Path, default=DEFAULT_WEB)
    build.add_argument("--output-dir", type=Path, default=DEFAULT_INDEX)
    build.add_argument("--min-df", type=int, default=2)
    verify = sub.add_parser("verify", help="Verify index and optionally source checksums")
    verify.add_argument("--index-dir", type=Path, default=DEFAULT_INDEX)
    verify.add_argument("--works", type=Path)
    verify.add_argument("--web-dir", type=Path)
    search = sub.add_parser("search", help="Search an already built index")
    search.add_argument("--index-dir", type=Path, default=DEFAULT_INDEX)
    search.add_argument("--title", required=True)
    search.add_argument("--abstract", default="")
    search.add_argument("--top-k", type=int, default=10)
    search.add_argument("--topic-id")
    search.add_argument("--year-min", type=int)
    search.add_argument("--year-max", type=int)
    search.add_argument("--work-type")
    search.add_argument("--exclude-work-id")
    search.add_argument("--include-title-only", action="store_true",
                        help="Include title-only records; lexical scores are less comparable")
    args = parser.parse_args(argv)
    if args.command == "build":
        result = build_index(args.works, args.web_dir, args.output_dir, min_df=args.min_df)
    elif args.command == "verify":
        result = verify_index(args.index_dir, works_path=args.works, web_dir=args.web_dir)
    else:
        result = PaperDiscovery(args.index_dir).search(args.title, args.abstract, top_k=args.top_k,
                    topic_id=args.topic_id, year_min=args.year_min, year_max=args.year_max,
                    work_type=args.work_type, exclude_work_id=args.exclude_work_id,
                    include_title_only=args.include_title_only)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
