# Paper Discovery: optional human relevance review

The current TF-IDF Paper Discovery index has technical integrity checks, **not**
human-validated relevance. This small, separate evaluation uses 20 public,
illustrative research-idea queries. It does not change RQ1–RQ6, the original
12,000-work sample, the frozen topic classifier or its evaluation. No human
relevance labels or empirical Precision/nDCG scores are supplied by this
repository.

## Prepare the review

From the repository root, restore the documented LFS inputs, install the
package, and build/verify the discovery index as in [the web guide](WEB_APPLICATION.md).
Then run:

```bash
openalex-evaluate-discovery --help
openalex-evaluate-discovery prepare --help
openalex-evaluate-discovery prepare \
  --index-dir data/artifacts/web/paper_discovery \
  --queries config/discovery_evaluation_queries.jsonl \
  --output-dir data/application/paper_discovery_evaluation
```

If the configured index is elsewhere, omit `--index-dir` to use the application
configuration, or supply its verified path. `prepare` refuses to overwrite an
existing review directory. It searches each query against the *same frozen
index*, stores up to five result identities and display titles, and writes a
blank `judgments.csv`. The manifest records the query and index-manifest hashes,
index scope, ordered query/result identities and a hash of fixed display fields.
It does not infer relevance from cosine similarity.

Give a real reviewer the local CSV. The paper's title and query title/abstract
are supplied for context; where possible the reviewer should inspect the
paper's abstract or publication page before grading. Edit only `relevance`:

- `0`: not relevant to the research idea;
- `1`: partially relevant, e.g. shared methods or application but not the
  central problem;
- `2`: directly relevant to the central research question.

Use `0` for a clearly unrelated result; use `1` only when there is a
substantive connection. Do not guess when evidence is insufficient: record the
issue separately and leave the grade blank until resolved. The scoring command
intentionally refuses partial sheets. For stronger evidence, use two reviewers
working independently and report disagreements/adjudication separately; the
script does not certify reviewer identity or independence.

After all returned rows are judged:

```bash
openalex-evaluate-discovery score \
  --run-dir data/application/paper_discovery_evaluation \
  --annotator-id reviewer_1
```

This creates a new `scores_reviewer_1.json` without overwriting existing
results. `Precision@5` counts only grade-2 results, divided by five even if
fewer than five results were returned. `nDCG@5` uses gains `2^grade−1` and
logarithmic discount; its ideal order is computed from **only the observed
top-five judgments**, so it measures ranking within the retrieved set, not
recall against all relevant OpenAlex works. Queries with no results receive
zero on both metrics. The JSON records denominators, input hashes and the
self-reported annotator ID.

These 20 ideas are illustrative and not a probability sample of user queries.
The candidate universe may be the original sample alone or a later application
sync; compare runs only when index scope and corpus are the same. The scores
cannot establish global recall, semantic correctness, novelty or plagiarism
quality. Record annotation date, reviewer process, unresolved cases and index
version before citing any human result. Keep record-level judgments local; the
directory is Git-ignored and may contain copyrighted paper text or user notes.
