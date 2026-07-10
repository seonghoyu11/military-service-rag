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

## Prototype validation: diagnosing and fixing "enlistment postponement" tagging/ranking (2026-07-10)

Wired up a Flask API (`app.py`, `routes/query.py`) plus a static HTML prototype
(`frontend/prototype.html`) and found/fixed the following while testing real
questions against it.

### Issue 1: the "postponement" topic tag had no directionality

For "I'm a permanent resident, how do I get an enlistment postponement?", a
chunk about the *opposite* meaning — Art. 24 of the overseas-travel
administrative directive (the voluntary-early-enlistment program, which
explicitly *cancels* an existing postponement) — ranked first, while the
actual answers (Enforcement Decree Art. 128/149, Attached Table 3) were either
missing from the candidate pool or ranked far below it.

**Root cause:**
- `tagger.py` (via the shared keyword table in `classifier/model.py`) tagged
  "postponement" purely on substring presence.
- Every chunk's text is prefixed with a header like `[Act 제70조(국외여행의
  허가 및 취소) 제N항]`, and that article's own *title* contains "취소"
  (cancellation) — so every paragraph of Art. 70 got falsely flagged as
  co-occurring "postponement" + "cancellation" regardless of that
  paragraph's actual content.
- More fundamentally: the intent classifier's tags were never wired into
  actual retrieval ranking (hybrid + reranker) at all — they were purely
  display metadata. No amount of tag refinement could have changed the
  search results by itself.

**Fix:**
- Split the "postponement" topic into two directions: `입영연기_신청`
  (grounds for getting one) and `입영연기_취소` (grounds for an existing one
  being cancelled/withdrawn).
  - Corpus side: a precise regex (`연기(를|처분을|처분의|처분과|의)?.{0,25}?취소`)
    matches only the "the postponement itself is being cancelled" case (6
    chunks) — far narrower than raw "postponement"+"cancellation"
    co-occurrence (39 chunks), which would have wrongly caught unrelated
    "permit revocation as a penalty" provisions (Art. 70, Art. 147-2, etc.).
  - Article 24 of the travel directive has paragraphs that never literally
    say "postponement...cancelled," so an article-title override was added:
    if the title contains "입영희망" (wishes to enlist), tag it `_취소`
    regardless of body wording — the whole article is inherently about
    giving up an existing postponement to enlist early.
  - Query side: cancellation/negation cues ("cancel," "withdraw," "want to
    stop") trigger `_취소`; otherwise default to `_신청`.
- Wired the tags into `routes/query.py`: widened the candidate pool
  (30→50, since Art. 128 was previously outside it) and the reranked pool
  (top-5→top-15), then applied a ±0.25 score adjustment based on whether the
  chunk's direction tag matches the query's, before taking the final top-5.

**Re-verification:**
- "I'm a permanent resident, how do I get a postponement?" → Enforcement
  Decree Art. 128(2) now ranks first (previously absent from the candidate
  pool entirely); Art. 24 (the cancellation-direction chunk) drops to 4th.
- "I'm a permanent resident, I want to cancel my postponement" (opposite
  direction) → Art. 24 correctly boosts to ranks 1-3.
- "I've held a permanent-residency for over 3 years, up to what age can I get
  an overseas-travel permit?" (a residency-duration-specific question) →
  Attached Table 3 sweeps the entire top-5. This confirms the system now
  correctly routes general procedural questions to Art. 128 and
  duration-specific questions to Table 3 — Table 3 not appearing for the
  first, general question wasn't a bug after all.

### Issue 2: steering the out-of-scope (KATUSA etc.) fallback toward adjacent, answerable info

Previously, detecting a KATUSA/language-soldier keyword just returned "not in
the law database." Improved it so that when a covered user type (permanent
resident, international student, etc.) is also detected in the same
question, the fallback steers toward genuinely answerable adjacent
information — the voluntary-early-enlistment program (Art. 24) — instead of
a dead end. `classify()` now returns a `related_lookup` (law name + article
number) when applicable; `routes/query.py` fetches that article's full text
and returns it as `related_scope_info`. When no user type is detected, no
lookup is attempted — just a generic re-prompt.

Tested: "How do I get assigned to KATUSA?" (no user type) → generic guidance
only, `related_scope_info: null`. "I want to apply for KATUSA, can permanent
residents do that too?" (user type detected) → permanent-resident-specific
guidance plus all 9 paragraphs of Art. 24 returned as `related_scope_info`.
Both behaved as intended.
