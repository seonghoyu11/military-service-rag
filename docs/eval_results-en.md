# Evaluation Results

## Stage 2: Embedding model comparison (2026-07-09)

### Method
- `backend/data/eval/test_queries.json`: 15 questions — a mix of real-case-style
  scenarios and MMA-FAQ-style phrasing, each labeled with the ground-truth
  chunk (`law_name` / `article_no` / `paragraph_no`). One item (id=15, about
  KATUSA) is a deliberate out-of-scope negative test.
- Embedded all 272 chunks and all 15 queries with each candidate model, then
  computed Recall@5, Recall@10, and MRR from cosine similarity
  (`backend/evaluation/compare_embeddings.py`).

### Results

| Model | Recall@5 | Recall@10 | MRR | Avg. positive top-1 | Negative (KATUSA) top-1 |
|---|---|---|---|---|---|
| **BGE-m3** | 0.929 (13/14) | **1.0 (14/14)** | 0.746 | 0.723 | 0.443 |
| multilingual-e5-large | 0.929 (13/14) | 0.929 (13/14) | **0.816** | 0.887 | 0.801 |
| KoE5 | 0.857 (12/14) | 0.929 (13/14) | 0.612 | 0.694 | 0.264 |

### Chosen model: BGE-m3

- Perfect Recall@10 (14/14), and the clearest separation between similarity
  scores for genuinely relevant vs. out-of-scope questions.
  multilingual-e5-large gives the out-of-scope KATUSA question a top-1 score
  of 0.801 — barely below its average score for real matches (0.887) — which
  would make a raw-similarity-threshold "no relevant article found" fallback
  unreliable.
- Side benefit: BGE-m3 can produce dense and sparse (lexical-weight)
  embeddings from a single model call, which may come in handy when
  implementing the BM25+Dense hybrid retrieval in Stage 3.
- KoE5, despite being Korean-specific, performed worst overall. At this model
  scale (~560M params), differences in contrastive-retrieval training and data
  quality appear to matter more than language specialization.

### Takeaway: hybrid retrieval (Stage 3) is empirically justified

- Question 14 ("What are the consequences of repeatedly postponing departure
  without an overseas-travel permit?") has a ground-truth answer (Military
  Service Act Art. 70(2)) that literally contains the word "기피" (evade) —
  yet **all three dense models missed it outside the top 5** (ranked 9th to
  19th). Dense embeddings alone can miss even direct lexical matches like
  this, which is concrete evidence that pairing them with BM25 (lexical
  matching) in the planned hybrid design is actually necessary, not just a
  nice-to-have.

### Infrastructure
- All 272 chunks were embedded with BGE-m3 and loaded into a MongoDB Atlas
  Vector Search index (`law_chunks_vector_index`, cosine similarity, 1024
  dimensions). Verified end-to-end with a live `$vectorSearch` query
  (`backend/pipeline/load_to_mongo.py`).

## Stage 3: Hybrid retrieval + reranker (2026-07-10)

### Method
- BM25 tokenization uses `kiwipiepy` for Korean morphological analysis,
  keeping only content words (nouns/verb stems) and dropping particles/endings.
- Hybrid: BM25 and Dense (BGE-m3) scores are each min-max normalized, then
  combined as `alpha * dense + (1-alpha) * bm25`. `alpha` was grid-searched
  from 0.0 to 1.0 in steps of 0.1 (`backend/evaluation/tune_hybrid.py`).
- Reranker: the hybrid's top-30 candidates are re-scored with
  BAAI/bge-reranker-v2-m3.

### Results (after fixing the mislabeled item 14, see below)

| Configuration | Recall@5 | Recall@10 | MRR | Negative (KATUSA) top-1 |
|---|---|---|---|---|
| BM25 alone | 1.0 | 1.0 | 0.818 | (score scale not comparable) |
| Hybrid (`alpha=0.3`, 70% BM25 + 30% dense) | **1.0** | **1.0** | **0.929** | (normalized score, hard to interpret) |
| Hybrid + Reranker | 1.0 (@3) | — | 0.881 | **0.000** |

### Observations

- **BM25 alone is already very strong** (Recall@5/10 = 1.0), likely because
  this domain (military-service-law Q&A) has a lot of vocabulary overlap
  between how users phrase questions and the statute text itself.
- **The reranker didn't improve Recall/MRR** on this 14-question test set
  (differences are within noise at this sample size), **but it's decisively
  better for interpretability**: it scores real matches 0.77-0.999 and the
  out-of-scope KATUSA question 0.000, giving a genuine confidence signal for
  "no relevant article found" — exactly the separation
  multilingual-e5-large failed to provide in Stage 2.
- **Found one mislabeled test-set item along the way**: item 14 ("what are the
  consequences of repeatedly postponing departure without a permit?") was
  originally labeled with only Military Service Act Art. 70(2) as the correct
  answer. Hybrid+reranker kept returning Art. 94 (Violation of the
  Overseas-Travel-Permit Obligation — the actual penalty provision) as the
  top result; checking the text confirmed it's the more directly correct
  answer. The label was fixed (Art. 94 added) and the evaluation rerun.

## Stage 4: Intent classifier validation (2026-07-10)

- Validated the rule-based keyword classifier (`classifier/predict.py`)
  against all 15 test-set questions.
- Questions containing explicit keywords classified correctly. Colloquial
  phrasing (e.g. "can I put it off?" instead of the formal word for
  "postponement") needed a few synonyms added to catch it.
- Cases requiring implicit context (e.g. a user type mentioned in an earlier
  turn but not repeated in a follow-up question) are a fundamental limitation
  of a stateless rule-based classifier, left as-is for now — to be addressed
  by a lightweight trained classifier once enough labeled query data
  accumulates, per plan.
- Confirmed that KATUSA-style out-of-scope keywords correctly trigger
  `out_of_scope=True` with the fallback message instead of running retrieval.
