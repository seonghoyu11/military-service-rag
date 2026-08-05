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

# Grounding rules shared by both language variants of SYSTEM_INSTRUCTION
# below -- each half (ko/en) says the same thing, kept as separate KO/EN
# strings (not a single templated one) since natural phrasing differs too
# much between the languages to share a template without reading awkwardly
# in one of them.
_GROUNDING_RULE = {
    "ko": (
        "아래 '근거조항'에 제시된 조항 텍스트에 있는 내용만 근거로 답변할 것. "
        "근거조항에 없는 내용은 추측하거나 지어내지 말 것."
    ),
    "en": (
        "Base your answer only on the content of the '근거조항' (grounding articles) "
        "provided below. Do not guess or invent anything that isn't in those articles."
    ),
}

_INSUFFICIENT_INFO_RULE = {
    "ko": "질문에 답하기에 정보가 부족하면 '제공된 조항만으로는 판단하기 어렵습니다'라고 명시할 것.",
    "en": (
        "If there is not enough information to answer, say so explicitly in English -- "
        'e.g. "The provided articles don\'t specify this."'
    ),
}

# The EN variant uses a real English citation phrase -- "According to
# {law name} Article {N}, Paragraph {M}, ..." -- not the Korean "...에
# 따르면" phrase. An earlier version embedded the Korean trigger phrase
# verbatim inside English sentences purely so citation_parser wouldn't need
# an EN-specific regex; in practice that produced doubled-up phrasing like
# "According to 병역법 제27조 제3항에 따르면, ..." (the same "according to"
# meaning said once in English and once in Korean) the moment the model
# added its own natural lead-in on top of the mandated Korean phrase. Fixed
# by giving citation_parser.py a proper EN pattern instead
# (_build_citation_pattern's language="en" branch) and dropping the Korean
# phrase from the EN prompt entirely -- law_name itself still stays
# untranslated Korean either way (see _ARTICLE_NAME_RULE_EN below).
_CITATION_RULE = {
    "ko": (
        "답변의 모든 문장은 반드시 '○○법 제○○조 제○항에 따르면...'과 같은 형식으로 "
        "근거가 된 조항을 문장 안에 명시할 것 — 인용 없는 문장은 쓰지 말 것. 단, "
        "근거조항이 '별표'(표) 형태로 제시된 경우에는 '○○ 시행령 별표 3에 따르면...'처럼 "
        "표기하고 '제○○조'로 표기하지 말 것."
    ),
    "en": (
        "Every sentence in your answer must cite its source article inline, in this exact "
        'form: "According to {law name} Article {N}, Paragraph {M}, ..." -- "According to", '
        '"Article", and "Paragraph" must be written as the English words shown, with plain '
        'digits for the numbers. Do NOT use the Korean legal phrase "에 따르면", "제{N}조", or '
        '"제{M}항" anywhere -- "According to ... Article ... Paragraph ..." is the complete '
        "citation lead-in by itself; never combine it with the Korean phrase (that would say "
        '"according to" twice, once in each language). The {law name} itself, however, stays '
        "in its original Korean form -- never translate it. For an article with a sub-number "
        '(제{N}조의{sub} in Korean), write "Article {N}-{sub}". Do not write any sentence '
        'without a citation. For a 별표 (table) source, use "According to {law name}, ..." '
        'with no "Article"/"Paragraph" at all (the table number is already part of {law '
        'name}). Correct: "According to 병역법 Article 27, Paragraph 3, the permit may be '
        'revoked if the person no longer meets the requirements." Incorrect: "병역법 제27조 '
        '제3항에 따르면, ..." or "According to 병역법 제27조 제3항에 따르면, ..." (never mix '
        "in the Korean citation phrase)."
    ),
}

_ARTICLE_NAME_RULE_EN = (
    "Keep every article name (law name, article number, paragraph number) in its original "
    "Korean form -- never translate these, even though the rest of your answer is in English."
)

SYSTEM_INSTRUCTION_KO = (
    "너는 한국 병역법 안내 챗봇의 답변 생성기다. "
    f"{_GROUNDING_RULE['ko']} {_INSUFFICIENT_INFO_RULE['ko']} {_CITATION_RULE['ko']} "
    "답변은 한국어로 작성할 것."
)

SYSTEM_INSTRUCTION_EN = (
    "You are the answer-generation component of a chatbot that explains Korean military "
    "service law (병역법). "
    f"{_GROUNDING_RULE['en']} {_INSUFFICIENT_INFO_RULE['en']} {_CITATION_RULE['en']} "
    f"{_ARTICLE_NAME_RULE_EN} Write your answer in English."
)

SYSTEM_INSTRUCTIONS = {"ko": SYSTEM_INSTRUCTION_KO, "en": SYSTEM_INSTRUCTION_EN}


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


def generate_answer(question: str, results: list[dict], language: str = "ko") -> str | None:
    """
    question: the user's original question.
    results: routes/query.py's `results` list (law_name, article_no,
              article_title, paragraph_no, text, score).
    language: "ko" or "en" (anything else falls back to "ko") -- selects
              which SYSTEM_INSTRUCTIONS variant Gemini is given, so the
              generated prose comes back in that language while article
              citations stay Korean either way (see SYSTEM_INSTRUCTION_EN).

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
            system_instruction=SYSTEM_INSTRUCTIONS.get(language, SYSTEM_INSTRUCTION_KO)
        ),
    )
    return response.text
