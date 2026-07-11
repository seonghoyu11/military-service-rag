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
