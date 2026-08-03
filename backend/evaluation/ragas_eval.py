"""
Stage 6: RAGAS quantitative evaluation of the retrieval+generation pipeline.

Calls routes.query.answer_question() directly (the same function /api/query
hits, since the Stage 6 refactor pulled it out of the Flask view) instead of
making HTTP requests to a running server or reimplementing the pipeline --
this exercises the literal production code path, same principle behind the
answer_error monkeypatch test documented in docs/eval_results.md.

Two passes, run separately:
  1. Reference-free (faithfulness, answer_relevancy) -- runs on every
     question in the eval set that actually produced an answer. No
     ground_truth needed. This is the primary signal for this project's
     core promise (no hallucinated citations).
  2. Reference-based (context_precision, context_recall) -- runs only on
     the subset of questions that have a hand-written `ground_truth` field
     in the eval set, since these metrics need a reference answer to
     compare against.

COST NOTE: every question in the eval set triggers a REAL generate_answer()
call (Stage 5, counts against the free-tier Gemini quota) PLUS one or more
judge calls per RAGAS metric (also real Gemini calls, via
generation/ragas_llm.py -- see that file for why this goes through the same
whitelist/backoff as everything else). A 10-question eval set with both
passes is roughly 10 (generation) + 10*2 (reference-free judge calls) +
5*2 (reference-based judge calls, if ~5 are labeled) = ~40 Gemini calls.
Free tier is ~10-15 RPM / ~1000-1500 per day (see gemini_client.py) --
comfortable for a set this size run occasionally, but don't loop this over
the full 28-scenario stress-test set without checking the daily count first.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datasets import Dataset
from ragas import evaluate
from ragas.embeddings import LangchainEmbeddingsWrapper
from ragas.llms import LangchainLLMWrapper
from ragas.metrics import (
    Faithfulness,
    ResponseRelevancy,
    LLMContextPrecisionWithReference,
    LLMContextRecall,
)
from ragas.run_config import RunConfig

from routes.query import answer_question
from generation.ragas_llm import WhitelistedGeminiChatModel
from evaluation.ragas_embeddings import BGE_M3_Embeddings

EVAL_SET_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "data", "eval", "ragas_eval_set.json"
)

# generate_answer() (Stage 5) uses gemini_client.DEFAULT_MODEL (gemini-3.6-flash)
# for the actual answers. Judge calls use a *different* whitelisted model here
# so the two don't compete for the same free-tier daily quota bucket --
# discovered the hard way: gemini-3.6-flash's free tier turned out to be capped
# at 20 requests/DAY for this account (not the ~1000-1500/day assumed at design
# time), and the 8-question generation pass alone was enough to leave no
# headroom for the ~12-20 judge calls RAGAS needs on top of that.
#
# (2026-08-01 briefly moved DEFAULT_MODEL to gemini-3.5-flash-lite too, which
# would have put generation and judge calls in the same 500 RPD bucket -- but
# that switch was reverted 2026-08-03 after a faithfulness spot check found
# the lite model unreliably ignored well-matched retrieved context on some
# questions. DEFAULT_MODEL is back to gemini-3.6-flash, so this is a genuinely
# separate quota bucket from JUDGE_MODEL again.)
JUDGE_MODEL = "gemini-3.5-flash-lite"

# RAGAS defaults to max_workers=16 / max_retries=10, which fires way more
# concurrent requests than the free tier's ~10-15 RPM can absorb -- that's what
# turned a handful of real 429s into a wall of TimeoutErrors (RAGAS's own
# retry-of-retries piling on top of gemini_client's own capped backoff).
# Serializing to 1 worker with 1 retry keeps this from hammering the API.
JUDGE_RUN_CONFIG = RunConfig(max_workers=1, max_retries=1)


def _run_pipeline(eval_set):
    """
    Calls the real pipeline for each question and assembles RAGAS-shaped
    rows. Skips out_of_scope/low_confidence/answer-less results from the
    reference-free pass -- those never reach generate_answer() by design
    (see generation/answer.py's low_confidence gating), so there's no
    `answer` text to score faithfulness/relevancy against. Still worth
    checking manually, just not through these particular metrics.
    """
    rows = []
    for item in eval_set:
        result = answer_question(item["question"])
        if result.get("out_of_scope") or result.get("low_confidence") or not result.get("answer"):
            print(
                f"[ragas_skip] question={item['question']!r} "
                f"out_of_scope={result.get('out_of_scope')} "
                f"low_confidence={result.get('low_confidence')} "
                f"has_answer={bool(result.get('answer'))}",
                file=sys.stderr,
            )
            continue
        rows.append({
            "user_input": item["question"],
            "response": result["answer"],
            "retrieved_contexts": [r["text"] for r in result["results"]],
            "reference": item.get("ground_truth"),  # may be None
        })
    return rows


def run_reference_free(rows):
    dataset = Dataset.from_list([
        {k: v for k, v in row.items() if k != "reference"} for row in rows
    ])
    llm = LangchainLLMWrapper(WhitelistedGeminiChatModel(model=JUDGE_MODEL))
    embeddings = LangchainEmbeddingsWrapper(BGE_M3_Embeddings())
    return evaluate(
        dataset,
        metrics=[Faithfulness(), ResponseRelevancy()],
        llm=llm,
        embeddings=embeddings,
        run_config=JUDGE_RUN_CONFIG,
    )


def run_reference_based(rows):
    labeled = [row for row in rows if row.get("reference")]
    if not labeled:
        print("[ragas] no ground_truth-labeled rows -- skipping reference-based metrics", file=sys.stderr)
        return None
    dataset = Dataset.from_list(labeled)
    llm = LangchainLLMWrapper(WhitelistedGeminiChatModel(model=JUDGE_MODEL))
    return evaluate(
        dataset,
        metrics=[LLMContextPrecisionWithReference(), LLMContextRecall()],
        llm=llm,
        run_config=JUDGE_RUN_CONFIG,
    )


if __name__ == "__main__":
    with open(EVAL_SET_PATH, encoding="utf-8") as f:
        eval_set = json.load(f)

    rows = _run_pipeline(eval_set)
    print(f"[ragas] {len(rows)}/{len(eval_set)} questions produced a scoreable answer", file=sys.stderr)

    print("\n=== Reference-free metrics (faithfulness, answer_relevancy) ===")
    free_result = run_reference_free(rows)
    print(free_result)

    print("\n=== Reference-based metrics (context_precision, context_recall) ===")
    based_result = run_reference_based(rows)
    if based_result is not None:
        print(based_result)
