import os
import json
import sys
import time

from flask import Blueprint, request, jsonify

from classifier.predict import classify
from db.mongo import get_db
from generation.answer import generate_answer
from generation.citation_parser import parse_citations
from retrieval import bm25_search, hybrid, reranker

query_bp = Blueprint("query", __name__)

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHUNKS_PATH = os.path.join(BACKEND_DIR, "data", "processed", "law_chunks.json")

with open(CHUNKS_PATH, encoding="utf-8") as f:
    _chunks = json.load(f)
_bm25 = bm25_search.build_bm25_index(_chunks)

# "입영연기_신청" (getting a postponement) and "입영연기_취소" (cancelling one
# already granted) share so much vocabulary that BM25/dense/reranker alone
# confuse them -- e.g. a 자진 입영(voluntary early enlistment) chunk about
# cancelling a granted postponement can outrank the actual "how do I get a
# postponement" answer. Nudge the score using the directional tag once we
# know which way the question is asking.
DIRECTIONAL_TAGS = {"입영연기_신청", "입영연기_취소"}
DIRECTIONAL_BOOST = 0.25
FINAL_TOP_K = 5
# Explicit override for classifier.model.SYNONYM_ANCHOR_LOOKUPS matches. Being
# in the candidate pool isn't enough on its own -- the cross-encoder reranker
# can still judge the anchor chunk as genuinely low-relevance on its own terms
# (e.g. "휴학" vs "재학사실을...허가요건을 유지하지 못한 경우" scored 0.0118,
# rank 16/50) and a top_k rerank cut before this boost runs would drop it
# entirely. So reranker.rerank() below is called on the *whole* candidate
# pool (no top_k truncation) precisely so this boost can still surface it.
ANCHOR_BOOST = 0.3

# Empirically, the reranker's absolute top-1 score is NOT a clean separator
# between "genuinely irrelevant" and "genuinely relevant but tersely phrased"
# questions in this corpus -- e.g. "미국 영주권 받은 지 2년밖에 안 됐는데" (a real,
# answerable question) scored 0.0061, LOWER than "복수국적인데 한국 국적 포기 안
# 하면 군대 가야 하나요" (an out-of-corpus noise question) at 0.0147. No single
# threshold cleanly separates these samples. This is set low and treated as an
# ADVISORY flag shown alongside results, not a hard cutoff that hides them --
# hiding results on this signal would suppress more legitimate weak-signal
# answers than it filters actual noise. See docs/eval_results.md (issue 2).
LOW_CONFIDENCE_THRESHOLD = 0.05
LOW_CONFIDENCE_NOTICE = {
    "ko": (
        "검색 결과의 확신도가 낮습니다. 질문을 더 구체적으로 작성하시거나 표현을 바꿔서 "
        "다시 시도해 보세요. 아래 결과는 참고용입니다."
    ),
    "en": (
        "The search results have low confidence. Try rephrasing your question or making it "
        "more specific. The results below are for reference only."
    ),
}


def _apply_directional_boost(reranked, intent_topic_tags):
    intent_directional = DIRECTIONAL_TAGS & set(intent_topic_tags)
    if not intent_directional:
        return reranked

    adjusted = []
    for chunk, score in reranked:
        chunk_directional = DIRECTIONAL_TAGS & set(chunk.get("topic_tags", []))
        if chunk_directional & intent_directional:
            score += DIRECTIONAL_BOOST
        elif chunk_directional:
            score -= DIRECTIONAL_BOOST
        adjusted.append((chunk, score))

    return sorted(adjusted, key=lambda pair: -pair[1])


def _apply_anchor_boost(reranked, anchor_lookups):
    if not anchor_lookups:
        return reranked

    adjusted = []
    for chunk, score in reranked:
        if any(
            chunk["law_name"] == a["law_name"] and chunk["article_no"] == a["article_no"]
            for a in anchor_lookups
        ):
            score += ANCHOR_BOOST
        adjusted.append((chunk, score))

    return sorted(adjusted, key=lambda pair: -pair[1])


def _inject_anchor_chunks(candidates, anchor_lookups):
    """
    Force-includes specific (law_name, article_no) chunks into the candidate
    pool regardless of their BM25/dense rank. Some user phrasing (e.g. "자퇴")
    has near-zero lexical/semantic overlap with the statute text that answers
    it, so the real answer can rank far outside the pool the reranker ever
    sees -- see classifier.model.SYNONYM_ANCHOR_LOOKUPS.
    """
    if not anchor_lookups:
        return candidates

    existing_texts = {chunk["text"] for chunk, _ in candidates}
    extra = [
        (chunk, 0.0)
        for chunk in _chunks
        if chunk["text"] not in existing_texts
        and any(
            chunk["law_name"] == a["law_name"] and chunk["article_no"] == a["article_no"]
            for a in anchor_lookups
        )
    ]
    return candidates + extra


def _session_user_type(session_id):
    """
    Looks up the caller's saved profile (Stage 6 /api/profile) by session_id.
    A Mongo hiccup here shouldn't take down the whole query -- worst case is
    just falling back to the no-profile behavior, so failures are swallowed
    and logged the same way generation failures are (see [answer_error]
    above).
    """
    if not session_id:
        return None
    try:
        doc = get_db()["profiles"].find_one({"_id": session_id})
    except Exception as e:
        print(f"[profile_lookup_error] session_id={session_id!r} error={e!r}", file=sys.stderr)
        return None
    return doc.get("user_type") if doc else None


