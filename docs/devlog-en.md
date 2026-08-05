# DutyCompass - Developer Notes: RAG Chatbot for Overseas Korean Military Service Obligors

A RAG-based chatbot guiding overseas military-service obligors — permanent
residents, international students, dual nationals, second-generation
overseas Koreans — through Korea's military service administrative
procedures. The goal was to get accuracy from a structured pipeline (parse →
embed → hybrid retrieval → rerank → classify → generate) rather than just
prompting an LLM directly. Scope: from when a service obligation arises up
to enlistment.

This document walks through what was built at each stage, what actually went
wrong, and how it was diagnosed, in the order it happened. The honest
throughline isn't "built it perfectly the first time" — it's "build a
prototype, actually use it, find problems, diagnose them with data, fix
them," repeated.

---

## Table of Contents

- [Stage 1: Law-parsing pipeline](#stage-1-law-parsing-pipeline)
- [Stage 2: Embedding model comparison + MongoDB ingestion](#stage-2-embedding-model-comparison--mongodb-ingestion)
- [Stage 3: Hybrid retrieval + reranker](#stage-3-hybrid-retrieval--reranker)
- [Stage 4: Intent classifier](#stage-4-intent-classifier)
- [Building a prototype, actually using it, and finding what was broken](#building-a-prototype-actually-using-it-and-finding-what-was-broken)
  - [Finding 1: search results came back with the opposite meaning](#finding-1-search-results-came-back-with-the-opposite-meaning)
  - [Finding 2: fixing the tags didn't change the search results](#finding-2-fixing-the-tags-didnt-change-the-search-results)
  - [Finding 3: article boundaries were silently broken](#finding-3-article-boundaries-were-silently-broken)
  - [Finding 4: the right answer exists in the corpus, but retrieval can't find it](#finding-4-the-right-answer-exists-in-the-corpus-but-retrieval-cant-find-it)
  - [Finding 5: real answers and noise scores can invert](#finding-5-real-answers-and-noise-scores-can-invert)
  - [Finding 6: a scope-detection blind spot](#finding-6-a-scope-detection-blind-spot)
  - [Finding 7: the code was right, but the server's response wasn't](#finding-7-the-code-was-right-but-the-servers-response-wasnt)
- [What this taught](#what-this-taught)
- [Waiting on Stage 5: a threshold experiment and one more evasive-phrasing gap (2026-07-15)](#waiting-on-stage-5-a-threshold-experiment-and-one-more-evasive-phrasing-gap-2026-07-15)
- [Stage 5 LLM switch: Anthropic Claude → Google Gemini (2026-07-31)](#stage-5-llm-switch-anthropic-claude--google-gemini-2026-07-31)
- [Stage 6: formalizing the Flask API + RAGAS quantitative evaluation (2026-08-01)](#stage-6-formalizing-the-flask-api--ragas-quantitative-evaluation-2026-08-01)
- [Progress summary](#progress-summary)
- [What's left](#whats-left)

## Stage 1: Law-parsing pipeline

Parsed 6 law PDFs (the Military Service Act, its Enforcement Decree,
Enforcement Rule, an MMA directive, an MND directive, and Attached Table 3)
into 272 chunks while preserving article/paragraph structure. The rule was
zero paraphrasing — keep the original text verbatim. Attached Table 3 (a
table) was converted row-by-row into natural-language sentences.

**Three real bugs found during sample verification:**
- The `refers_to` (cross-reference) field was mistaking a chunk's own
  article number — embedded in its own header — for a cross-reference. 224
  of 270 chunks (83%) were affected. Fixed by extracting references only
  from the body text, before the header gets prepended.
- PDF extraction split words across a mid-syllable line break ("사\n람" →
  "사람") — 582 occurrences. Fixed with a function
  (`join_wrapped_lines`) that joins a "Hangul + newline + Hangul" pattern —
  which later turns out to cause a different bug downstream (see below).
- Attached Table 3's table-cell extraction inserted stray whitespace into
  category labels ("병역준비 역, 사회복 무요원..."). Fixed by comparing
  against a whitespace-stripped copy.

## Stage 2: Embedding model comparison + MongoDB ingestion

Compared BGE-m3, multilingual-e5-large, and KoE5 using a hand-built 15-
question test set (a mix of real-case-style scenarios and MMA-FAQ-style
phrasing, including one deliberate out-of-scope negative test about
KATUSA), measuring Recall@K and MRR.

**Result: BGE-m3 selected.** Perfect Recall@10 (14/14), and — more
importantly — the clearest separation between similarity scores for
genuinely relevant vs. out-of-scope questions. multilingual-e5-large gave
the out-of-scope question a top-1 score of 0.801, barely below its average
for real matches, which would make a raw-score "no relevant article found"
threshold unreliable. Interestingly, the Korean-specialized model (KoE5)
scored worst of the three — at this scale (~560M params), retrieval-
specific training and data quality seem to matter more than language
specialization. Embedded all 272 chunks with BGE-m3 and loaded them into a
MongoDB Atlas Vector Search index.

## Stage 3: Hybrid retrieval + reranker

Combined BM25 (Korean morphological tokenization via `kiwipiepy`, stripping
particles/endings) with Dense (BGE-m3) scores via min-max normalization and
a weighted sum. A grid search settled on `alpha=0.3` (70% BM25, 30% dense) —
perfect Recall@5/10, MRR 0.929.

One interesting finding here: **BM25 alone already hit perfect Recall@5/10**
— this domain (military-service-law Q&A) turns out to have a lot of
vocabulary overlap between how users phrase questions and the statute text
itself. And BM25 correctly caught a question all three embedding models had
missed in Stage 2 ("what are the consequences of repeatedly evading
departure without a permit?") — the correct answer literally contains the
word "evade," which the dense models somehow missed anyway. That was
concrete evidence the hybrid design was actually necessary, not just a
nice-to-have.

The reranker (bge-reranker-v2-m3) didn't move Recall/MRR much on this small
test set, but was decisively better for **score interpretability** — real
matches scored 0.77–0.999, the out-of-scope question scored 0.000, giving a
genuine confidence signal for "no relevant article found."

## Stage 4: Intent classifier

Started rule-based (keyword matching), designed to be swapped for a
lightweight trained classifier once labeled query data accumulates.
Classifies by user type (permanent resident / international student / dual
national / 2nd-gen overseas Korean) × topic (postponement, permit
revocation, for-profit-activity restriction, etc.).

**An important scope decision made here:** KATUSA and language-soldier
programs are technically "recruitment before enlistment," so they fall
inside the stated scope — but their actual eligibility criteria (TOEIC score
cutoffs, etc.) aren't set by statute; they come from an annual MMA
recruitment notice that changes every year, so baking them into the corpus
would go stale almost immediately. Properly including the relevant
directive would also pull in a long chain of cross-referenced provisions,
making the scope balloon indefinitely. So they were deliberately excluded
from the dataset. Instead, the intent classifier detects KATUSA/language-
soldier keywords and points to the actual current-year MMA recruitment-
notice pages (different pages for each program), and — when a covered user
type is also mentioned — steers toward genuinely answerable adjacent
information already in scope (the voluntary-early-enlistment program, Art.
24).

---

## Building a prototype, actually using it, and finding what was broken

This is where most of the real learning happened. A Flask API (`app.py`,
`routes/query.py`) plus a plain HTML/JS prototype (`frontend/prototype.html`)
were built quickly, without waiting for Claude API integration, just to see
the "classify → retrieve → rerank" pipeline working end to end. Feeding it
real questions kept surfacing problems that code review alone would never
have caught.

### Finding 1: search results came back with the opposite meaning

Asking "I'm a permanent resident, how do I get an enlistment postponement?"
returned, as the top result, an article about **cancelling** a granted
postponement (the voluntary-early-enlistment program) — the exact opposite
of what was asked. Diagnosis:
- An article's own title contained the word "cancellation" (e.g., "overseas
  travel permit issuance **and cancellation**"), so every paragraph of that
  article was getting falsely tagged as co-occurring "postponement" +
  "cancellation," regardless of that paragraph's actual content.
- More fundamentally: the intent classifier's tags were never wired into
  actual retrieval ranking at all — they were purely display metadata. No
  amount of tag refinement could have changed the search results by
  itself.

Split the "postponement" topic into two directions — "wants to get one" vs.
"wants to cancel one" — using a precise regex (matching "postponement...
cancellation" in close proximity, far narrower than plain co-occurrence of
the two words), then wired the tags into actual score adjustments in
`routes/query.py`: boost when the query's direction matches a candidate
chunk's direction, penalize on mismatch. Re-verification confirmed the
opposite-direction query ("I want to cancel my postponement") got correctly
boosted the other way.

### Finding 2: fixing the tags didn't change the search results

After Finding 1's fix, a related test still failed: "up to what age can I
avoid enlisting?" was classified under a generic "none" topic — none of the
"postponement" keywords matched at all, so the directional correction never
even triggered. This kept happening: colloquial phrasing diverges from
statute vocabulary in ways that are easy to miss — "until when," "up to
what age," "age limit" never say the word "postponement" at all, yet are
unambiguously postponement questions.

### Finding 3: article boundaries were silently broken

Opening the raw processed corpus directly turned up a chunk where three
separate articles (21, 22, 23) had been merged with zero boundary between
them — "...while enrolled[NO SPACE]Article 22 (scope of for-profit
activity)..." glued together with no space or line break at all. A full
scan of all 272 chunks found **16 chunks contaminated** this way.

Tracing the cause: **the line-wrap repair function built back in Stage 1
(`join_wrapped_lines`) was erasing legitimate line breaks at article
boundaries as a side effect.** The source PDF correctly had a line break
right where one article ended and the next began, but the blanket "Hangul +
newline + Hangul → join them" rule deleted it too, since both sides of that
particular break happened to be Hangul characters as well. Worth recording
as a case study: logic built to fix one bug quietly created a different bug
at a different layer, later. Added an exception to the line-join function
(don't join a newline immediately followed by an article-header pattern),
then re-parsed, re-tagged, re-embedded, and re-indexed the entire corpus
(272 → 270 chunks).

### Finding 4: the right answer exists in the corpus, but retrieval can't find it

"Does my postponement get cancelled if I take a leave of absence?" and
"what happens to my service obligation if I drop out of my foreign
university?" — the correct answer article never uses either word ("leave
of absence" or "drop out"); it says "if a review of enrollment status finds
the permit conditions no longer met." The "drop out" question's correct
answer ranked 168th out of 270 by BM25.

First tried force-including the correct article into the candidate pool
whenever those specific synonyms were detected — it still didn't surface in
the top 5. Digging further: **the cross-encoder reranker itself judged the
semantic connection as weak**, so even after getting into the candidate
pool, it was being cut before the final ranking step even ran. Candidate-
pool inclusion alone wasn't enough — the reranker needed to score the whole
pool (not a truncated slice), and an anchor match needed an explicit score
boost on top of that.

### Finding 5: real answers and noise scores can invert

Trying to implement a "low confidence" threshold, the actual score
distribution turned up something uncomfortable: **a genuinely correct
answer scored lower (0.0061) than an actual noise question (0.0147).**
Short, incomplete phrasing (a statement rather than a well-formed question)
tends to get scored low by the reranker regardless of relevance — which
means no single absolute threshold can cleanly separate real answers from
noise on this signal alone.

The call made here: implement it as an advisory flag rather than a hard
cutoff — show a "low confidence" notice below a threshold, but still return
the results. Accepting that the signal isn't clean, and choosing to
occasionally mis-flag a correct answer over hiding weak-but-real answers
outright.

### Finding 6: a scope-detection blind spot

Questions about the **post-discharge** period — "someone who already
served, then gets permanent residency again, what happens?" — didn't match
any KATUSA/language-soldier keyword, so noise-level search results
(relevance 0.05–0.16) surfaced with no fallback at all, looking like a
normal answer. Added a separate keyword set for post-service phrasing
("discharged," "completed service," "already went," etc.), routed to a
distinct message ("this chatbot only covers pre-enlistment procedures")
rather than the KATUSA-style recruitment-notice fallback.

### Finding 7: the code was right, but the server's response wasn't

After fixing Finding 6, live testing still showed the old behavior, even
though running the classifier code standalone gave the correct result. The
cause wasn't the code or the data — it was **process management**. Across
this session's many restarts, the server had been killed by port
(`lsof -ti:5001 | xargs kill -9`), but Flask's debug auto-reloader spawns a
parent watcher process plus a child worker process; killing only the child
bound to the port can leave the parent orphaned. A stale process still
holding old code was the one actually answering requests.

As a fix going forward, added a one-line startup fingerprint to the server
log — chunk count + file mtime for the parsed corpus, plus a short hash of
a specific keyword list — so a stale process shows up immediately in the
log instead of silently serving outdated behavior. Also switched the
restart habit from port-based killing to process-name-based killing.

---

## What this taught

- **Don't assume — scan.** More than once, the guessed root cause (a
  parsing edge case) turned out to be completely different from the actual
  one (a side effect of a different fix). A habit of running a regex scan
  over the whole corpus and confirming with a number kept paying off.
- **A perfect threshold might not exist.** When the data says so, admit it
  — an advisory signal instead of a hard cutoff is a legitimate answer, not
  a cop-out.
- **A fix at one layer can quietly break another layer.** The line-wrap
  repair function erasing article boundaries is the clearest example —
  text-preprocessing logic interacts in ways that aren't obvious until
  something downstream breaks.
- **Building a prototype and actually using it is the fastest QA there is.**
  Most of the bugs in this write-up were invisible to code review and only
  surfaced by feeding the system real questions.
- **Process/deployment management is also debugging surface.** A
  meaningful fraction of "the code is right but the result is wrong" cases
  turned out to be about which process was actually answering the request,
  not the code itself.

## Waiting on Stage 5: a threshold experiment and one more evasive-phrasing gap (2026-07-15)

With the Anthropic API key wait dragging on, used the downtime to close out a piece of
unfinished business from Finding 5 (threshold) and chase down a suspicious case that
turned up in stress testing.

**The margin (top1-top2) experiment.** Finding 5 concluded that a single absolute score
can't cleanly separate real answers from noise. The hypothesis: the *gap* between the
top-1 and top-2 scores might be a better signal — a real answer should win by a wide
margin, while noise results should all cluster together at similarly low scores. Added
margin logging to `routes/query.py` and measured it against the same 12 regression
queries. The result was a half-win: re-examining the original inversion case that
motivated this (real answer 0.0061 < noise 0.0147) by margin instead does put them back
in the right order (0.0008 > 0.0006) — but the gap is only 0.0002, far too thin to set a
production threshold on with just two noise samples. The strong true-positive cases were
already being caught fine by the existing absolute threshold, so margin bought nothing
extra there either. Left the code alone and kept only the logging in production to keep
collecting data — a reminder that "the hypothesis points the right way, but there isn't
enough data yet to act on it" is itself a legitimate conclusion.

**The evasive-phrasing gap.** A question like "I have citizenship elsewhere, can't I just
not go back to Korea?" was suspected of falling through to `topic_tags: ['일반']` with a
top-1 relevance of 0.0123 (effectively noise). Re-testing reproduced it, and the cause was
a familiar shape: phrases like "not go back" / "won't return" never use legal terms like
"evade" or "violation," so they matched neither the `제재` (sanctions) topic keywords nor
the BM25/dense candidate pool. Added the evasive-verb phrasing to
`TOPIC_KEYWORDS["제재"]`, and used the same forced-anchor pattern from the leave-of-
absence/drop-out case to wire it to Military Service Act Article 70 (the travel-permit
obligation itself) and Article 94 (the penalty for violating it). After the fix, top-1
became Article 94 (boosted score 0.30) and `low_confidence` correctly flipped to `False`.

A side finding along the way: questions the intent classifier flags `out_of_scope=True`
(KATUSA, post-discharge timing, etc.) never reach the reranker, so no margin gets logged
for them — worth remembering when collecting margin data going forward.

## Stage 5 LLM switch: Anthropic Claude → Google Gemini (2026-07-31)

The Claude API requires registering a payment method (prepaid credit) before it can be
used, which kept stalling the start of Stage 5. The Google Gemini API (Google AI Studio,
`GOOGLE_API_KEY`) offers a free tier usable without a card on file, so Stage 5's LLM was
switched to Gemini Flash.

This switch is low-risk because the "judgment" work in this project — user-type/intent
classification, article retrieval and ranking, confidence gating — is already fully owned
by the rule-based pipeline built through Stage 4. The LLM's only job is synthesizing the
retrieved article text into a natural-language answer with citations. Swapping the model
doesn't touch the accuracy-critical logic; only generation quality (fluency, citation
format compliance, grounding faithfulness) needed re-verification, which kept the
migration cost small.

The free tier comes with a new constraint — no billing may ever occur — so the code adds
guardrails: a hardcoded model whitelist (only `gemini-3.6-flash`/`gemini-3.5-flash`/
`gemini-3.5-flash-lite`/`gemini-3.1-flash-lite`/`gemini-2.5-flash`/`gemini-2.0-flash`,
six models total, Pro-tier models blocked), no Vertex AI code path (Google AI Studio
only), and a capped retry count instead of unbounded retries on rate-limit errors. The
default model was set to `gemini-3.6-flash` based on actually calling all six whitelisted
models (2 turned out to be effectively dead on this account -- 404/zero quota). Full
implementation and verification details are in the "Stage 5: Gemini Flash
answer-generation verification" section of `docs/eval_results-en.md`.

## Stage 6: formalizing the Flask API + RAGAS quantitative evaluation (2026-08-01)

Added a login-free, lightweight session profile (`/api/profile`) and feedback
collection (`/api/feedback`). The session profile is a pure UX convenience --
so a user doesn't have to re-type "I'm a permanent resident..." every time --
so it was designed to only affect `intent["user_type_tags"]`, never the
retrieval ranking logic itself: `classify()` got a new `session_user_type`
parameter, but any user type explicitly detected in the question text always
wins over the session profile (a question can be about a third party).

Then wired up RAGAS quantitative evaluation. Extracted the `/api/query` view's
logic into a pure `answer_question()` function so RAGAS could call it directly
without HTTP, exercising the literal production code path -- same principle as
the `answer_error` monkeypatch test from an earlier session. RAGAS's LLM judge
doesn't use `langchain_google_genai` directly either; it's wrapped in a custom
`BaseChatModel` that routes through `gemini_client.generate()`, so judge calls
get this project's "absolutely no billing" whitelist/backoff too.

**Two more things only found by actually running it:**
- `ragas==0.4.3` unconditionally imports a Vertex AI integration this project
  doesn't use (`langchain_community.chat_models.vertexai`), and that submodule
  had already been removed from the latest `langchain-community` (0.4.2,
  mid-"sunset"), so `import ragas` broke outright. Fixed by pinning
  `langchain-community==0.3.31`.
- This account's real daily quota for `gemini-3.6-flash` turned out to be
  **20 requests** -- far below the "1000-1500" assumed when Stage 5 was
  designed. Today's profile-integration tests and anchor regression checks
  alone had already used a good chunk of it before RAGAS even started;
  adding the pipeline's 6 generation calls plus roughly 12-20 judge calls
  exhausted it almost immediately -- the first run got only 1 of 12
  evaluations through before everything else failed on quota-related errors.
  Separated the judge onto a different whitelisted model
  (`gemini-3.5-flash-lite`) from the generation model, and serialized RAGAS's
  concurrency (`max_workers=1`), then it actually ran to completion -- except
  `gemini-3.6-flash` itself was already at zero quota for the day by then, so
  today's actual generation numbers came from temporarily binding the
  generation model to `gemini-3.5-flash-lite` via `unittest.mock.patch`,
  with no code changes.

The resulting numbers (faithfulness 0.2778, answer_relevancy 0.2670,
context_recall 0.7917, context_precision NaN from timeouts) aren't settled
quality metrics yet, given all that -- see the two "Stage 6" sections in
`docs/eval_results-en.md` for the full caveats and how to re-run cleanly.

## Stage 5 default-model lite switch attempt and rollback (2026-08-03)

Live numbers from the Google AI Studio console showed RPD wasn't uniform
across the 6 whitelisted models -- the three "Flash" models
(3.6/3.5/2.5-flash) were all capped at 20 RPD, while only the "Flash Lite"
models (3.5/3.1-flash-lite) got 500. The then-default `gemini-3.6-flash` had
already burned through its daily 20 once, so `DEFAULT_MODEL` was switched to
`gemini-3.5-flash-lite` to cut the risk of running out mid-demo.

Re-running the same 5 questions from the 2026-07-31 faithfulness spot check
after the switch turned up a problem: for 2 of 5 (a leave-of-absence
question and a social-service-agent travel question), the retrieved results
clearly contained the right article -- the latter with a top1 score of
0.9882 -- yet the lite model cited none of it, returning only "cannot be
determined from the provided articles." Retried both questions twice more
each to check for reproducibility: 3/3 identical every time -- not sampling
noise, a real defect in the lite model. Not hallucination (it ignored
evidence rather than inventing it), but it broke the "accurately cited
articles" core promise just as badly, so rolled back to
`gemini-3.6-flash`. Re-verifying the same two questions after the rollback
showed citations fully restored to baseline quality.

With quota freshly reset, also re-ran RAGAS with no model patch this time --
against the real `gemini-3.6-flash`. Faithfulness jumped from 07-31's 0.2778
to **0.8783**, backing up the hypothesis floated that day: the low score
wasn't a pipeline defect, it was the temporarily-substituted lite generation
model itself. context_precision again failed to score (NaN, timeouts), but
there were zero 429/quota errors -- today's 8 total `gemini-3.6-flash` calls
(2 rollback-verification + 6 RAGAS generation) stayed comfortably inside the
20 RPD cap. `DEFAULT_MODEL` stays on `gemini-3.6-flash`; the RPD-20 risk is
accepted knowingly. Full tables and logs are in the new section of
`docs/eval_results-en.md`.

## Stage 7: Next.js frontend port (2026-08-04)

Ported the Claude Design prototype (`DutyCompass.dc.html` -- a finished UI
running on its own DSL runtime, backed by mock data) to Next.js (App Router)
+ TypeScript + Tailwind CSS, and wired it to the real `/api/query` instead
of the mock. Went into plan mode before writing any code -- this was a
from-scratch app scaffold, and getting the structure right up front was
worth it.

**Design decisions already locked in during planning:**
- Kept the theme system as CSS-custom-property inline injection, exactly
  like the source (moving to Tailwind `dark:` classes would mean
  hand-transcribing ~90 color values into two places -- pure transcription risk).
- Scaffolded next-intl's `app/[locale]/` routing now, but deferred actual
  English translations to a follow-up (`localePrefix: "always"` keeps `/ko`
  and `/en` symmetric so the routing never needs revisiting).
- Designed the loading animation as a state machine: advance through 4
  fixed-timing stages, but if the real response is slower than that, hold at
  the last stage with its existing pulse animation for a "still working"
  signal; if the response is faster (e.g. out-of-scope), snap all stages to
  checked and hold briefly before applying the result.

**Things only found by actually writing the code:**
- `DutyCompass.dc.html`'s paragraph-number formatting turned out to be plain
  "Art. N" text, not the circled numerals (①②③) the porting instructions
  assumed -- caught by re-reading the actual source and corrected.
- Didn't use the originally-proposed citation-parsing design (a generic
  regex recognizing law names) -- built the regex from the literal
  `law_name` strings already in `results` instead, since the generic
  approach would have failed to match law names with an internal space
  (e.g. "병역의무자 국외여행 업무처리 규정").
- Next.js 16 (the latest at scaffold time) auto-generates an `AGENTS.md`
  warning that "this version may differ from your training data" -- this
  actually paid off: the bundled local docs caught that `middleware.ts` had
  been renamed to `proxy.ts` (export name too, `middleware` -> `proxy`)
  before any code was written against the old convention.
- Hit React Compiler's newer lint rules (`set-state-in-effect`,
  `immutability`) -- fixed two typing/reveal-animation hooks and one
  answer-rendering spot to use React's "adjust state during render" pattern
  instead of calling setState inside an effect body.
- **A duplicated 별표 (table) label bug**: `formatArticleLabel` was
  appending `article_no` ("별표3") after `law_name` (which already contains
  "병역법 시행령 별표 3"), rendering a visible duplicate. Code review alone
  didn't catch this -- **only actually looking at a screenshot did**, which
  justified not skipping the headless-browser verification pass.

**Verification**: ran the backend (5001) and frontend (3000) together and
drove a headless browser via Playwright -- normal answer (including citation
click -> scroll+highlight), low-confidence, out-of-scope, and
`answer_error` (via a temporary mock, fully removed after verification)
scenarios, plus 별표 label rendering, dark mode, and the EN "coming soon"
tooltip: 12/12 checks passed, zero console errors, 13 screenshots captured.
Full log is in the "Stage 7" section of [`eval_results-en.md`](eval_results-en.md).

Also wrote `backend/README-en.md` and `frontend/README-en.md` (+ Korean
pairs) this pass, documenting every directory's files in detail.

## Stage 8: Diagnosing `/api/query` latency -- the reranker was the real bottleneck (2026-08-04)

Started from one clue the user pulled out of a shell log: "Loading
weights" showed up in stderr during one specific request, but not during
the two prior requests in the same process. The working hypothesis was
that the embedder (BGE-m3) / reranker were being reloaded on every
request, and the ask was to verify that first.

The hypothesis turned out to be wrong -- both `embedder.py` and
`reranker.py` already cached their models correctly at module level
(`_loaded_models` dict, `_model` global). The actual cause was that
`answer_question()` returns early -- skipping retrieval/rerank entirely --
whenever a question is `out_of_scope` (KATUSA-type questions). That means
both models only get lazy-loaded on the process's **first in-scope
request**. If the session's first two questions were out-of-scope and the
third was the first in-scope one, that reproduces the observed log
exactly. Not a bug -- just a question of which request ends up absorbing
the cold-start cost.

Still a real problem for actual users (whoever's first genuine question
after a restart eats the delay), so `app.py` got a `_preload_models()`
call to load both models eagerly at server startup instead. Separately
from the root-cause diagnosis, also added a `[timing]` log
(retrieval/rerank/generate/total) to `answer_question()` so future
"it's slow" reports can point straight at the actual bottleneck stage.

**That's where the real finding showed up.** After a clean restart, "Loading
weights" never recurred (confirming the preload fix), but a single request
was still taking 56-94s. Breaking it down via the new `[timing]` log showed
**the reranker eating 43-73s, 75-80% of the total** -- dwarfing both
retrieval (~7s) and generate (5-15s). `routes/query.py` already had a
comment flagging exactly this risk ("the reranker scores up to 50
candidates every time on CPU with no `top_k` cutoff, so this could be the
bottleneck"), and this measurement confirmed it. So the originally
suspected cause (model reloading) wasn't the real one -- a different
hypothesis already written into the code was. Without the timing logs,
this would likely have kept getting misdiagnosed as a cold-start issue.

Diagnosis and instrumentation (preload + timing logs) only this round --
the reranker itself was left untouched. Full numbers and code are in the
"Stage 8" section of `docs/eval_results-en.md`.

## Stage 8 follow-up 1: reranker batching/thread tuning attempt -- no improvement (2026-08-04)

Picking up from Stage 8's conclusion ("the reranker is the real
bottleneck"), this round checked whether anything about it could
actually be fixed. Two ideas: (1) if `rerank()` called `predict()`
per-pair in a loop, switch to one batched call; (2) if it was still slow
after that, try raising the CPU thread count.

Idea 1 turned out to be moot -- it already passed the entire candidate
pool to `model.predict(pairs)` in a single call, nothing to fix. Moving
to idea 2: `torch.get_num_threads()` was 4, but this machine (M3) has 8
logical cores. Added `torch.set_num_threads(os.cpu_count())` to the top
of `reranker.py`.

The 3 anchor-query scores (leave of absence -> Art. 27(3) 0.5618,
part-time job -> Art. 22 0.3002, "how long can I put it off" -> Attached
Table 3 0.3092) matched to the decimal before and after the thread-count
change -- no regression. But re-running the 4 `[timing]` queries showed
rerank time essentially unchanged: 47.55->52.25s, 73.11->72.19s,
72.67->72.40s, 42.68->40.69s (one case even got worse). Conclusion:
neither attempt helped. A single forward pass of bge-reranker-v2-m3 was
likely already saturated at 4 threads, or the workload just doesn't
scale linearly with thread count. The change is harmless so it stayed in
the code, but it isn't validated as a fix. Full numbers in the "Stage 8
follow-up" section of `docs/eval_results-en.md`.

## Stage 7 follow-up: two OOS response UI fixes (2026-08-04)

Found and fixed two issues while manually testing "I want to apply for
KATUSA, does having a green card qualify me too?": (1) the MMA link
inside the OOS message was plain text, unclickable; (2) the
`relatedScopeInfo` evidence cards always rendered fully expanded,
pushing the actual guidance message off-screen.

Decided to linkify only at the frontend display layer, without changing
the backend's message format -- added `linkifyText()` following the same
pattern as `mapAnswerSegments`, splitting text into text/link segments.
The first pass matched URLs with a plain `\S+` and trimmed trailing
punctuation afterward, which failed on a parenthesis-wrapped link like
"see the notice(https://...)" -- the closing paren and whatever touched
it with no space ("...0525)를") got swallowed whole into the URL. Wrote
6 unit tests first and one of them actually caught this -- not something
that would've been obvious from just reading the code. Fixed by
excluding `)` from the URL character class entirely. Along the way, also
noticed the backend's `\n`-separated message lines weren't being
rendered as real line breaks at all, and fixed that with `whiteSpace:
pre-line`.

For the toggle, reproduced `MessageItem.tsx`'s existing pattern (local
`useState` + `EvidenceToggleButton` + a conditional card list) inside
`OosCard.tsx`. `EvidenceToggleButton` had the `evidence` i18n namespace
hardcoded, so added a `namespace` prop to reuse it instead of writing a
new component.

Verified in a real Playwright headless browser: the KATUSA question's
link is clickable and the toggle expands/collapses correctly; the
`related_scope_info: null` case (no user-type keyword detected) renders
no toggle button at all; the existing `isNormal`/`low_confidence` toggle
behavior shows no regression -- zero console errors across the board.
`vitest` (19/19), `tsc --noEmit`, and `eslint` all pass. Full
verification log and screenshot notes are in the "Stage 7 follow-up"
section of `docs/eval_results-en.md`.

## Stage 9: making the EN toggle actually work -- English answer generation (2026-08-05)

Stage 7 only got as far as scaffolding next-intl's routing; the EN
button itself was a "coming soon" tooltip stub. This round made three
things actually happen: (1) the whole UI switches language, (2) the
Gemini-generated answer body comes back in English, (3) article
citations stay in their original Korean form either way.

Threaded a `language` parameter through `answer_question()` ->
`classify()` -> `generate_answer()`, and unified every fixed backend
string (OOS notice, low-confidence notice) into `{"ko": ..., "en": ...}`
dicts.

On the frontend, `Header.tsx` now does a real locale switch via
next-intl's `useRouter`/`usePathname` (`router.replace(pathname,
{locale})`), and the old "coming soon" stub machinery
(`showEnHint`/`tryEn`/`EN_HINT_MS`) was removed entirely.
`messages/en.json`, previously just a copy of `ko.json`, is now real
English.

The hardest part was `citation_parser.py`, which parses answers using a
Korean regex trigger ("...에 따르면") -- and it took two wrong turns to
get right. Attempt 1: rather than hoping an English answer would
"naturally" reproduce that phrase, the EN system instruction mandated
embedding the exact Korean phrase verbatim inside English sentences.
Parsing worked, but reading an actual answer showed `"According to
X에 따르면"` -- "according to" said twice, once per language. Attempt 2:
dropped the English preposition and had sentences start directly with
"X에 따르면, ..." -- no more duplication, but the user pointed out
something more basic: an English answer should have *only* "according
to," with no "에 따르면" at all, full stop. So `citation_parser.py`
got a real English pattern ("According to {law name} Article N,
Paragraph M") and the system instruction now bans the Korean phrase
from English answers entirely. Both times, parsing itself was fine from
the start -- the actual failures were about prose matching spec, which
only showed up once a human read the output.

Mid-verification, MongoDB Atlas connectivity dropped out entirely at the
TLS handshake level (an infrastructure issue unrelated to this work --
resolved once the user updated the IP allowlist). Checked everything
that didn't need Mongo first (`classify()`'s language branching, pytest,
frontend tsc/eslint/vitest), then once the connection was back, verified
EN normal (both a table source and an ordinary-article source)/
low_confidence/out_of_scope plus the same questions in KO as a
regression check over real HTTP, and the EN toggle button itself via
Playwright -- all clean, zero console errors. Full details in the
"Stage 9" section of `docs/eval_results-en.md`.

## Progress summary

Stages 1-9 are all done. See each stage's section above and
`docs/eval_results-en.md` for details.

## What's left

- **Reranker latency**: confirmed that neither batching nor thread-count
  tuning helps. What's left is either shrinking the candidate pool
  (requires revisiting the tradeoff against the issue-1 accuracy fix) or
  switching to `device="mps"` (revisiting the original CPU choice, made
  over memory-pressure concerns) -- neither attempted yet.
- **A proofread pass on `messages/ko.json`**: the Korean text in the porting
  source arrived with corrupted encoding, so a number of strings were
  reconstructed via pattern-matching -- worth a review.

Related docs: [architecture-en.md](architecture-en.md) (overall structure),
[eval_results-en.md](eval_results-en.md) (the full raw evaluation log this
document is distilled from — much more detailed), and
[`../backend/README-en.md`](../backend/README-en.md) /
[`../frontend/README-en.md`](../frontend/README-en.md) for a
directory-by-directory file breakdown.
