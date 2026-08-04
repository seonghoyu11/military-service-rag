# Backend — DutyCompass Flask API

> 한국어 버전: [README.md](README.md)

A Flask API server that parses the Military Service Act, its enforcement
decree/rule, MMA/MND directives, and Attached Table 3 into law chunks, then
serves them through BM25+Dense hybrid retrieval → reranker → (if confident)
Gemini-generated answers. See [`docs/architecture-en.md`](../docs/architecture-en.md)
for the overall architecture, [`docs/devlog-en.md`](../docs/devlog-en.md) for the
stage-by-stage build log, and [`docs/eval_results-en.md`](../docs/eval_results-en.md)
for the full quantitative/qualitative evaluation history.

## Directory layout

```
backend/
├── app.py                  # Flask app factory, blueprint registration, startup log
├── config.py                # Loads .env (GOOGLE_API_KEY, MONGO_URI, MONGO_DB_NAME)
├── requirements.txt
├── classifier/              # Rule-based intent/user-type classifier
├── pipeline/                 # PDF parsing -> chunking -> tagging -> embedding -> Mongo load
├── retrieval/                 # BM25 / Dense / Hybrid / Reranker
├── generation/                # Gemini answer generation + citation parsing
├── routes/                    # Flask endpoints (query / profile / feedback)
├── db/                         # MongoDB connection
├── evaluation/                  # Embedding/hybrid-alpha tuning + RAGAS quantitative eval
├── tests/                       # pytest unit tests
└── data/                        # Raw PDFs / parsed output / eval sets
```

## classifier/ — rule-based classifier

Despite the directory name, this is **not a trained ML model** -- it's a
keyword-table-driven rule classifier (`train.py` is an empty stub for a
future trained classifier). `model.py`'s tables are shared by both the
query-side classifier (`predict.py`) and the corpus-side chunk tagger
(`pipeline/tagger.py`) so both sides use the same tag vocabulary.

- **`model.py`**
  - `USER_TYPE_KEYWORDS`: 4 user types (permanent resident / 2nd-gen overseas
    Korean / dual citizen / international student) -> keyword lists
  - `TOPIC_KEYWORDS`: 8 topics (permit revocation / for-profit activity /
    travel-expense payment / overseas travel permit / leave / service /
    postponement / sanctions / exemption) -> keyword lists
  - `POSTPONEMENT_CANCEL_PATTERN` / `POSTPONEMENT_CANCEL_QUERY_KEYWORDS`:
    regex/keywords that split the "postponement" topic directionally into
    입영연기_신청 (requesting) vs 입영연기_취소 (cancelling)
  - `SYNONYM_ANCHOR_LOOKUPS`: a list of `{keywords, law_name, article_no}`
    entries that force specific articles into the retrieval candidate pool
    when trigger words appear -- for phrasing with near-zero lexical overlap
    with the statute text (e.g. 휴학/자퇴 (leave of absence/withdrawal) ->
    Overseas Travel Directive Art. 27; 아르바이트/알바 (part-time job) -> Art. 22)
  - `OUT_OF_SCOPE_CATEGORIES`/`OUT_OF_SCOPE_KEYWORDS` etc.: tables that
    detect questions outside this project's scope (KATUSA, language soldiers,
    etc.) and return a guidance message + related article
  - `POST_SERVICE_KEYWORDS`: detects "after completing service" questions
    (out of scope -- no data exists for this at all)
- **`predict.py`**: `classify(question, session_user_type=None)` applies the
  tables above and returns `{user_type_tags, topic_tags, out_of_scope,
  fallback_message, related_lookup, anchor_lookups}`. Order of evaluation:
  post-service check -> out-of-scope category check -> (if in scope) user-type/
  topic tagging + anchor_lookups.

## pipeline/ — raw PDF to Mongo-loaded chunks

- **`parser.py`**: `parse_standard_law` uses `pdfplumber` to extract text from
  the 5 standard-law PDFs (strips headers/footers, repairs line-wrap
  artifacts, strips revision-history tags, splits into articles/paragraphs
  via `제N조(...)`/circled-numeral markers). `parse_별표3` is a dedicated
  table parser for the Attached Table 3 PDF (forward-fills merged cells,
  converts each row into a natural-language Korean sentence).
- **`chunker.py`**: `chunk_articles` chunks at the article level when the body
  is short/single-paragraph, otherwise at the paragraph level, prefixing each
  chunk with a `[Law Name Art. N (Title)]` header. `extract_references` pulls
  in-body citation references (`refers_to`).
- **`tagger.py`**: applies `classifier/model.py`'s keyword tables to tag each
  chunk with `user_type_tags`/`topic_tags`, including the same directional
  postponement split used on the query side. Overseas Travel Directive Art.
  24 is special-cased to always get the postponement/cancellation tags.
- **`embedder.py`**: config for 3 embedding models (`bge-m3` /
  `multilingual-e5-large` / `koe5`) plus `embed_passages`/`embed_queries`
  wrappers. Production uses `bge-m3`.
- **`load_to_mongo.py`**: loads `data/processed/law_chunks.json`, embeds every
  chunk with `bge-m3`, reloads the `law_chunks` Mongo collection, and
  creates/rebuilds the Atlas Vector Search index (1024-dim cosine + filter
  fields on the tag arrays), polling until queryable.
- **`run_pipeline.py`**: end-to-end script (parse -> chunk -> tag) that
  produces `law_chunks.json` (note: paths are hardcoded absolute paths).