def answer_question(question, session_user_type=None, language="ko"):
    """
    Classifies the question, returns the top-ranked law chunks (hybrid
    retrieval + reranker), and -- when confident enough -- a Gemini-generated
    answer grounded in those chunks.

    Pulled out of the /api/query view (Stage 6) so RAGAS evaluation
    (evaluation/ragas_eval.py) can call the exact same production code path
    directly, without going through HTTP or reimplementing any of this.

    language: "ko" or "en" (anything else falls back to "ko") -- the EN
    toggle's output language. Only changes which language fixed strings
    (LOW_CONFIDENCE_NOTICE, classify()'s fallback_message) and the Gemini-
    generated answer come back in; retrieval/reranking/boosts are entirely
    language-independent (see generation/answer.py and classifier/model.py
    for where the actual localized strings live).
    """
    if language not in ("ko", "en"):
        language = "ko"

    intent = classify(question, session_user_type=session_user_type, language=language)
    if intent["out_of_scope"]:
        related_scope_info = None
        lookup = intent.get("related_lookup")
        if lookup:
            related_scope_info = [
                {
                    "law_name": c["law_name"],
                    "article_no": c["article_no"],
                    "article_title": c["article_title"],
                    "paragraph_no": c["paragraph_no"],
                    "text": c["text"],
                }
                for c in _chunks
                if c["law_name"] == lookup["law_name"] and c["article_no"] == lookup["article_no"]
            ]

        return {
            "out_of_scope": True,
            "message": intent["fallback_message"],
            "intent": intent,
            "related_scope_info": related_scope_info,
        }

    t0 = time.time()
    candidates = hybrid.search(question, _bm25, _chunks, top_k=40, candidate_pool=50)
    candidates = _inject_anchor_chunks(candidates, intent.get("anchor_lookups"))
    t1 = time.time()
    # top_k=len(candidates): score every candidate, don't truncate yet -- both
    # boosts below need the full reranked list to have a chance at surfacing
    # a chunk the reranker itself scored outside the top 15.
    reranked = reranker.rerank(question, candidates, top_k=len(candidates))
    t2 = time.time()

    # Margin (top1 - top2) diagnostic, logged pre-boost so the directional/anchor
    # nudges below don't distort the reranker's own confidence signal. Collecting
    # data to check whether margin separates true-positive from noise queries
    # better than the absolute LOW_CONFIDENCE_THRESHOLD does -- see eval_results.md.
    top1_score = reranked[0][1] if reranked else 0.0
    top2_score = reranked[1][1] if len(reranked) > 1 else 0.0
    print(
        f"[margin] query={question!r} top1={top1_score:.4f} top2={top2_score:.4f} "
        f"margin={top1_score - top2_score:.4f}",
        file=sys.stderr,
    )

    reranked = _apply_directional_boost(reranked, intent["topic_tags"])
    reranked = _apply_anchor_boost(reranked, intent.get("anchor_lookups"))[:FINAL_TOP_K]

    low_confidence = bool(reranked) and reranked[0][1] < LOW_CONFIDENCE_THRESHOLD

    results = [
        {
            "law_name": chunk["law_name"],
            "article_no": chunk["article_no"],
            "article_title": chunk["article_title"],
            "paragraph_no": chunk["paragraph_no"],
            "text": chunk["text"],
            "score": round(score, 4),
        }
        for chunk, score in reranked
    ]

    # Generation only runs on confident, non-empty retrieval -- a low-confidence
    # or empty result set never reaches Gemini, so the LLM can't dress up a
    # weak retrieval as a confident-sounding answer (see generation/answer.py).
    # Any failure here (API error, quota exhaustion, etc.) is swallowed so the
    # request still returns the retrieved articles instead of a 500.
    answer = None
    answer_error = None
    if not low_confidence and results:
        try:
            answer = generate_answer(question, results, language=language)
        except Exception as e:
            print(f"[answer_error] query={question!r} error={e!r}", file=sys.stderr)
            answer_error = f"{type(e).__name__}: {e}"
        t3 = time.time()
    else:
        t3 = t2

    print(
        f"[timing] query={question!r} retrieval={t1-t0:.2f}s rerank={t2-t1:.2f}s "
        f"generate={t3-t2:.2f}s total={t3-t0:.2f}s",
        file=sys.stderr,
    )

    # Structured form of `answer` for the frontend's clickable citation
    # chips (chip click -> scroll/highlight the matching card in `results`).
    # Parsed here, not on the frontend, since the law_name/article_no
    # matching needs `results` -- which already lives in this function --
    # and keeps any future citation-format changes (e.g. the 별표 special
    # case) in one place instead of two. `answer` is left untouched for
    # debugging/logging; this is purely additive.
    answer_segments = parse_citations(answer, results, language) if answer else None

    return {
        "out_of_scope": False,
        "intent": intent,
        "results": results,
        "related_scope_info": None,
        "low_confidence": low_confidence,
        "low_confidence_notice": LOW_CONFIDENCE_NOTICE[language] if low_confidence else None,
        "answer": answer,
        "answer_segments": answer_segments,
        "answer_error": answer_error,
    }


@query_bp.route("/api/query", methods=["POST"])
def query():
    data = request.get_json(silent=True) or {}
    question = (data.get("question") or "").strip()
    if not question:
        return jsonify({"error": "question is required"}), 400

    session_id = (data.get("session_id") or "").strip()
    session_user_type = _session_user_type(session_id)
    language = data.get("language") if data.get("language") in ("ko", "en") else "ko"

    return jsonify(
        answer_question(question, session_user_type=session_user_type, language=language)
    )