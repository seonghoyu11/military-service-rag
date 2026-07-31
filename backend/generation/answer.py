"""
Stage 5: synthesizes retrieved law-article chunks into a grounded,
citation-bearing natural-language answer via Gemini.

By the time a question reaches this module, the rule-based pipeline
(classifier -> hybrid retrieval -> reranker, see routes/query.py) has
already done all the "judgment" work -- which articles are relevant, how
they're ranked, whether the result is confident enough to answer at all.
This module's only job is turning already-retrieved article text into
readable Korean prose with citations; it must not introduce facts that
aren't in that text.
"""
from google.genai import types

from generation.gemini_client import DEFAULT_MODEL, generate

SYSTEM_INSTRUCTION = (
    "너는 한국 병역법 안내 챗봇의 답변 생성기다. 아래 '근거조항'에 제시된 조항 "
    "텍스트에 있는 내용만 근거로 답변할 것. 근거조항에 없는 내용은 추측하거나 "
    "지어내지 말고, 질문에 답하기에 정보가 부족하면 '제공된 조항만으로는 "
    "판단하기 어렵습니다'라고 명시할 것. 답변의 모든 문장은 반드시 "
    "'○○법 제○○조 제○항에 따르면...'과 같은 형식으로 근거가 된 조항을 문장 "
    "안에 명시할 것 — 인용 없는 문장은 쓰지 말 것. 단, 근거조항이 '별표'(표) "
    "형태로 제시된 경우에는 '○○ 시행령 별표 3에 따르면...'처럼 표기하고 "
    "'제○○조'로 표기하지 말 것. 답변은 한국어로 작성할 것."
)


def _format_articles(results):
    blocks = []
    for i, r in enumerate(results, start=1):
        article_no = r["article_no"]
        paragraph_no = r.get("paragraph_no")
        if article_no.startswith("별표"):
            # Table (별표) entries aren't "조" (numbered articles) -- article_no
            # is a literal table label like "별표3", not a number, so the
            # "제N조" template below would produce a malformed "제별표3조".
            header = f"{r['law_name']} ({r['article_title']}) 항목 {paragraph_no}"
        else:
            paragraph = f" 제{paragraph_no}항" if paragraph_no not in (None, "all") else ""
            header = f"{r['law_name']} 제{article_no}조{paragraph} ({r['article_title']})"
        blocks.append(f"[근거조항 {i}] {header}\n{r['text']}")
    return "\n\n".join(blocks)


def generate_answer(question: str, results: list[dict]) -> str | None:
    """
    question: the user's original question.
    results: routes/query.py's `results` list (law_name, article_no,
              article_title, paragraph_no, text, score).

    Returns the generated answer text, or None if there's nothing to ground
    an answer in (empty `results`).

    Callers (routes/query.py) are expected to gate on `low_confidence` and
    empty results *before* calling this -- this function doesn't receive the
    `low_confidence` flag at all, by design, so it can't accidentally dress
    up a low-confidence retrieval as a confident-sounding answer. The empty-
    `results` check below is just a defensive no-op guard for direct calls.
    """
    if not results:
        return None

    prompt = (
        f"--- 근거조항 ---\n{_format_articles(results)}\n\n"
        f"--- 질문 ---\n{question}"
    )

    response = generate(
        DEFAULT_MODEL,
        prompt,
        generation_config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION
        ),
    )
    return response.text