## retrieval/ — hybrid search + reranker

- **`bm25_search.py`**: Korean tokenization via `kiwipiepy.Kiwi`, keeping only
  content-bearing POS tags, indexed with `rank_bm25.BM25Okapi`.
- **`vector_search.py`**: queries MongoDB Atlas `$vectorSearch` directly
  (embeds the query with `bge-m3`).
- **`hybrid.py`**: min-max normalizes BM25/dense scores and combines them with
  weight `alpha` (`DEFAULT_ALPHA=0.3`, tuned via `evaluation/tune_hybrid.py`'s
  grid search).
- **`reranker.py`**: reranks candidates with the `BAAI/bge-reranker-v2-m3`
  cross-encoder (forced to CPU to avoid MPS memory pressure).
  `rerank(query, candidates, top_k=5)`.

## generation/ — Gemini answer generation

- **`gemini_client.py`**: a free-tier model whitelist (`ALLOWED_MODELS`) plus
  a 429-backoff `generate()` wrapper. `DEFAULT_MODEL` has changed more than
  once due to real daily-quota (RPD) limits discovered in production -- see
  the file's header comment and the "Stage 5" / lite-switch sections of
  [`docs/eval_results-en.md`](../docs/eval_results-en.md) for the current
  value and why.
- **`answer.py`**: `generate_answer(question, results)` -- a system prompt
  that forces the model to answer only from the retrieved results, with a
  separate branch so table (별표) sources are cited as "별표 N" instead of a
  malformed "Art. N".
- **`citation_parser.py`**: `parse_citations(answer_text, results)` splits the
  plain-text answer into `{type:"text"|"citation", ...}` segments for the
  frontend's clickable citation chips. Builds its matching regex from the
  literal `law_name` strings already in `results` (robust to law names with
  internal spaces, and handles table sources with no separate pattern). Has a
  documented known limitation around order-based fallback when the same
  table is cited multiple times for different rows -- see the docstring.
- **`ragas_llm.py`**: `WhitelistedGeminiChatModel`, wraps RAGAS's LLM judge so
  it also routes through `gemini_client.generate()` (same whitelist/backoff
  guarantees for judge calls).

## routes/ — Flask endpoints

| File | Method/path | Description |
|---|---|---|
| `query.py` | `POST /api/query` | Logic lives in the pure function `answer_question()` (called directly by RAGAS, no HTTP) -- classify -> retrieve -> rerank -> (if confident) generate |
| `profile.py` | `POST /api/profile` | Upserts a login-free session profile keyed by `session_id`, validated against `VALID_USER_TYPES` (5 values) |
| `profile.py` | `GET /api/profile/<session_id>` | Fetches a session profile |
| `feedback.py` | `POST /api/feedback` | Stores a 👍/👎 + comment + a full snapshot of that query's results (not a foreign-key reference, since `/api/query` is stateless) |

## db/

**`mongo.py`**: creates one `MongoClient(config.MONGO_URI)` at import time;
`get_db()` returns the `config.MONGO_DB_NAME` database. Collections used
elsewhere in the project: `law_chunks` (pipeline/retrieval), `profiles`
(routes/profile.py), `feedback` (routes/feedback.py).

## evaluation/

- **`compare_embeddings.py`**: compares the 3 embedding models, producing
  `data/eval/embedding_comparison_results.json`.
- **`tune_hybrid.py`**: grid search over `hybrid.py`'s `alpha`, producing
  `data/eval/hybrid_alpha_grid_results.json` (best MRR at alpha=0.3).
- **`ragas_eval.py`**: the production RAGAS quantitative evaluation script
  (faithfulness/answer_relevancy/context_precision/context_recall). Full run
  history and caveats are in [`docs/eval_results-en.md`](../docs/eval_results-en.md).
- **`ragas_embeddings.py`**: local BGE-m3 embedding wrapper for RAGAS's
  answer_relevancy metric (reuses `pipeline/embedder.py`, no network calls).
- **`results/`**: currently empty.
- `run_eval.py`: empty stub (unimplemented).

## tests/

`test_citation_parser.py` -- unit tests for `generation/citation_parser.py`.
`fixtures/citation_case1.json`/`citation_case2.json` are captured verbatim
from real `/api/query` responses (not hand-written) -- one exercises the
quadruple-别표-citation case, the other the space-in-law-name matching case,
both checked down to content, not just non-null result_index. Run with
`cd backend && python3 -m pytest tests/`.

## data/

- `raw/`: the 6 source PDFs (Military Service Act / its Enforcement Decree /
  Enforcement Rule / Overseas Travel Directive / Overseas Permanent Resident
  Travel Expense Directive / Attached Table 3).
- `processed/law_chunks.json`: the final parsed/chunked/tagged output, 270 chunks.
- `eval/test_queries.json`: 15 hand-written retrieval-quality eval questions
  (with labeled correct articles).
- `eval/ragas_eval_set.json`: 8 questions for RAGAS evaluation (some with
  ground_truth).
- `eval/embedding_comparison_results.json`, `eval/hybrid_alpha_grid_results.json`:
  outputs of the evaluation/ scripts above.

## Running it

For full setup (`.env`, MongoDB, dependencies) see the top-level
[`README.md`](../README.md)'s "Getting Started". Summary:

```bash
cd backend
cp .env.example .env   # fill in GOOGLE_API_KEY, MONGO_URI
pip install -r requirements.txt --break-system-packages
python pipeline/load_to_mongo.py   # one-time
python app.py                       # http://localhost:5001
```
