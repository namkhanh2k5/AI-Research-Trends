# AI Research Trends & Scientific Impact

**A Bibliometric and Machine Learning Analysis Using OpenAlex**

This university Introduction to Data Science project studies how AI research
evolved during the six complete calendar years 2020–2025, how citation impact
varies after accounting for time and field, how Open Access is associated with
impact, and how institutions and countries collaborate.

The project prioritizes reproducible data collection, transparent population and
sample definitions, tidy analytical tables, data-quality reporting, and cautious
interpretation. It does **not** treat citations as scientific quality.

## Current status

Phase 1 final review is complete: the research corpus is fixed, six topic records
were directly revalidated, native taxonomy and custom text labels are separated,
the 1,000-work pilot has stratified missingness and a small category audit, and
the offline tests pass. Phase 2 collection has not started.

## Study design in one minute

- Period: `2020-01-01` through `2025-12-31`; any 2026 result must be labeled YTD.
- Population frame: OpenAlex articles, reviews, and preprints whose **primary**
  topic is in subfield 1702 (Artificial Intelligence) or 1707 (Computer Vision
  and Pattern Recognition).
- Population trends: use complete API `group_by` results where possible.
- Detailed records: deterministic probability samples from the frame, never an
  artificially balanced category sample used as if it represented prevalence.
- Classification has two non-equivalent layers: overlapping OpenAlex-native topic
  membership and separately reported custom title/abstract rules for LLM,
  Multimodal AI, and RAG. Primary-topic analyses remain a third, single-label view.
- Unit of analysis: a unique canonical OpenAlex Work ID. Author, institution,
  topic, and country links live in separate bridge tables in Phase 3.
- Impact: prefer OpenAlex FWCI (normalized by year, type, and primary subfield),
  citation percentiles, and age-aware sensitivity analyses. Raw citations are
  descriptive counts, not quality scores.

See [the collection strategy](docs/DATA_COLLECTION_STRATEGY.md) for the sampling
estimand and weighting details.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e ".[dev]"
cp .env.example .env
```

Add a free key to `.env` before non-trivial collection. OpenAlex currently
requires a verified key to follow a cursor after its first page. Never commit it.

## Phase 1 commands

All commands have `--help`.

```bash
openalex-validate-topics --help
openalex-discover-topics --help
openalex-collect-aggregates --help
openalex-collect-pilot --help
openalex-profile-pilot --help

openalex-validate-topics
openalex-discover-topics
openalex-collect-aggregates
openalex-collect-pilot --size 1000 --seed 20251019
openalex-profile-pilot data/interim/pilot_<UTC>/works.jsonl
jupyter nbconvert --execute --to notebook --inplace \
  notebooks/01_data_quality.ipynb
pytest
```

Without installing the package, use:

```bash
PYTHONPATH=src python -m ai_research_trends.crawling.validate_topics
PYTHONPATH=src python -m ai_research_trends.crawling.discover_topics
PYTHONPATH=src python -m ai_research_trends.crawling.collect_aggregates
PYTHONPATH=src python -m ai_research_trends.crawling.collect_pilot --size 1000
```

Each pilot run creates:

- `data/raw/openalex/pilot_<UTC>/page_####.json`: unchanged HTTP bodies;
- `data/raw/openalex/pilot_<UTC>/works.jsonl`: lossless record-level raw export;
- `data/raw/openalex/pilot_<UTC>/manifest.json`: query, timestamps, page hashes,
  rate-limit metadata, and completeness flags;
- `data/interim/pilot_<UTC>/works.jsonl`: deduplicated extracted records.

Raw and derived data are ignored by Git. Keep them in durable project storage and
archive manifests with submitted reports.

## Repository layout

```text
config/                         study and category definitions
docs/                           proposal, methods, dictionary, feasibility report
data/raw/                       immutable API response bodies (Git-ignored)
data/interim/                   extracted/normalized intermediate data (Git-ignored)
data/processed/                 future Parquet analytical tables (Git-ignored)
data/metadata/                  manifests and quality reports (Git-ignored)
src/ai_research_trends/
  crawling/                     API client and collection CLIs
  preprocessing/               Phase 3 table builders
  features/                    bibliometric feature engineering
  analysis/                    Phase 4 statistical analysis
  ml/                          Phase 5 leakage-aware experiments
notebooks/                      thin, numbered presentation notebooks
dashboard/                      Phase 6 application
models/                         fitted artifacts (Git-ignored)
reports/                        reports and figures
tests/                          unit tests
```

All importable modules live under the single `ai_research_trends` package; the
five installed CLI entry points in `pyproject.toml` target that package.

## Reproducibility and ethics

OpenAlex is a changing research graph. Every run records retrieval time, exact
parameters, raw-body SHA-256 hashes, and API-returned query metadata. Topic
assignments changed substantially in October 2026; do not compare a newly
retrieved series with a pre-change export without documenting that break.

Coverage, author disambiguation, affiliation matching, references, abstracts,
topics, countries, and OA status can all be missing or wrong. Results describe
OpenAlex coverage under the declared design—not all research activity or research
quality. No causal claim is made from the OA/impact association.
