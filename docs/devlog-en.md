# Developer Notes: RAG Chatbot for Overseas Korean Military Service Obligors

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
guardrails: a hardcoded model whitelist (only `gemini-2.5-flash`/`gemini-2.5-flash-lite`,
Pro-tier models blocked), no Vertex AI code path (Google AI Studio only), and a capped
retry count instead of unbounded retries on rate-limit errors. Full implementation and
verification details are in the "Stage 5: Gemini Flash answer-generation verification"
section of `docs/eval_results-en.md`.

## What's left

- **Stage 5 (in progress)**: Google Gemini API integration — retrieved
  articles + question → natural-language answer generation (eligibility
  judgment stays rule-based; the LLM's job is synthesis only).
- **Stage 6**: formalize the Flask API (`/api/profile`, `/api/feedback`) +
  RAGAS evaluation (needs Stage 5 done first, to measure answer
  faithfulness).
- **Stage 7**: the Next.js frontend — a Korean/English toggle via
  next-intl is required, since the target users are overseas Koreans.

Related docs: [architecture-en.md](architecture-en.md) (overall structure),
[eval_results-en.md](eval_results-en.md) (the full raw evaluation log this
document is distilled from — much more detailed).