# Architecture & Progress

## Overall structure
```
[Next.js frontend] <-> [Flask backend] <-> [MongoDB Atlas]
                          |        (users/conversations/feedback + vector DB, unified)
                          v
                  [Intent Classifier]
                          v
              [Hybrid Retrieval: BM25 + Dense + Reranker]
                          v
                  [Google Gemini API (Gemini 3.5 Flash)] -> answer with cited articles
```

## Scope
Guidance covering the period from when a military service obligation arises up to
enlistment. Anything after enlistment (unit assignment, KATUSA/language-soldier
recruitment eligibility, etc.) is explicitly out of scope — see the rationale under
"Scope decisions" below and test set item id=15 in `docs/eval_results-en.md`.

## Source documents (6, excerpted)
Military Service Act, its Enforcement Decree, its Enforcement Rule, the MMA
directive on overseas-travel administrative procedures for service obligors, the
MND directive on leave/travel expense payment for overseas permanent residents
serving as enlisted soldiers, and Attached Table 3 (overseas-emigration permit
eligibility table).

## Progress

### Stage 1: Data parsing pipeline — Done
- `pipeline/parser.py`, `chunker.py`, `tagger.py` -> `data/processed/law_chunks.json`
  (272 chunks)
- Preserves article/paragraph structure; Attached Table 3 rows are converted to
  natural-language sentences; chunks are tagged with `user_type_tags`,
  `topic_tags`, `refers_to` metadata.
- Issues found and fixed during verification:
  - A bug where `refers_to` mistook a chunk's own article number (embedded in
    its header) for a cross-reference (224 of 270 chunks polluted -> down to 2
    after the fix, and those 2 turned out to be genuine self-citations in the
    actual article text).
  - PDF line wraps that split words mid-syllable in the stored text (582
    occurrences -> 22, most of the remainder being legitimate 가/나/다 list
    markers).
  - Attached Table 3 category labels getting garbled by stray whitespace
    introduced during PDF table-cell extraction — fixed.

### Stage 2: Embedding model comparison + MongoDB ingestion — Done
- Compared 3 candidate models (BGE-m3 / multilingual-e5-large / KoE5) with a
  hand-built 15-question test set (`data/eval/test_queries.json`) using
  Recall@K and MRR -> **BGE-m3 selected** (full results in
  `docs/eval_results-en.md`).
- Embedded all 272 chunks with BGE-m3 and loaded them into a MongoDB Atlas
  Vector Search index (`law_chunks_vector_index`); verified with a live
  `$vectorSearch` query.
- Infrastructure: `config.py` (loads `.env`), `db/mongo.py` (shared connection
  helper).

### Stage 3: Hybrid retrieval (BM25 + Dense + Reranker) — Done
- `retrieval/bm25_search.py`: BM25 over content words only (particles/endings
  stripped via `kiwipiepy` morphological analysis) — Recall@5 = 1.0 on the
  test set even standalone.
- `retrieval/vector_search.py`: thin wrapper around Atlas `$vectorSearch`.
- `retrieval/hybrid.py`: weighted sum of min-max normalized BM25 + Dense
  scores. Grid search settled on `alpha=0.3` (70% BM25, 30% Dense) -> perfect
  Recall@5/10, MRR 0.929.
- `retrieval/reranker.py`: BAAI/bge-reranker-v2-m3 cross-encoder re-ranks the
  hybrid candidates. Didn't move Recall/MRR much on this tiny test set, but
  gives well-calibrated 0-1 relevance scores (0.000 for the out-of-scope
  KATUSA question vs. 0.77-0.999 for real matches) — kept in the pipeline for
  that reason (see `docs/eval_results-en.md`).
- Found and fixed a mislabeled ground-truth answer in the test set along the
  way (item 14 was missing its best answer, Military Service Act Art. 94).

### Stage 4: Intent classifier (lightweight, rule-based) — Done
- `classifier/model.py`: keyword tables for user type (permanent
  resident/international student/dual national/2nd-gen overseas Korean) x
  topic (postponement, overseas-travel permit, permit revocation, for-profit
  activity restriction, travel-expense payment, service duties, penalties,
  reduction/exemption), plus out-of-scope keywords.
- `classifier/predict.py`: applies the rules to an incoming question; returns
  a fallback message instead of doing retrieval when an out-of-scope keyword
  (e.g. KATUSA) is matched.
- `pipeline/tagger.py` was refactored to pull its keyword tables from
  `classifier/model.py` instead of duplicating them, so chunk tags and query
  intent classification stay on the same vocabulary (useful later for
  tag-filtered retrieval).
- Validated against the 15-question test set: explicit keyword matches work
  well; colloquial phrasing (e.g. "can I put it off?" instead of the formal
  term for "postponement") needed a few synonyms added. Cases needing implicit
  context (e.g. a user type mentioned in an earlier turn but not repeated) are
  left as a known limitation of a stateless rule-based classifier — to be
  addressed by swapping in a lightweight trained classifier once enough
  labeled query data accumulates, per the original plan.

### Stage 5: Answer generation (Google Gemini API) — In progress
Switched from the Anthropic Claude API to the Google Gemini API (rationale in
`docs/devlog-en.md`). `generation/answer.py` generates citation-bearing answers
grounded strictly in the retrieved article text.

### Stage 6 onward: Not started
Finishing the Flask API, Next.js frontend (stage 7, including the next-intl
EN/KO toggle) — to be built in order per the plan.

## Scope decisions
- **KATUSA / language-soldier recruitment**: deliberately excluded from the
  dataset. Actual eligibility criteria (e.g. TOEIC score cutoffs) aren't set by
  statute — they come from an annual MMA recruitment notice that changes every
  year, so baking them into the RAG corpus would go stale almost immediately.
  Properly including the relevant directive would also pull in a long chain of
  cross-referenced provisions across the Act, Decree, and Rule, making the
  scope balloon indefinitely. Related questions are caught by keyword matching
  in the intent classifier and answered with a fallback message pointing users
  to the current-year MMA recruitment notice (implemented in Stage 4).
- **Frontend KO/EN toggle**: planned for Stage 7 via next-intl — required
  since the target users are overseas Koreans, many more comfortable reading
  English.
