# Evaluation Results

## Table of Contents

- [Stage 1: Data parsing validation (2026-07-09)](#stage-1-data-parsing-validation-2026-07-09)
- [Stage 2: Embedding model comparison (2026-07-09)](#stage-2-embedding-model-comparison-2026-07-09)
- [Stage 3: Hybrid retrieval + reranker (2026-07-10)](#stage-3-hybrid-retrieval--reranker-2026-07-10)
- [Stage 4: Intent classifier validation (2026-07-10)](#stage-4-intent-classifier-validation-2026-07-10)
- [Prototype validation: diagnosing and fixing "enlistment postponement" tagging/ranking (2026-07-10)](#prototype-validation-diagnosing-and-fixing-enlistment-postponement-taggingranking-2026-07-10)
- [Retrieval quality fixes, round 2: diagnosing and fixing 6 issues (2026-07-10)](#retrieval-quality-fixes-round-2-diagnosing-and-fixing-6-issues-2026-07-10)
- [Threshold improvement check: margin (top1-top2) based low-confidence flagging (2026-07-15)](#threshold-improvement-check-margin-top1-top2-based-low-confidence-flagging-2026-07-15)
- [Queries 25-28 re-verification + one more evasive-phrasing gap fixed (2026-07-15)](#queries-25-28-re-verification--one-more-evasive-phrasing-gap-fixed-2026-07-15)
- [Deployment sync issue: "the code is right but the server response doesn't match it" (2026-07-10)](#deployment-sync-issue-the-code-is-right-but-the-server-response-doesnt-match-it-2026-07-10)
- [Final live-server re-verification of queries 25, 27, 28 (2026-07-21)](#final-live-server-re-verification-of-queries-25-27-28-2026-07-21)
- [7 new queries: live-server verification (2026-07-30)](#7-new-queries-live-server-verification-2026-07-30)
- [Issue A fix: "part-time job" question returned an unrelated article (2026-07-31)](#issue-a-fix-part-time-job-question-returned-an-unrelated-article-2026-07-31)
- [Issue B fix: the `low_confidence` flag wasn't shown in the frontend at all (2026-07-31)](#issue-b-fix-the-low_confidence-flag-wasnt-shown-in-the-frontend-at-all-2026-07-31)
- [Stage 5: Gemini Flash answer-generation verification (2026-07-31)](#stage-5-gemini-flash-answer-generation-verification-2026-07-31)
- [Stage 6: formalizing the Flask API -- session profile + feedback (2026-08-01)](#stage-6-formalizing-the-flask-api----session-profile--feedback-2026-08-01)
- [Stage 6's last piece: RAGAS quantitative evaluation (2026-08-01)](#stage-6s-last-piece-ragas-quantitative-evaluation-2026-08-01)

## Stage 1: Data parsing validation (2026-07-09)

### Method
- Parsed 6 law PDFs (the Military Service Act, its Enforcement Decree,
  Enforcement Rule, an MMA directive, an MND directive, and Attached Table 3)
  into 272 chunks while preserving article/paragraph structure. The rule was
  zero paraphrasing -- keep the original text verbatim. Attached Table 3 (a
  table) was converted row-by-row into natural-language sentences.
- 3 bugs found during sample verification.

### Results -- 3 bugs found and their fixes

| Bug | Scope of contamination | Fix |
|---|---|---|
| The `refers_to` (cross-reference) field was mistaking a chunk's own article number -- embedded in its own header -- for a cross-reference | 224 of 270 chunks (83%) | Fixed by extracting references only from the body text, before the header gets prepended |
| PDF extraction split words across a mid-syllable line break ("사\n람" -> "사람") | 582 occurrences -> 22 (most of the remainder being legitimate 가/나/다 list markers) | Fixed with a function (`join_wrapped_lines`) that joins a "Hangul + newline + Hangul" pattern |
| Attached Table 3's table-cell extraction inserted stray whitespace into category labels ("병역준비 역, 사회복 무요원...") | -- | Fixed by comparing against a whitespace-stripped copy |

See the "Stage 1: Law-parsing pipeline" section of `docs/devlog-en.md` for more detail.

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

## Retrieval quality fixes, round 2: diagnosing and fixing 6 issues (2026-07-10)

### Issue 5 (handled first): article-boundary parsing bug — rescanned all 272 chunks

**Symptom:** the chunk for Art. 21 of the overseas-travel administrative
directive actually had Articles 21, 22, and 23 merged together with no
boundary at all (`...재학하는 경우제22조(영리활동의 범위)...` — no space,
no line break — glued straight together).

**Full scan:** searched every chunk for the article-header pattern
`제\d+조(?:의\d+)?\([^)]+\)` appearing 2+ times in the body text. Found
**16 contaminated chunks out of 272** (concentrated mostly in the overseas-
travel directive; the "Article 30" label alone existed on 3 separate chunks
holding completely different content).

**Root cause:** not what was suspected going in (a single-block article
with no ①②③ markers failing to recognize the next article's header).
Instead, **`join_wrapped_lines()` — the function added in the very first
session to repair PDF line-wraps that split words mid-syllable — was
erasing legitimate line breaks at article boundaries as a side effect.**
The source PDF correctly had a line break ("...재학하는 경우\n제22조(영리활동의
범위)..."), but the blanket "Hangul + newline + Hangul → join" rule deleted
it, since both sides of that specific break happened to be Hangul
characters too.

**Fix:**
1. Added an exception to `join_wrapped_lines()`: don't join a newline
   immediately followed by a "제N조(" pattern. This resolved 15 of the 16
   contaminated chunks.
2. The remaining one (a `병역법 시행령 제156조` chunk) had a different cause —
   a numbered list item inside its body cited another provision as "법
   제46조(법 제54조제1항에서 준용하는 경우를 포함한다)," which happened to match
   the header pattern by coincidence. Fixed by adding a filter to
   `article_pattern`: reject a match whose parenthetical content itself
   contains "제N조" (confirmed no genuine article title in the corpus ever
   references its own article number this way before applying the filter).
3. After re-parsing, chunk count changed from 272 → **270** (correctly
   separating the merged articles shifted where the 500-character
   paragraph-splitting threshold kicked in). Confirmed Articles 21/22/23
   now each come out as exactly one chunk apiece.
4. Re-tagged → re-embedded with BGE-m3 → re-indexed on MongoDB Atlas.

Handled this before Issue 3 (synonym gaps) since the boundary bug could
plausibly have been driving some of what looked like a synonym problem.

### Issue 1: the right answer exists in the corpus, but retrieval never finds it — anchor force-include + explicit score boost

**Diagnosis:** `국외여행 업무처리 규정 제27조③` ("if a review of the student's
enrollment status finds the permit conditions are no longer met" → permit
revoked) is the correct answer for "휴학"(taking a leave of absence)/
"자퇴"(dropping out) questions, but neither word ever appears in that
article's text.
- "I'm studying abroad — if I take a leave of absence, does my postponement
  get cancelled?" → BM25 rank 2 (score 6.12, close to the rank-1 score of
  6.42) — not bad on its own.
- "What happens to my service obligation if I drop out of my foreign
  university?" → BM25 rank **168 out of 270** (score 1.19 vs. a rank-1
  score of 11.69) — effectively invisible.

**First attempt (failed):** added `SYNONYM_ANCHOR_LOOKUPS` to force Art. 27
into the candidate pool whenever "휴학/자퇴/제적" is detected, but it still
didn't surface in the top 5. Turned out Art. 27 was already naturally
present in the hybrid candidate pool — but **the cross-encoder reranker
itself judged the semantic connection between "휴학" and the statute's
phrasing as weak** (rank 16 of 50, score 0.0118), so it was already cut
before the top-15 rerank truncation even ran.

**Actual fix:**
1. Changed `reranker.rerank()` to score the **entire candidate pool**
   instead of truncating to the top 15 first — otherwise the boost below
   never gets a chance to act on it.
2. Applied an explicit score boost (+0.3) for anchor matches, separate from
   and in addition to the directional boost (±0.25), then took the final
   top 5.

**Re-verification:** for the "leave of absence" question, Art. 27③ now
ranks **#1** at 0.5618 (previously didn't even make the candidate pool).
For the "dropped out" question, all 4 paragraphs of Art. 27 sweep the
top 4.

### Issue 2: re-checking the confidence threshold — confirmed a raw score alone can't cleanly separate noise from real answers

**Diagnosis:** confirmed by reading the code that threshold logic was not
implemented at all.

**Measured score distribution** (reranker top-1 score, after the Issue 5 fix):

| Case | Score | Note |
|---|---|---|
| Social-service-worker overseas travel (real answer) | 0.9882 | Clearly high |
| Dad is a company-posted expat (real answer) | 0.1086 | |
| Got permanent residency 2 years ago (real answer, sentence fragment) | **0.0061** | |
| I want to delay enlistment (real answer, but a synonym gap) | 0.0073 | |
| Dual national not renouncing Korean citizenship (noise) | **0.0147** | |
| Dual national working a job in Korea (noise) | 0.0007 | |

**Key finding:** real-answer cases (0.0061, 0.0073) scored **lower** than a
noise case (0.0147) — an inversion that empirically confirms **no single
absolute threshold can cleanly separate the two** on this signal alone.
Likely because the reranker tends to score short, incomplete
sentences/statements (as opposed to well-formed questions) lower regardless
of relevance, and a noise case can coincidentally score a bit higher just
from partial vocabulary overlap.

**Implementation:** given that finding, implemented as an **advisory flag,
not a hard cutoff**. Below `LOW_CONFIDENCE_THRESHOLD = 0.05`, the response
includes `low_confidence: true` plus a re-prompt suggestion, but the
retrieved results themselves are still returned (hiding them would suppress
more legitimate weak-signal answers than it filters actual noise). This
threshold is known to sometimes flag a correct answer as low-confidence;
a better signal (e.g. LLM-based relevance re-verification once Stage 5's
Claude API integration exists) is left as future work.

### Issue 3: user-phrasing vs. statute-vocabulary synonym gaps (re-evaluated after the Issue 5 fix)

- "취업" (formal word for "employment") → 영리활동 (for-profit activity):
  already matched correctly (was already in the keyword list) — did not
  reproduce.
- "아르바이트" (part-time/casual work) → 영리활동: genuine gap confirmed,
  keyword added.
- "박사과정" (PhD program) → 유학생 (international student): genuine gap
  confirmed (only "유학" existed, no degree-program phrasing) — added
  "박사과정"/"석사과정"/"석박사"/"학위과정"/"대학원생".

### Issue 4: opposite-meaning matches recurring — root cause was misclassification as "일반" (general)

**Diagnosis:** "I'm a permanent resident, up to what age can I avoid
enlisting?" was being classified as `topic_tags: ['일반']` — none of the
"postponement" keywords matched at all, so the directional correction logic
never even triggered. As a result, Art. 24 (the opposite-meaning article,
about voluntary early enlistment) won purely on raw lexical/semantic
similarity.

**Fix:**
1. Added "언제까지" (until when)/"몇 살까지" (until what age)/"나이 제한" (age
   limit) to the "postponement" topic keywords.
2. Added "자진" (voluntarily)/"조기" (early)/"빨리 가고" (want to go
   sooner)/"일찍 가고" (want to go early) as cancellation-direction signals.
3. (Found along the way) `POSTPONEMENT_CANCEL_QUERY_KEYWORDS`'s bare
   "취소"/"철회" keywords couldn't distinguish "취소되나요?" (passive,
   asking *whether* it will be cancelled) from "취소하고 싶어요" (active,
   *wanting* to cancel it) — discovered when re-verifying Issue 1, since
   "I'm studying abroad, if I take a leave of absence does my postponement
   get cancelled?" was being misclassified as cancellation-direction.
   Narrowed the keywords to active-intent phrasings only ("취소하고 싶,"
   "취소하려," "철회하고 싶," etc.).
4. (Found along the way) some paragraphs of Art. 24 (e.g. paragraph 8,
   which is purely a resubmission-timing rule) never matched any
   "postponement" keyword at all, so they never got a directional tag and
   quietly skipped the directional boost/penalty entirely. Fixed in
   `tagger.py`: the overseas-travel directive's Art. 24 is now
   unconditionally tagged `입영연기_취소` (identified by exact law name +
   article number, not a title-substring match), regardless of what that
   specific paragraph's body says — since the whole article is inherently
   about voluntarily giving up a postponement. Scoping it to the exact
   article (rather than any article whose title contains "입영희망") avoids
   misclassifying the unrelated Enforcement Decree Art. 135-2 ("processing
   of active-duty volunteers"), which shares similar title wording but is a
   different, domestic-reclassification mechanism.

**Re-verification:** Attached Table 3 (0.309) / Art. 149 (0.308) / Art. 128
(0.287) now take the top 3; Art. 24 disappears from the top 5 entirely.

### Issue 6: a scope-detection blind spot — questions about the post-enlistment period

Added a new `POST_SERVICE_KEYWORDS` list ("전역" (discharge)/"제대"
(complete service)/"군복무 마친" (finished military service)/"갔다 온"
(already went), etc.) to detect questions about life after service. Routes
to a different message than the existing KATUSA-style out-of-scope branch
("This chatbot only covers procedures from when a service obligation arises
up to enlistment. For post-discharge matters, please contact your
jurisdiction's Military Manpower Administration office") — kept as its own
category since it's a structurally different kind of "out of scope" than
the KATUSA recruitment-notice case (no data exists at all here, vs. a
yearly-changing notice there).

### Final 12-query regression/verification results

| # | Question | Result |
|---|---|---|
| 1 | Leave of absence while studying abroad — does my postponement get cancelled? | ✅ Art. 27③ ranks #1 (0.5618); previously wasn't even in the candidate pool |
| 2 | What happens to my service obligation if I drop out of my foreign university? | ✅ All 4 paragraphs of Art. 27 sweep the top 4 |
| 3 | Dual national — any downside to working a job in Korea? | Correctly classified as 영리활동/이중국적자; `low_confidence: true` (0.0007) — a legitimately low-confidence call, since the corpus genuinely has no answer from this specific angle |
| 4 | PhD program at a US grad school — what's the age limit? | ✅ 유학생 correctly detected; correctly classified as postponement/"wants a postponement" direction |
| 5 | Permanent resident — up to what age can I avoid enlisting? | ✅ Table 3 / Art. 149 / Art. 128 take the top 3; Art. 24 completely pushed out |
| 6 | Someone who already served, then gets permanent residency again — what happens? | ✅ Issue 6 fallback works correctly |
| 7 | Dual national — do I have to serve if I don't renounce Korean citizenship? | `low_confidence: true` (0.0147), correctly flagged |
| 8 | I want to delay enlistment — is there a way? | ⚠ "늦게 가고" (want to go later) phrasing wasn't in the postponement keyword list, so it fell through to `topic_tags: ['일반']` — a similar synonym gap remains, left out of this fix's scope |
| 9 | My dad is a company-posted expat — do I also get a postponement? | ✅ No regression (Table 3/Art. 128/Art. 149 still on top) |
| 10 | Got my US permanent residency 2 years ago | ✅ No regression, Table 3 still ranks #1 (`low_confidence: true` is advisory-only, so the result is still shown) |
| 11 | Social-service-worker — can I travel overseas? | ✅ No regression (0.9882, unchanged) |
| 12 | Got into KATUSA, and my permanent-residency application is still pending — what happens? | ✅ No regression; out_of_scope + permanent-resident-specific guidance + all 9 paragraphs of Art. 24 |

**Summary:** 5 of the 6 issues (1, 3, 4, 5, 6) fully resolved. The remaining
one (Issue 2, threshold) turned out to be fundamentally unsolvable with a
single absolute score cutoff, confirmed empirically, and was implemented as
an advisory signal instead. Query 8 surfaced one more similar synonym gap,
logged as a follow-up.

*(2026-07-10 follow-up: the Query 8 gap ("delay enlistment") was
subsequently closed by adding adverb+verb combination keywords — "늦게 가,"
"천천히 가," "나중에 가," "최대한 늦게," etc. — to
`TOPIC_KEYWORDS["연기"]`.)*

## Threshold improvement check: margin (top1-top2) based low-confidence flagging (2026-07-15)

### Background

Issue 2 established that a single absolute score can't cleanly separate real answers
from noise (a genuine answer at 0.0061 scored lower than a noise case at 0.0147).
Hypothesis: the **gap between the top-1 and top-2 scores** might be a more reliable
signal than the absolute score — a real answer should have its top result win by a wide
margin, while noise results should all cluster together at similarly low scores.

Added margin logging to `routes/query.py` right after the reranker call (before the
directional/anchor boosts, so those domain-specific nudges don't distort the reranker's
own confidence signal), then re-ran the final 12 regression queries to collect values.

### Results

| # | Question | Category | top1 | top2 | margin | Absolute threshold (0.05) verdict |
|---|---|---|---|---|---|---|
| 1 | Leave of absence while studying abroad | TP | 0.1648 | 0.1072 | 0.0576 | high-conf |
| 2 | Drop out of foreign university | TP (synonym gap already closed) | 0.0225 | 0.0179 | 0.0046 | low-conf |
| 3 | Dual national, working a job in Korea | Negative (no real answer in corpus) | 0.0007 | 0.0003 | **0.0004** | low-conf |
| 4 | PhD program, age limit | TP | 0.2073 | 0.0437 | 0.1636 | high-conf |
| 5 | Permanent resident, how long can I avoid enlisting | TP | 0.4486 | 0.3120 | 0.1366 | high-conf |
| 6 | Already served, now getting permanent residency again | out_of_scope | — | — | N/A (reranker never runs) | — |
| 7 | Dual national, not renouncing citizenship | Negative | 0.0147 | 0.0141 | **0.0006** | low-conf |
| 8 | Want to delay enlistment | TP (synonym gap patched) | 0.0073 | 0.0059 | 0.0014 | low-conf |
| 9 | Dad is a company-posted expat | TP | 0.1086 | 0.0715 | 0.0371 | high-conf |
| 10 | Got permanent residency 2 years ago | TP (weak signal) | 0.0061 | 0.0053 | 0.0008 | low-conf |
| 11 | Social-service worker, overseas travel | TP | 0.9882 | 0.9583 | 0.0299 | high-conf |
| 12 | Got into KATUSA, PR application pending | out_of_scope | — | — | N/A (reranker never runs) | — |

**Side finding**: queries 6 and 12 both hit the intent classifier's early `out_of_scope`
return path, so the reranker is never called and no margin gets logged for them — they
naturally drop out of the margin comparison (a branch this check hadn't accounted for
going in).

### Hypothesis check

**Strong true positives (1, 4, 5, 9, 11)**: margins land in the 0.03–0.16 range, clearly
separated from the noise cases (0.0004–0.0006). But these cases already clear the 0.05
absolute threshold and were correctly classified `low_confidence=False` without any help
from margin — margin adds nothing here.

**The low-absolute-score band where the threshold actually struggled (2, 3, 7, 8, 10 —
all below 0.05)**: ranking by margin within this band puts the noise cases (#3=0.0004,
#7=0.0006) below the true positives (#10=0.0008, #8=0.0014, #2=0.0046) every time — the
direction matches the hypothesis. Specifically, re-examining the inversion case that
motivated this whole check (#10 vs #7): absolute score had it backwards (0.0061 <
0.0147), but margin puts it back in the right order (0.0008 > 0.0006).

**However**, the margin gap within this band is itself only 0.0002–0.0010 — just as thin
as the absolute-score gap was. With only 2 noise samples and a 0.0002 margin difference
between #10 and #7, setting a hard threshold off these 12 queries risks overfitting badly
— a reranker retrain or slightly different phrasing could easily flip this ordering back.

### Conclusion and next steps

The hypothesis's **direction is supported** (noise margins are consistently smaller than
true-positive margins, and the problem inversion case gets corrected) — but margin buys
no extra separation for the strong true positives the absolute threshold already
handles, and in the low-confidence band where it's actually needed, the gap is too thin
(~0.0002) to justify a threshold off 5–7 samples. Not implementing a margin condition in
`low_confidence` for now.

Alternatives to discuss next session (not started now):
- (a) Collect more labeled queries (at least ~10 each of noise/true-positive) and
  re-check the margin distribution, or calibrate a logistic regression over absolute
  score + margin together
- (b) Replace this judgment call entirely with LLM-based relevance re-verification once
  Stage 5 (Claude API integration) is done

The margin logging itself (the `[margin]` tag in `routes/query.py`) stays in the code to
keep collecting data from production traffic.

## Queries 25-28 re-verification + one more evasive-phrasing gap fixed (2026-07-15)

### Background

A prior session (28 stress-test scenarios run locally, never saved as a file in this
repo) reported that query 25 ("I want to delay enlistment, is there a way?") was being
classified `topic_tags: ['일반']` with noise-level relevance (0.007–0.01) surfacing as if
it were a normal answer. Re-opening the same question this session showed it correctly
classified as `topic_tags: ['연기', '입영연기_신청']`, `low_confidence: False` — the two
reports conflicted.

### Steps 1-2: clean restart, then actually re-ran queries 25-28

Ruled out a stale process with `pkill -9 -f "app.py"` and a clean restart. The startup
log confirmed 270 chunks in `law_chunks.json` and `POST_SERVICE_KEYWORDS` count 12 /
hash=2dc6d7a4 — the same code version as the prior session. Compared the live
`/api/query` response against `classify()` run standalone, side by side:

| # | Question | topic_tags | low_confidence | top1 article | `/api/query` matches standalone `classify()`? |
|---|---|---|---|---|---|
| 25 | Want to delay enlistment, is there a way? | `['연기', '입영연기_신청']` | False | Enforcement Decree Art. 125② (0.2573) | Yes |
| 26 | Dad is a company-posted expat, do I get a postponement too? | `['연기', '입영연기_신청']` | False | Table 3 (0.3586) | Yes |
| 27 | I have citizenship elsewhere, can't I just not go back to Korea? | `['일반']` | **True** | Table 3, 0.0123 (irrelevant) | Yes |
| 28 | I'd like to know how long I can delay it | `['연기', '입영연기_신청']` | False | Enforcement Decree Art. 124① (0.2524) | Yes |

### Step 3: verdict

Query 25 classified correctly on re-test, and the live server response matched the
standalone `classify()` output exactly, ruling out a deployment-sync issue too. **The
earlier "fell through to 일반" report doesn't reproduce this session** — there's no way
to inspect that other session's exact process state now, but the current code behaves
correctly, so Issue 8 is closed. Query 27, on the other hand, surfaced a **genuine new
gap**.

### Step 4: fixing the query-27 evasive-phrasing gap

The correct answer to "can't I just not go back to Korea?" is Military Service Act
Article 70 (the travel-permit obligation itself) and Article 94 (the penalty for
violating that obligation) — but phrases like "not go back" / "won't return" never use
legal terms like "evade" or "violation," so they matched neither the `제재` topic
keywords nor the BM25/dense candidate pool (the same shape as the leave-of-absence/
drop-out gap). Two changes in `backend/classifier/model.py`:

- Added the evasive-verb phrasing to `TOPIC_KEYWORDS["제재"]`
- Added two new `SYNONYM_ANCHOR_LOOKUPS` entries with the same keyword set, forcing
  Military Service Act Articles 70 and 94 into the candidate pool (same pattern as the
  existing leave-of-absence/drop-out → Article 27 anchor)

**Re-verification** (clean restart, query 27 only):

| | Before | After |
|---|---|---|
| topic_tags | `['일반']` | `['제재']` |
| anchor_lookups | `[]` | Military Service Act Art. 70, Art. 94 |
| low_confidence | True (0.0123) | **False** |
| top1 | Table 3 (irrelevant, 0.0123) | Art. 94 (0.3027, anchor boost applied) |
| top-5 | — | Art. 94 + Art. 70③④⑦②, correctly populated with relevant articles |

Checked the new anchor keywords ("not go back" / "won't return" etc.) against all 12
existing regression queries' text — no accidental overlaps, so regression risk is low.

### Threshold note

This fix doesn't touch the threshold value at all — it stays within the existing
advisory approach (`low_confidence` flag only, results still shown) and instead pulls
the genuinely relevant articles themselves up via anchor force-include + boost.
`LOW_CONFIDENCE_THRESHOLD = 0.05` is unchanged.

## Deployment sync issue: "the code is right but the server response doesn't match it" (2026-07-10)

### Symptom

Running `classifier/predict.py` standalone against "someone who already
served, then gets permanent residency again — what happens?" correctly
returns `out_of_scope=True` + `POST_SERVICE_FALLBACK_MESSAGE` (so the code
itself was right) — but an earlier live call to `/api/query` with the same
question reportedly surfaced noise-level search results (relevance
0.05–0.16) with no fallback at all.

### Diagnosis

1. **`law_chunks.json` itself was up to date** — 270 chunks, mtime matching
   the most recent re-parse. Different from an earlier precedent where the
   corpus had been "re-parsed" but the file actually being served was
   stale.
2. **`app.py` runs with `debug=True`**, so Werkzeug's auto-reloader is on —
   if a single process had stayed running the whole time, it should have
   auto-restarted on every file edit.
3. **Most likely actual cause: an orphaned/duplicate process.** Across this
   session's repeated restarts, killing by port alone
   (`lsof -ti:5001 | xargs kill -9`) didn't always fully clean up — at one
   point during this same session, two `app.py` processes were observed
   running simultaneously in `ps aux` alongside an "Address already in
   use" error (Werkzeug's reloader is a parent watcher process + child
   worker process; killing only the child that's bound to the port can
   leave the parent alive and confuse the next restart). An old process
   that was still holding stale code likely served that earlier request.
4. **Attempted reproduction:** at the time of this investigation, nothing
   was running on port 5001 at all (the backend had just been shut down at
   the user's request), so the exact failure couldn't be reproduced live.
   Instead, restarted from a fully clean state using
   `pkill -9 -f "app.py"` (matches by process name rather than port, so it
   also catches orphans) and re-verified from there.

### Re-verification (after restarting from a single, fully clean process)

**"Someone who already served, then gets permanent residency again — what happens?"**
```json
{
  "out_of_scope": true,
  "message": "This chatbot only covers procedures from when a service obligation arises up to enlistment. For post-discharge matters, please contact your jurisdiction's Military Manpower Administration office.",
  "related_scope_info": null,
  "intent": { "user_type_tags": ["영주권자"], "topic_tags": [], "out_of_scope": true }
}
```
Matches the expected behavior exactly (no search results, fallback fires correctly).

**"Got into KATUSA, and my permanent-residency application is still pending — what happens?"** (regression check)
```
out_of_scope: True
message: "...카투사: https://www.mma.go.kr/contents.do?mc=mma0000525 ..."
related_scope_info: 9 paragraphs (Art. 24)
```
No regression.

### Prevention going forward

Added a one-line startup fingerprint to `app.py`, printed to stderr
(`_log_startup_fingerprint()`):
```
[startup] pid=11149 law_chunks.json: 270 chunks, mtime=1783695412 | POST_SERVICE_KEYWORDS: 12 keywords, hash=2dc6d7a4
```
- `law_chunks.json` chunk count + mtime → instantly confirms whether the
  parsed corpus this process loaded matches the latest re-parse.
- `POST_SERVICE_KEYWORDS` count + a short sha256 hash → confirms whether a
  given code change has actually reached this process (a mismatched
  count/hash means a stale process is the one answering requests).
- Also logs the `pid`, so it can be cross-checked against
  `ps aux | grep app.py` to confirm the process actually listening is the
  one whose log line you're reading.

**Operational habit correction:** restart with `pkill -9 -f "app.py"`
(matches by process name) instead of `lsof -ti:5001 | xargs kill -9`
(matches by port) — confirmed in this session that port-based killing can
leave orphaned processes behind, given the reloader's parent/child process
structure.

## Final live-server re-verification of queries 25, 27, 28 (2026-07-21)

### Background

The 2026-07-15 session re-verified queries 25/27/28 and patched query 27 (evasive-phrasing
gap), but that verification happened inside the same session that made the fix -- a
"self-check right after the change" limitation. This session re-ran the same three queries
against a freshly, independently clean-restarted server, in a separate session, to confirm
the documented results actually reproduce.

### Clean restart confirmation

```
[startup] pid=97494 law_chunks.json: 270 chunks, mtime=1783695412 | POST_SERVICE_KEYWORDS: 12 keywords, hash=2dc6d7a4
 * Restarting with stat
[startup] pid=97631 law_chunks.json: 270 chunks, mtime=1783695412 | POST_SERVICE_KEYWORDS: 12 keywords, hash=2dc6d7a4
```

Confirmed no existing process (`ps aux | grep app.py` only matched the grep itself) after
`pkill -9 -f "app.py"`, then restarted. Both the parent and child pid match the same
`hash=2dc6d7a4`, 270 chunks as the 2026-07-15 session -- code/data versions confirmed
identical.

### `/api/query` re-verification results

| # | Question | topic_tags | anchor_lookups | low_confidence | top1 (boosted) | Matches eval_results.md (07-15)? |
|---|---|---|---|---|---|---|
| 25 | "I want to delay enlistment, is there a way?" | `['연기','입영연기_신청']` | `[]` | False | Decree Art. 125(2) (0.2573) | ✅ Matches to 4 decimal places |
| 27 | "I have citizenship, can I just not go back to Korea?" | `['제재']` | Military Service Act Art. 70, 94 | False | Military Service Act Art. 94 (0.3027) | ✅ Matches to 4 decimal places |
| 28 | "I want to know how long I can postpone" | `['연기','입영연기_신청']` | `[]` | False | Decree Art. 124(1) (0.2524) | ✅ Matches to 4 decimal places |

All three responses exactly matched the 2026-07-15 session's recorded results -- and since
no code was touched this session (pure verification only), this rules out both deployment
sync issues and code regression.

### Additional finding: raw reranker score vs. post-boost final score

The `[margin]` stderr log in `routes/query.py` (logged **before** the anchor/directional
boosts are applied -- pure cross-encoder score) was captured alongside the results:

```
[margin] query='저 군대 늦게 가고 싶은데 방법 있나요' top1=0.0073 top2=0.0059 margin=0.0014
[margin] query='시민권 있는데 그냥 한국 안 들어가면 안 되나요' top1=0.0123 top2=0.0121 margin=0.0003
[margin] query='언제까지 미룰 수 있는지 궁금해요' top1=0.0024 top2=0.0014 margin=0.0010
```

The raw top1 scores for all three queries (0.0024-0.0123) are noise-level -- well below
`LOW_CONFIDENCE_THRESHOLD = 0.05`. Without the anchor boost (+0.3) and directional boost
(±0.25), all three would have been flagged `low_confidence: true`, and query 27 in
particular would have surfaced an unrelated article as top1 instead of the correct one
(per the 07-15 record: pre-patch top1 was an unrelated Table 3 entry, raw score 0.0123).

In other words, this re-verification confirms not just that "the final response is
correct," but that **the anchor/directional boost mechanism is actually what determines
correctness for these three cases** -- observed directly at the raw-log level. This is
one step stronger evidence than the 07-15 record, and matches exactly the thin
0.0002-0.0014 margin gaps observed in the earlier margin experiment (see "Margin logging,
2026-07-15" section above).

### Conclusion

All 28 stress-test scenarios (1-28) are now verified against the live server. No action
items remain here -- next step is Stage 5 (Claude API integration) once the Anthropic API
key is issued.

## 7 new queries: live-server verification (2026-07-30)

### Background

Re-verifying at the HTTP level whether issues diagnosed in earlier sessions
(postponement/cancellation directionality, forced anchor inclusion, the threshold
advisory flag, etc.) are actually reflected in the running server. Not a standalone
script -- direct POST requests to `/api/query` against a live Flask server.

### Clean restart check

```
[startup] pid=62665 law_chunks.json: 270 chunks, mtime=1783695412 | POST_SERVICE_KEYWORDS: 12 keywords, hash=2dc6d7a4
 * Restarting with stat
[startup] pid=62739 law_chunks.json: 270 chunks, mtime=1783695412 | POST_SERVICE_KEYWORDS: 12 keywords, hash=2dc6d7a4
```

`pkill -9 -f "app.py"` killed nothing (exit code 1, no process was running) before
restarting with `python3 app.py`. Both the parent (62665) and child (62739) pids report
the same `hash=2dc6d7a4`, 270 chunks, and an mtime matching the real `law_chunks.json`
file mtime (1783695411) -- confirmed no zombie process or stale module load.

### `/api/query` re-verification results

| # | Question | topic_tags | user_type_tags | anchor_lookups | low_confidence | top1 (boosted) | Verdict |
|---|---|---|---|---|---|---|---|
| 1 | Leave of absence while studying abroad -- does my postponement get cancelled? | `['허가취소','연기','입영연기_신청']` | -- | Overseas Travel regulation Art. 27 | False | Art. 27③ (0.5618) | ✅ PASS |
| 2 | Withdrew from a foreign university -- what happens to my service obligation? | `['일반']` | `['전체']` | Overseas Travel regulation Art. 27 | False | Art. 27③ (0.3014) | ✅ PASS |
| 3 | Is it a problem if I have a part-time job? | `['영리활동']` | `['전체']` | `[]` | True | Enforcement Decree Art. 147-2 (0.0008) | ❌ FAIL |
| 4 | I'm a PhD student -- am I recognized as an international student too? | `['일반']` | `['유학생']` | `[]` | True | Enforcement Decree Art. 147 (0.0245) | ✅ PASS |
| 5 | I can't stay in Korea for 6+ months because I need to maintain my green card -- is that a problem? | `['일반']` | `['영주권자']` | `[]` | **False** | Overseas Travel regulation Art. 24 (0.0995) | ⚠️ PARTIAL |
| 6 | I'm a permanent resident -- until when can I avoid enlisting? | `['연기','입영연기_신청']` | `['영주권자']` | `[]` | False | Table 3 (0.3092) | ✅ PASS |
| 7 | What if I just don't go back to Korea? | `['제재']` | `['전체']` | Military Service Act Art. 70, 94 | False | Military Service Act Art. 94 (0.3044) | ✅ PASS |

Margin log (pre-boost, raw cross-encoder scores):

```
[margin] query='유학 중인데 휴학하면 입영연기가 취소되나요' top1=0.1648 top2=0.1072 margin=0.0576
[margin] query='외국 대학 자퇴하면 병역은 어떻게 되나요' top1=0.0225 top2=0.0179 margin=0.0046
[margin] query='아르바이트하면 문제되나요' top1=0.0008 top2=0.0002 margin=0.0006
[margin] query='박사과정 중인데 저도 유학생으로 인정되나요' top1=0.0245 top2=0.0066 margin=0.0179
[margin] query='영주권 유지하려고 한국에 6개월 넘게 못 있는데 문제없나요' top1=0.0995 top2=0.0965 margin=0.0030
[margin] query='영주권자인데 언제까지 입영 안 해도 되나요' top1=0.4486 top2=0.3120 margin=0.1366
[margin] query='그냥 한국 안 들어가면 안 되나요' top1=0.0082 top2=0.0073 margin=0.0008
```

### Root-cause analysis for the failed/partial cases

**#3 FAIL -- a logic gap, not a deployment sync issue.** The classifier correctly tags
the `영리활동` (for-profit activity) topic (`classifier/model.py`'s
`TOPIC_KEYWORDS["영리활동"]`), but there's no anchor/boost mechanism connecting that tag
to the specific article (Art. 22, scope of for-profit activity). `SYNONYM_ANCHOR_LOOKUPS`
(`classifier/model.py:101-126`) only has entries for leave-of-absence/withdrawal (Art. 27)
and evasive phrasing (Art. 70/94) -- nothing for for-profit-activity/part-time-job.
`_apply_directional_boost` (`routes/query.py:53`) only reacts to
`DIRECTIONAL_TAGS = {"입영연기_신청","입영연기_취소"}`, and
`_apply_anchor_boost`/`_inject_anchor_chunks` do nothing when `anchor_lookups` is an empty
list. As a result Art. 22 (raw score 0.0002, ranked 3rd among candidates) is left with no
forced inclusion or boost, and the unrelated Art. 147-2 (overseas-travel-permit
revocation) stays top1. In short: the anchor-forcing mechanism from Issue 1 was scoped
only to the "leave of absence/withdrawal" and "evasive phrasing" cases, and was never
extended to the part-time-job/for-profit-activity case. The code reproduced exactly as
it's actually running, so this isn't a deployment sync problem -- it's a pure
functionality gap.

**#5 PARTIAL -- a known, already-documented design limitation (consistent with
Issue 2).** `low_confidence` is an absolute cutoff:
`reranked[0][1] < LOW_CONFIDENCE_THRESHOLD(0.05)` (`routes/query.py:168`). This query's
top1 (raw 0.0995) clears the threshold, so `low_confidence=False` gets set, but its
margin over top2 (0.0965) is only 0.0030 -- the same "noise-level" gap as #3 (0.0006) or
#7 (0.0008). In other words, the absolute score alone can't tell whether this case is a
genuine answer or an ambiguous match that happened to clear the threshold. This isn't a
new bug; it's the same unresolved issue already concluded in the "Threshold improvement
check: margin (top1-top2) based low-confidence flagging (2026-07-15)" section above -- the
advisory-flag mechanism itself (not a hard cutoff) was confirmed working correctly in #3
(low_confidence=true fired, but results were still returned); it's just that the threshold
criterion doesn't account for margin, and that pre-existing limitation resurfaced here
too.

### Conclusion

5 of 7 (#1, 2, 4, 6, 7) PASS. #3 is a newly-discovered pure logic gap from the anchor
mechanism's limited scope (Issue 1 needs to be extended). #5 is a reproduction of the
already-documented threshold-vs-margin limitation, with the advisory-flag mechanism itself
confirmed working correctly. No deployment sync issue or code regression was found -- the
startup fingerprint (270 chunks, hash=2dc6d7a4) matched on both the parent and child
process, and every response was fully explainable by the current code logic.

**Suggested next action**: consider adding a for-profit-activity/part-time-job -> Art. 22
entry to `SYNONYM_ANCHOR_LOOKUPS`.

## Issue A fix: "part-time job" question returned an unrelated article (2026-07-31)

### Symptom

Item #3 from "7 new queries: live-server verification" above. "Is it a problem if I have a
part-time job?" was correctly classified as `topic_tags: ['영리활동']`, but top1 came back
as the unrelated Enforcement Decree Art. 147-2 (raw score 0.0008) with
`low_confidence: true`. The correct answer -- Overseas Travel regulation Art. 22 (scope of
for-profit activity) -- was left at its natural rank of 3rd (raw score 0.0002, noise
level).

### Root cause

`backend/classifier/model.py`'s `SYNONYM_ANCHOR_LOOKUPS` (leave-of-absence/withdrawal ->
Art. 27, evasive phrasing -> Art. 70/94) had no entry for for-profit-activity/part-time-job
-> Art. 22, so `routes/query.py`'s `_apply_anchor_boost` (+0.3) never fired for this case
at all. Re-confirmed: even when the classifier tags the topic correctly, if there's no
anchor mechanism linking that tag to a specific article, it has zero effect on the
retrieval ranking.

### Fix

Added an entry to `SYNONYM_ANCHOR_LOOKUPS` (`backend/classifier/model.py`):

```python
{
    "keywords": ["아르바이트", "알바", "파트타임", "영리활동"],
    "law_name": "병역의무자 국외여행 업무처리 규정",
    "article_no": "22",
},
```

### Code-path verification

In the leave-of-absence/withdrawal case, the correct chunk didn't even make it into the
candidate pool (top_k=40, candidate_pool=50) in the first place, which is why
`_inject_anchor_chunks` (forced inclusion) was needed. This Art. 22 chunk, by contrast,
was already ranked 3rd naturally by BM25/dense and therefore already inside the candidate
pool. So `_inject_anchor_chunks` is effectively a no-op here (the chunk already exists, so
nothing gets duplicated), and it was `_apply_anchor_boost` (`routes/query.py:70`) alone --
correctly matching once Art. 22 populated `anchor_lookups` and adding +0.3 -- that flipped
top1. Cross-referencing the margin log (pre-boost) against the final boosted score
confirms this exact code path actually fired (see the re-verification results below).
Neither the threshold nor the boost magnitude was changed.

### Re-verification results

Clean restart check (`pkill -9 -f "app.py"` then restart, no zombie processes):

```
[startup] pid=69673 law_chunks.json: 270 chunks, mtime=1783695412 | POST_SERVICE_KEYWORDS: 12 keywords, hash=2dc6d7a4
 * Restarting with stat
[startup] pid=69710 law_chunks.json: 270 chunks, mtime=1783695412 | POST_SERVICE_KEYWORDS: 12 keywords, hash=2dc6d7a4
```

| Question | anchor_lookups | topic_tags | low_confidence (before → after) | top1 (before → after) |
|---|---|---|---|---|
| Is it a problem if I have a part-time job? (아르바이트하면 문제되나요) | `[]` → Art. 22 | `['영리활동']` (unchanged) | true → **false** | Art. 147-2 (raw 0.0008) → **Art. 22 (0.3002)** |
| "저 알바 좀 오래 해도 되나요" (synonym regression, "can I work a part-time job for a long time?") | `[]` → Art. 22 | `['일반']`* | -- → false | -- → **Art. 22 (0.3004)** |

\* "알바" (informal for "part-time job") isn't in `TOPIC_KEYWORDS["영리활동"]`'s keyword
list (영리/취업/생업/아르바이트), so `topic_tags` still comes back `일반` (general) --
but `SYNONYM_ANCHOR_LOOKUPS` uses a separate keyword list that does catch "알바", so the
retrieval ranking still correctly puts Art. 22 at top1. Only the topic_tags label is
inaccurate (a minor gap, cosmetic for the UI intent label) with zero impact on actual
retrieval results -- out of scope for this fix, tracked separately without patching it.

Margin log (pre-boost, raw scores -- for comparison against the boosted results):

```
[margin] query='아르바이트하면 문제되나요' top1=0.0008 top2=0.0002 margin=0.0006
[margin] query='저 알바 좀 오래 해도 되나요' top1=0.0004 top2=0.0001 margin=0.0003
```

The raw top1 scores (0.0008, 0.0004) are both far below Art. 22's post-boost scores
(0.3002, 0.3004) -- i.e., without the anchor match, an unrelated article would still be
sitting at top1. This confirms at the raw-log level that `_apply_anchor_boost` is what
actually flipped the ranking for this case.

### Regression check

Re-ran the existing anchor cases plus the postponement/permanent-resident family of
queries on the same server -- everything matched the prior record down to the score, no
regressions.

| Question | anchor_lookups | top1 | Matches prior record? |
|---|---|---|---|
| Leave of absence while studying abroad -- does my postponement get cancelled? | Art. 27 | Art. 27③ (0.5618) | ✅ |
| Withdrew from a foreign university -- what happens to my service obligation? | Art. 27 | Art. 27③ (0.3014) | ✅ |
| What if I just don't go back to Korea? | Art. 70, 94 | Art. 94 (0.3044) | ✅ |
| I'm a permanent resident -- until when can I avoid enlisting? | `[]` | Table 3 (0.3092) | ✅ |

### Conclusion

Issue A resolved. Confirmed `_apply_anchor_boost` correctly fires for the Art. 22 case via
the raw-vs-boosted score comparison, and all 4 pre-existing anchor cases show no
regression. Additionally found a minor gap where topic_tags doesn't catch the "알바"
synonym, but since it has no effect on retrieval accuracy, it was left out of this fix's
scope.

## Issue B fix: the `low_confidence` flag wasn't shown in the frontend at all (2026-07-31)

### Symptom

`routes/query.py` correctly includes a `low_confidence_notice` message (prompting the user
to rephrase) in the response JSON whenever `low_confidence: true`, but
`frontend/prototype.html`'s `render(data)` function never referenced either field, so
nothing showed up on screen. As a result, even noise-level results (e.g. raw score 0.0007)
looked like confident, settled answers.

### Fix

Two changes to `frontend/prototype.html`:

1. Added a new `.low-conf` class in `<style>` -- given a distinct blue/navy tone with a
   left accent border, visually distinct from the existing `.oos` (out-of-scope notice,
   orange tone).
2. In `render(data)`, right before rendering the `data.results` cards (after both the
   out-of-scope branch and the empty-results branch), insert an escaped `.low-conf` notice
   box whenever `data.low_confidence && data.low_confidence_notice`.

```javascript
if (data.low_confidence && data.low_confidence_notice) {
  html += `<div class="low-conf">${escapeHtml(data.low_confidence_notice)}</div>`;
}
```

### Re-verification

This environment has no headless-browser binary available (no Chrome/Chromium/Playwright
installed; `safaridriver` exists but selenium doesn't), so instead of a GUI screenshot, the
actual `<script>` content was extracted verbatim from `prototype.html` and run inside a
Node `vm` context, with `document` replaced by a minimal stub that only implements the
browser's `textContent -> innerHTML` text-node serialization rules (`&`->`&amp;`,
`<`->`&lt;`, `>`->`&gt;`, quotes left un-escaped -- matching real browser behavior). This
ran `render()`/`escapeHtml()` exactly as written. Real API responses were captured from the
live server (clean-restarted, pid 69673/69710) and fed in as-is.

1. **Low-confidence case**: since Issue A's fix means "Is it a problem if I have a
   part-time job?" is no longer low-confidence, tested instead with "I have dual
   citizenship -- would working in Korea count against me?" (이중국적인데 한국에서
   취업하면 불이익 있나요).
   - Actual server response: `low_confidence: true`, `low_confidence_notice`: "The
     search result's confidence is low. Please rephrase your question or make it
     more specific and try again. The results below are for reference only."
   - `render()` output: `output.innerHTML` contained a generated
     `<div class="low-conf">` box, with the notice text unchanged (no special
     characters, so escaping made no visible difference). ✅
2. **High-confidence regression case**: "I'm a public-service worker (사회복무요원) --
   can I travel abroad?"
   - Actual server response: `low_confidence: false`, top1 = Enforcement Decree
     Art. 135 (0.9882)
   - `render()` output: no `.low-conf` box -- confirmed no false positive. ✅
3. **XSS-escaping check**: cloned an actual response and swapped
   `low_confidence_notice` for
   `<script>alert(1)</script> "onload=alert(2)" & <img src=x onerror=alert(3)>`,
   then re-ran.
   - Result: `&lt;script&gt;alert(1)&lt;/script&gt; "onload=alert(2)" &amp;
     &lt;img src=x onerror=alert(3)&gt;` -- confirmed `<`/`>`/`&` are all escaped,
     so the payload can't be interpreted as a tag. (Quotes don't need escaping
     inside a text node -- it's not an attribute context, so it's not an XSS
     vector; this is the same `escapeHtml()` function already used to render
     `.oos`, so the security properties are identical.)

### Conclusion

Issue B resolved. Confirmed `low_confidence`/`low_confidence_notice` render correctly by
actually executing the real code, confirmed no false positive on the high-confidence case,
and confirmed malicious payloads are safely escaped. One caveat: this was verified via
Node `vm` + a DOM stub rather than a real headless-browser GUI -- if Chrome/Playwright
becomes available in this environment, a screenshot-based re-verification is recommended.

## Stage 5: Gemini Flash answer-generation verification (2026-07-31)

### Background

After switching from the Anthropic Claude API to the Google Gemini API (rationale in
`docs/devlog-en.md`), implemented and verified a new feature: turning retrieved articles +
the question into a grounded, citation-bearing answer. Judgment (which articles are
relevant, how confident the retrieval is) is entirely owned by the rule-based pipeline
built through Stage 4 already -- this feature's only responsibility is synthesizing an
answer from text that's already been retrieved.

### Steps 1-2: cost-safety guardrails + the `generate_answer()` module

- `backend/generation/gemini_client.py`: a hardcoded 6-model whitelist
  (`gemini-3.6-flash`, `gemini-3.5-flash`, `gemini-3.5-flash-lite`,
  `gemini-3.1-flash-lite`, `gemini-2.5-flash`, `gemini-2.0-flash`) -- any model name
  outside the whitelist raises `DisallowedModelError` and blocks the API call entirely.
  `vertexai=False` is explicit (Google AI Studio path only, never the
  billing-enabled Vertex AI path). Only 429 (rate-limit/quota) errors get retried, up to
  2 times with exponential backoff; every other error surfaces immediately. A data-privacy
  note (free-tier prompts may be used by Google to improve their products) is left as a
  code comment.
- `backend/generation/answer.py`: `generate_answer(question, results)` -- a
  system_instruction that forces grounding ("don't guess or invent anything not in the
  provided articles," explicitly say "this can't be determined from the provided articles
  alone" when information is insufficient) plus a forced citation format ("Per Article
  N Paragraph M of [Act]..."). Returns `None` if `results` is empty (a defensive guard).
  **The `low_confidence` branch is NOT this function's job -- it belongs to
  `routes/query.py`.** `generate_answer()` was deliberately designed to never receive the
  `low_confidence` flag at all, so it's structurally impossible for it to dress up a
  low-confidence retrieval as a confident-sounding answer.

**Empirical finding -- some whitelisted models don't actually work.** Calling the spec's
originally-intended default, `gemini-3.5-flash`, kept returning 503 (high demand) across 3
retries spaced apart in time. Smoke-testing all 6 whitelisted models directly found:
- `gemini-2.5-flash` -> 404 ("no longer available to new users" -- effectively a dead
  model)
- `gemini-2.0-flash` -> 429 with a hard **0** free-tier quota (completely blocked on this
  account's free tier)
- `gemini-3.5-flash` -> persistent 503s (hard to call this "temporary" high demand)
- `gemini-3.6-flash` / `gemini-3.5-flash-lite` / `gemini-3.1-flash-lite` -> all worked

**Changed the default model to `gemini-3.6-flash`** (the whitelist itself stays at all 6
entries -- the safety boundary isn't compromised by 2 of them being dead on this
particular account, so there's no reason to remove them from the whitelist). This
empirical finding is documented with the date in a `gemini_client.py` comment.

### Step 3: `/api/query` integration verification

Wired `routes/query.py` to call `generate_answer()` only when `low_confidence: false` and
`results` is non-empty, wrapped in `try/except` so a failure returns `answer: null`,
`answer_error: "..."` instead of a 500 (the request never dies).

**Clean restart check** (`pkill -9 -f "app.py"` -> `python3 app.py`):
```
[startup] pid=91261 law_chunks.json: 270 chunks, mtime=1783695412 | POST_SERVICE_KEYWORDS: 12 keywords, hash=2dc6d7a4
 * Restarting with stat
[startup] pid=91303 law_chunks.json: 270 chunks, mtime=1783695412 | POST_SERVICE_KEYWORDS: 12 keywords, hash=2dc6d7a4
```

**Graceful-failure verification -- confirmed both a real occurrence and a simulated one.**
1. Real occurrence: during testing, a `gemini-3.6-flash` call actually returned a real 503.
   Server log: `[answer_error] query='사회복무요원인데 해외 갈 수 있나요'
   error=ServerError("503 UNAVAILABLE...")`. The HTTP response was still 200, `results`
   came back normally, `answer: null`, and `answer_error` held the error message -- the
   request didn't die.
2. Simulated: forced `routes.query.generate_answer` to raise `RuntimeError` via
   `unittest.mock.patch`, then called the real `/api/query` route through Flask's
   `test_client()` -- got `HTTP 200`, all 5 `results` returned normally, and
   `answer_error: "RuntimeError: simulated Gemini API failure..."`. (This monkeypatch is
   for constructing a reproducible failure case, not the "standalone script replacing
   server verification" pattern earlier sessions ruled out -- it runs the exact same
   `routes/query.py` code the live server loaded, and the only thing being faked is the
   single external API call site, not any application logic.)

### Bug found and fixed: citation formatting for Table 3 (별표) articles

**Symptom**: answers that cited a Table 3 (overseas-emigration permit eligibility table)
chunk read awkwardly, e.g. "병역법 시행령 별표 3 **제별표3조** 제1항에 따르면..." ("Per
**Article 별표3** of Table 3 of the Enforcement Decree..."). Not a hallucination -- no
fact was invented -- but a formatting defect from mechanically forcing the citation-format
requirement ("Per Article N Paragraph M") onto something that isn't a numbered article.

**Root cause**: `_format_articles()` unconditionally applied the "제{article_no}조"
("Article {article_no}") template to every result, but a Table 3 chunk's `article_no`
field is the literal string `"별표3"` (not a number), producing the malformed "제별표3조."

**Fix**: when `article_no` starts with `"별표"`, skip the "Article N" template and format
as `{law_name} ({article_title}) 항목 {paragraph_no}` (`answer.py`). Also added an
instruction to the system prompt: "when the source is a Table (별표), cite it as '~
Enforcement Decree Table 3에 따르면' ('Per Table 3 of the ~ Enforcement Decree'), not as
'Article N'."

**Re-verification**: after a clean restart, all 3 queries that touch a Table 3 chunk
(#2/#3/#4 in the Stage 4 table below) now cite it correctly as "병역법 시행령 별표 3에
따르면..." ("Per Table 3 of the Enforcement Decree...").

### Step 4: Faithfulness spot check (5 queries, real HTTP requests against the
clean-restarted server)

| # | Question | low_confidence | Answer generated? | Citation accuracy |
|---|---|---|---|---|
| 1 | Leave of absence while studying abroad -- does my postponement get cancelled? | False | Yes | ✅ Cited articles (Art. 27③, Art. 125②) all present in `results`. Didn't guess about "leave of absence" specifically since the articles don't mention it |
| 2 | I'm a permanent resident -- until when can I avoid enlisting? | False | Yes | ✅ Cited articles (Table 3, Art. 149①-1, Art. 128①-1) all present in `results`. Declined to give a definitive answer, citing missing user-specific details |
| 3 | I'm a public-service worker -- can I travel abroad? | False (top1 0.9882) | Yes | ✅ Cited articles (Art. 135⑧, Table 3 x4) all present in `results`. No fabricated articles |
| 4 | My dad is a company-posted expat -- do I also get a postponement? | False | Yes | ✅ Cited articles (Table 3, Art. 149①-5, Art. 128①-2/②, Art. 60①-2) all present in `results`. Correctly applied **the expat-parent exception** in Table 3 (the "5+ years abroad" clause explicitly excludes cases where a parent is a company-posted expat) rather than misapplying the general rule |
| 5 | I have dual citizenship -- would working in Korea count against me? | **True** | **Skipped** (`answer: null`, `answer_error: null`) | ✅ `generate_answer()` was never invoked, as designed -- only `low_confidence_notice` came back |

Full answer text (final, post-Table-3-format-fix):

**#1**
> Per Article 27 Paragraph 3 of the Regulations on Overseas Travel of Military
> Conscripts, a district Military Manpower Administration office must revoke the permit
> and notify the person if a review of enrollment status finds that someone who received
> an overseas-travel permit for study-abroad purposes no longer meets the permit
> conditions -- however, whether a leave of absence specifically triggers cancellation of
> an enlistment postponement isn't specified, so this can't be determined from the
> provided articles alone.
>
> Per Article 125 Paragraph 2 of the Enforcement Decree, a person enrolled at a foreign
> university or graduate school who wants a postponement of enlistment etc. must submit a
> postponement application to the district Military Manpower Administration office --
> however, no provision addressing cancellation due to a leave of absence is presented.

**#2**
> Per Table 3 of the Enforcement Decree, a person subject to reserve-forces/social-service/
> alternative-service call-up who has obtained permanent residency and has continuously
> resided in that country for 3+ years may receive an overseas-travel permit or extension
> valid up to age 37.
>
> Per Article 149 Paragraph 1 Item 1 of the Enforcement Decree, a service obligor who has
> resided abroad since before age 18 is deemed to have received an overseas-travel permit
> valid up to age 37 if they or a parent obtained permanent residency abroad (excluding
> conditional permanent residency) before age 25 and has continued residing abroad.
>
> Per Article 128 Paragraph 1 Item 1 of the Enforcement Decree, a person who received an
> overseas-travel permit or extension and is residing abroad is deemed to have their
> pre-enlistment physical/re-physical or enlistment postponed.
>
> Whether the questioner meets the specific conditions under Article 149 Paragraph 1 and
> Table 3 of the Enforcement Decree (timing of obtaining permanent residency, length of
> residence, etc.) can't be determined from the provided articles alone.

**#3**
> Per Article 135 Paragraph 8 of the Enforcement Decree, if a person serving as a
> public-service worker emigrates abroad with their family, the district Military Manpower
> Administration office releases them from their public-service call-up.
>
> Per Table 3 of the Enforcement Decree, a public-service call-up subject who has filed an
> overseas-emigration report may receive an overseas-travel permit or extension only once,
> within a 3-year scope.
>
> Per Table 3 of the Enforcement Decree, a public-service call-up subject who filed an
> overseas-emigration report and has continuously resided in the destination country
> (including the pre-departure waiting period) for 3+ years may receive an overseas-travel
> permit or extension valid up to age 37.
>
> Per Table 3 of the Enforcement Decree, a public-service call-up subject who has
> continuously resided abroad with a parent for 5+ years may receive an overseas-travel
> permit or extension valid up to age 37.
>
> Per Table 3 of the Enforcement Decree, a public-service call-up subject who has obtained
> conditional or temporary permanent residency in a foreign country and resides there may
> receive an overseas-travel permit or extension valid up to 6 months past the conditional/
> temporary permanent-residency's validity period.

**#4**
> Per Table 3 of the Enforcement Decree, if a parent is a company-posted expat, the
> family is excluded from the overseas-travel permit/extension eligibility even if they've
> continuously resided abroad with that parent for 5+ years.
>
> Per Article 149 Paragraph 1 Item 5 of the Enforcement Decree, a person is deemed to have
> received an overseas-travel permit valid up to age 37 only if they left Korea before age
> 18 with a parent who is *not* a company-posted expat and has continued residing abroad
> with that parent.
>
> Per Article 128 Paragraph 1 Item 2 of the Enforcement Decree, a person under 25 who
> hasn't been called up as a reserve-forces member, alternative-service member, or
> substitute-service member and is residing or staying abroad is deemed to have their
> pre-enlistment physical/re-physical or enlistment postponed.
>
> Per Article 128 Paragraph 2 of the Enforcement Decree, a person born abroad, or who has
> filed an overseas-emigration report under the Overseas Emigration Act and resides
> abroad, may have their pre-enlistment physical/re-physical or enlistment postponed based
> on confirmation from the head of the relevant diplomatic mission.
>
> Per Article 60 Paragraph 1 Item 2 of the Military Service Act, a district Military
> Manpower Administration office may postpone the pre-enlistment physical/re-physical for
> a person residing or staying abroad.
>
> Per Table 3 of the Enforcement Decree, Article 128 Paragraphs 1 and 2, Article 149
> Paragraph 1 of the Enforcement Decree, and Article 60 Paragraph 1 of the Military Service
> Act, whether the questioner's postponement applies can't be conclusively determined from
> the provided articles alone, given missing specifics (age, whether born abroad, whether
> an overseas-emigration report was filed, etc.).

**#5**: since `low_confidence: true`, `generate_answer()` was never called. Only
`answer: null` and `low_confidence_notice` came back, as designed.

### Conclusion

All 5 spot-check queries had citations that exactly matched articles actually present in
`results`, and no answer added a fact outside the provided text -- in particular, #1 (leave
of absence) and #2/#4 (user-specific eligibility details) were each honestly answered with
"can't be determined from the provided articles alone" wherever the articles didn't
explicitly cover the specific scenario asked about. #4 correctly applied Table 3's
expat-parent exception, handling that edge case correctly rather than defaulting to the
general rule. #5 confirmed the `low_confidence` gate does its job -- it blocks answer
generation entirely, by design.

Two things were found and fixed along the way: (1) the spec's default model,
`gemini-3.5-flash`, doesn't actually work on this account, so the default was switched to
`gemini-3.6-flash`; 2 of the whitelisted models (`gemini-2.5-flash`, `gemini-2.0-flash`)
turned out to be effectively dead on this account too -- the whitelist (the safety
boundary) was kept intact, only the actual default was swapped for one that works. (2) A
citation-formatting bug for Table 3 chunks was found, fixed, and re-verified.

Stage 5 (answer generation) is now implemented, integrated, and faithfulness-verified.

## Stage 6: formalizing the Flask API -- session profile + feedback (2026-08-01)

### Background

Added a login-free, lightweight session profile (`/api/profile`) and feedback
collection (`/api/feedback`). The session profile has zero involvement in retrieval
accuracy logic -- it only affects `intent["user_type_tags"]` (used for the OOS message
and the frontend's intent tags). In other words, this change is a UX improvement (no need
to re-type your user type every time), not a retrieval-accuracy improvement. So the
regression check here is framed as "did the retrieval top1/score stay the same," not "did
user_type get applied."

### New/modified files

- New: `backend/routes/profile.py` (`POST /api/profile`, `GET /api/profile/<id>`)
- New: `backend/routes/feedback.py` (`POST /api/feedback`)
- Modified: `backend/classifier/predict.py` -- `classify(question, session_user_type=None)`.
  Any user type explicitly detected in the question text always wins; the session profile
  is only used as an `or` fallback when `_detect_user_types(search_space)` comes back
  empty. All three branches (post-service / OOS / normal retrieval) apply the same
  priority rule.
- Modified: `backend/routes/query.py` -- parses `session_id`, adds a
  `_session_user_type()` helper (wrapped in try/except so a Mongo failure doesn't take
  down the query itself, logged as `[profile_lookup_error]`), and passes
  `session_user_type` into `classify()`. Nothing else -- retrieval, reranking, boosting,
  and answer generation logic are untouched.
- Modified: `backend/app.py` -- registers the `profile_bp`/`feedback_bp` blueprints.

### Clean restart check

```
[startup] pid=9556 law_chunks.json: 270 chunks, mtime=1783695412 | POST_SERVICE_KEYWORDS: 12 keywords, hash=2dc6d7a4
 * Restarting with stat
[startup] pid=9590 law_chunks.json: 270 chunks, mtime=1783695412 | POST_SERVICE_KEYWORDS: 12 keywords, hash=2dc6d7a4
```

`hash=2dc6d7a4`, 270 chunks -- identical to prior sessions, as expected since
`law_chunks.json`/`POST_SERVICE_KEYWORDS` weren't touched by this work.

### `/api/profile` basic behavior

| Case | Request | Result |
|---|---|---|
| Valid upsert | `POST {"session_id":"test-1","user_type":"영주권자"}` | ✅ HTTP 200, `user_type: "영주권자"` |
| Read-back | `GET /api/profile/test-1` | ✅ HTTP 200, returns the just-saved value |
| Invalid user_type | `POST {"session_id":"test-bad","user_type":"군인"}` | ✅ HTTP 400, error lists valid values |
| Missing session_id | `POST {"user_type":"영주권자"}` | ✅ HTTP 400 |

### `/api/query` + session-profile integration (4 cases, real HTTP)

| # | session_id (profile) | Question | Expected | Actual `user_type_tags` | Verdict |
|---|---|---|---|---|---|
| a | test-1 (permanent resident) | How do I get an overseas-travel permit? (no user type stated) | Session profile applies | `['영주권자']` | ✅ PASS |
| b | test-1 (permanent resident) | I'm studying abroad -- what happens if I take a leave of absence? (states international student) | Question wins over session | `['유학생']` | ✅ PASS |
| c | none | How do I get an overseas-travel permit? | Prior default behavior (`["전체"]`) preserved | `['전체']` | ✅ PASS |
| d | test-2 (2nd-gen overseas Korean) | I want to apply for KATUSA (OOS branch) | Session profile applies even in the OOS branch + `related_scope_info` populated | `['재외동포2세']`, `related_scope_info` has 9 items, guidance message mentions "재외동포2세" | ✅ PASS |

### Regression check -- retrieval results themselves must be unchanged

Re-ran 3 existing anchor test queries without a `session_id` -- every one matched the
prior record down to the exact score, no regressions. (Expected, since neither
`classify()`'s `topic_tags`/`anchor_lookups` computation nor `routes/query.py`'s retrieval
ranking logic was touched -- but confirmed empirically anyway.)

| Question | top1 | Prior record | This run | Match? |
|---|---|---|---|---|
| Leave of absence while studying abroad -- does my postponement get cancelled? | Art. 27③ | 0.5618 | 0.5618 | ✅ |
| Is it a problem if I have a part-time job? | Art. 22 | 0.3002 | 0.3002 | ✅ |
| I'm a permanent resident -- until when can I avoid enlisting? | Table 3 | 0.3092 | 0.3092 | ✅ |

### `/api/feedback` verification

| Case | Request | Result |
|---|---|---|
| Valid submission | `POST {"session_id":"test-1","question":"...","rating":"up","comment":"도움됐어요"}` | ✅ HTTP 201, returns `id` |
| Invalid rating | `POST {"question":"테스트","rating":"meh"}` | ✅ HTTP 400 |
| Missing question | `POST {"rating":"down"}` | ✅ HTTP 400 |

Confirmed the document actually landed in MongoDB's `feedback` collection:
```
{'_id': ObjectId('6a6e62ea61beb09f0e871244'), 'session_id': 'test-1',
 'question': '국외여행허가 어떻게 받나요?', 'rating': 'up', 'comment': '도움됐어요',
 'results': None, 'answer': None, 'created_at': datetime.datetime(2026, 8, 1, 21, 19, 38, 734000)}
```
The `profiles` collection also showed `test-1`/`test-2` correctly upserted. (These test
documents were left in the database rather than cleaned up -- ask if you'd like them
deleted.)

### Conclusion

All 5 files (2 new + 3 modified) applied, clean restart confirmed, profile/feedback API
basic behavior passed all 4+3 cases, session-profile integration passed all 4 cases (the
question's explicit signal always wins over the session profile, as designed), and all 3
retrieval-ranking regression queries matched down to the score. No deployment sync issue
or regression found.

## Stage 6's last piece: RAGAS quantitative evaluation (2026-08-01)

### Background

Wired RAGAS quantitative evaluation onto the retrieval+generation pipeline. Refactored
`routes/query.py` so the `/api/query` view body is a pure function,
`answer_question(question, session_user_type=None)`, and had RAGAS call that function
directly (no HTTP) so it exercises the literal production code path -- same principle
behind the earlier `answer_error` monkeypatch test.

RAGAS's LLM judge does NOT use `langchain_google_genai.ChatGoogleGenerativeAI` directly --
`generation/ragas_llm.py`'s `WhitelistedGeminiChatModel` internally routes every call
through `gemini_client.generate()`, so judge calls get this project's "absolutely no
billing" guardrails (model whitelist, 429 backoff) too. Embeddings (for answer_relevancy)
run on local BGE-m3 (`pipeline/embedder.py`) instead of a Gemini embedding API, so that
metric makes zero network calls.

### New/modified files

- New: `backend/generation/ragas_llm.py`, `backend/evaluation/ragas_embeddings.py`,
  `backend/evaluation/ragas_eval.py`, `backend/data/eval/ragas_eval_set.json`
- Modified: `backend/routes/query.py` -- extracted `answer_question()` as a pure function
  (a no-logic-change refactor), `backend/requirements.txt` -- added `langchain-core` and
  pinned `langchain-community==0.3.31` (reason below)

### Refactor regression check (required before running RAGAS)

Clean restart (`pkill -9 -f "app.py"` -> restart, confirmed `hash=2dc6d7a4`/270 chunks
unchanged) followed by re-running 3 anchor queries over real HTTP -- confirmed the
`answer_question()` extraction changed nothing about `/api/query`'s behavior.

| Question | top1 | Prior record | This run |
|---|---|---|---|
| Leave of absence while studying abroad -- does my postponement get cancelled? | Art. 27③ | 0.5618 | 0.5618 ✅ |
| Is it a problem if I have a part-time job? | Art. 22 | 0.3002 | 0.3002 ✅ |
| I'm a permanent resident -- until when can I avoid enlisting? | Table 3 | 0.3092 | 0.3092 ✅ |

### Dependency conflict found during install

`ragas==0.4.3` (the latest release pip resolved) unconditionally imports
`langchain_community.chat_models.vertexai.ChatVertexAI` at load time (an optional Vertex
AI integration this project doesn't use) -- but that submodule doesn't exist at all in
the latest `langchain-community` release (0.4.2, mid-"sunset," migrating individual
provider integrations out into standalone packages), so `import ragas` failed outright.
Fixed by pinning `langchain-community` to `0.3.31`, the last release that still has that
submodule (`langchain-core` stays at 1.5.3, within its compatible range). Pinned in
`requirements.txt` with the reason documented -- re-check this pin if ragas is ever
upgraded.

### Discovered while running -- `gemini-3.6-flash`'s real free-tier daily cap is 20

Running `python3 evaluation/ragas_eval.py` as originally planned: only 1 of 12
reference-free evaluations succeeded before the rest failed with `TimeoutError`, and the
reference-based pass hit a 429 on its very first job:

```
ClientError(429 RESOURCE_EXHAUSTED. ... quotaId: 'GenerateRequestsPerDayPerProjectPerModel-FreeTier',
quotaDimensions: {'model': 'gemini-3.6-flash'}, quotaValue: '20' ...)
```

This account's actual daily cap for `gemini-3.6-flash` turned out to be **20 requests**
-- far below the "~1000-1500/day" assumed when Stage 5 was designed. Today's session had
already used a good chunk of that from Stage 6's profile-integration tests and anchor
regression checks before RAGAS even started; adding the pipeline's 6 generation calls plus
roughly 12-20 judge calls on top exhausted it almost immediately. A direct re-check
confirmed it was already 429 by that point.

**Two fixes landed in code** (`evaluation/ragas_eval.py`):
1. **Separated the judge model from the generation model** -- added a `JUDGE_MODEL`
   constant pointing the judge at `gemini-3.5-flash-lite` (a different whitelisted model,
   its own quota bucket), so generation (`generate_answer()`) and judging no longer
   compete for the same model's daily quota.
2. **Serialized RAGAS's concurrency** -- RAGAS's defaults (`max_workers=16`,
   `max_retries=10`) fire far more concurrent requests than the free tier's ~10-15 RPM can
   absorb; a handful of real 429s turned into a wall of `TimeoutError`s once RAGAS's own
   retry-of-retries piled on top of `gemini_client.py`'s own capped backoff. Fixed with
   `RunConfig(max_workers=1, max_retries=1)`.

### Today-only workaround -- generation also had to switch models (important, read together with the above)

Even with those fixes, `gemini-3.6-flash` (Stage 5's actual production default) was
already at its daily cap for today (confirmed 429 on a direct re-check), so to get real
numbers today, `generation.answer.DEFAULT_MODEL` was temporarily bound to
`gemini-3.5-flash-lite` via `unittest.mock.patch`, **for this one run only**. **The
codebase itself was not touched** -- `generation/gemini_client.py`'s `DEFAULT_MODEL` is
still `gemini-3.6-flash`, and calling `/api/query` right now still generates answers with
`gemini-3.6-flash`.

**In other words, the numbers below reflect the quality of `gemini-3.5-flash-lite`'s
generation, not the quality of the model actually deployed in Stage 5
(`gemini-3.6-flash`).** Retrieval is 100% the real production path; only the generation
model was swapped, and only because of today's quota situation -- read the numbers with
that in mind.

### Results

`_run_pipeline`: 6 of 8 questions produced an answer. 2 were skipped by design because
`low_confidence=True` (`generate_answer()` was never called) -- "I have dual citizenship,
would working in Korea count against me?" (raw score 0.0007, a question with no
ground_truth to begin with, included specifically to verify the skip logic) and "I'm a
PhD student -- am I recognized as an international student too?" (raw top1 0.0245, matches
the same low-confidence result from yesterday's new-query verification session --
confirms reproducibility).

**Reference-free (6 questions, faithfulness + answer_relevancy):**

| Metric | Score |
|---|---|
| faithfulness | 0.2778 |
| answer_relevancy | 0.2670 |

**Reference-based (4 ground_truth-labeled questions, context_precision + context_recall):**

| Metric | Score |
|---|---|
| context_precision (LLMContextPrecisionWithReference) | NaN (4 of 8 jobs hit a 180s timeout -- every failure was on this metric specifically. Not "a low score" -- no score was ever produced) |
| context_recall | 0.7917 |

### Limitations that must be read alongside these numbers (not glossing over them to look cleaner)

1. **The 4 ground_truth answers aren't independent references.** They're the exact
   Gemini responses already citation-verified in yesterday's (07-31) Stage 5 faithfulness
   spot check, reused as-is rather than freshly hand-written gold answers -- there's a
   circularity here. In particular, context_recall (0.7917) measures how well the
   retrieved articles cover the ground_truth, and that ground_truth was itself generated
   from the same retrieval yesterday, which could be inflating the score relative to a
   truly independent reference.
2. **Today's run used a substituted generation model** (see the section above) -- the
   faithfulness/answer_relevancy scores around 0.28 grade `gemini-3.5-flash-lite`'s
   answers, not `gemini-3.6-flash`'s.
3. **A faithfulness of 0.28 doesn't square with yesterday's manual spot check (5/5
   citations accurate, nothing fabricated).** The root cause wasn't pinned down here --
   candidate hypotheses: (a) RAGAS's Faithfulness metric decomposes the answer into
   atomic claims and checks each against `retrieved_contexts`; the lite judge model may
   have been overly strict (or simply wrong) about matching formal statutory phrasing
   against the answer's paraphrases, or (b) the lite generation model's answers may have
   genuinely had weaker grounding than the `gemini-3.6-flash` answers spot-checked
   yesterday. Neither is ruled out. Without further investigation, this number shouldn't
   be read as "the pipeline hallucinates 73% of the time" -- yesterday's manual
   verification (which cross-checked actual article numbers) is the more trustworthy
   signal right now.
4. **context_precision failed to compute -- it isn't a bad score.** NaN means all 4
   scoring attempts timed out, not that precision was measured and found lacking.

### Conclusion

All 6 files applied, no refactor regression, and the RAGAS pipeline itself ran end-to-end
and produced real numbers. That said, four caveats -- (1) `gemini-3.6-flash`'s daily quota
turned out to be a very low 20, (2) today's run used a substituted generation model, (3)
the ground_truth circularity, (4) context_precision never got scored -- mean today's
numbers shouldn't be treated as this pipeline's settled quality metrics yet. The code
fixes (separated judge model, serialized RunConfig) are in place and unchanged, so once
`gemini-3.6-flash`'s quota resets (some day after today), re-running
`python3 evaluation/ragas_eval.py` as-is (no model patch) will produce numbers against the
actual production model.