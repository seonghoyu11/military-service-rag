"""
Splits generate_answer()'s plain-text answer into a segment list the
frontend can render as clickable citation chips, by matching citation
phrases against the `results` list already returned alongside the answer
(law_name/article_no/paragraph_no per chunk).

Both citation shapes SYSTEM_INSTRUCTION_KO (generation/answer.py) enforces
reduce to the same pattern once you look at how _format_articles() builds
the prompt Gemini actually sees:
  1. Ordinary articles: "{law_name} 제{N}조 제{M}항에 따르면" -- law_name is
     the plain law name (e.g. "병역법 시행령").
  2. 별표 (table) sources: "{law_name} 별표 {N}에 따르면" -- but the "별표 N"
     part isn't reconstructed from a template; it's already baked into the
     `law_name` field itself for these chunks (e.g. law_name is literally
     "병역법 시행령 별표 3", see _format_articles()'s table-branch header,
     which puts r["law_name"] straight into the block Gemini is shown). So
     matching "{law_name}에 따르면" directly, with no article number
     required, covers this case with no separate table-specific pattern.

SYSTEM_INSTRUCTION_EN uses a structurally different but parallel shape --
"According to {law_name} Article {N}, Paragraph {M}, ..." -- English words
for "Article"/"Paragraph", no Korean "제"/"조"/"항"/"에 따르면" at all (an
earlier version of the EN prompt embedded the Korean "...에 따르면" phrase
verbatim inside English sentences purely so this module wouldn't need an
EN-specific pattern; that read as an awkward "According to X에 따르면"
double-up of the same meaning in two languages once someone actually read
a real answer, so it was reverted in favor of a real English phrasing here
instead). `_build_citation_pattern(law_names, language)` dispatches
between the two regexes; `law_name` itself is never translated in either
language, so both patterns anchor on the same literal Korean strings.

Because of that, this module builds its citation regex from the literal
law_name strings already present in `results`, rather than trying to
recognize "looks like a law name" via a generic character-class pattern.
That's a deliberate choice, not just a simplification: this corpus has law
names with an internal space directly before the 법/규정/훈령 suffix (e.g.
"병역의무자 국외여행 업무처리 규정" has a space before "규정"), which a
generic `[\\w가-힣]+(?:법|규정|훈령)`-style pattern can't match across --
the space breaks the required no-gap adjacency between the name stem and
the suffix. Anchoring on the real law_name strings sidesteps that class of
bug entirely, and it also means matching automatically covers whatever law
names show up in retrieval, with nothing to keep in sync by hand.

ASSUMPTION (empirically true across every fixture examined so far, but not
a hard guarantee from the prompt): generate_answer() reproduces `law_name`
verbatim from the results block it was shown, rather than paraphrasing it.
SYSTEM_INSTRUCTION only specifies a citation *shape*, not "copy this exact
string" -- if a future law/chunk ever gets cited under a paraphrased name,
that citation would fall through to plain "text", not a "citation" segment
(see the fallback behavior below). Not a crash risk, just a missed chip.

Output shape: a list of
  {"type": "text", "content": str}
  {"type": "citation", "law_name": str, "article_no": str,
   "paragraph_no": str | None, "result_index": int | None}
segments, in reading order. result_index is None when a citation phrase
couldn't be matched to any result (shouldn't happen if generate_answer() is
only citing what it was given, but the frontend needs to handle it
gracefully -- render the label without making it clickable, don't crash).
"""
import re

# Captures either "제{N}조(의{sub})?( 제{M}항)?" for ordinary articles, or
# nothing extra, for table-shaped law_names that already end the sentence
# right after "law_name에 따르면" (see module docstring).
_ARTICLE_TAIL_KO = re.compile(
    r"\s*제(?P<article_no>\d+)조(?:의(?P<sub_no>\d+))?\s*(?:제(?P<paragraph_no>\d+)항)?"
)

# EN mirror of _ARTICLE_TAIL_KO -- generation/answer.py's EN system
# instruction mandates "Article {N}(-{sub})?(, Paragraph {M})?" as the
# literal English wording (never the Korean "제"/"조"/"항"/"에 따르면"), so
# an EN answer needs its own trigger pattern rather than reusing the KO one.
# Trigger is the leading "According to " instead of a trailing "에 따르면",
# since that's the fixed lead-in every EN citation clause starts with.
_ARTICLE_TAIL_EN = re.compile(
    r"\s+Article\s+(?P<article_no>\d+)(?:-(?P<sub_no>\d+))?"
    r"(?:,\s*Paragraph\s+(?P<paragraph_no>\d+))?"
)


def _build_citation_pattern(law_names, language="ko"):
    """
    Alternation sorted longest-name-first so that when one law_name is a
    prefix of another in the same results set (e.g. "병역법 시행령" is a
    prefix of "병역법 시행령 별표 3", both of which can appear together --
    an article from the base law and a table from the same law, cited in
    the same answer), the more specific/longer name wins the match instead
    of the alternation stopping early at the shorter prefix.

    language: "ko" or "en" (anything else falls back to "ko") -- selects
    which citation phrasing to match. The law_name itself is never
    translated regardless of language (see generate_answer's EN system
    instruction), so both patterns anchor on the same literal Korean
    law_name strings; only the surrounding article/trigger wording differs.
    """
    if not law_names:
        return None
    escaped = sorted((re.escape(n) for n in law_names), key=len, reverse=True)
    names_alt = "|".join(escaped)
    if language == "en":
        return re.compile(
            rf"According to\s+(?P<law_name>{names_alt})"
            rf"(?:{_ARTICLE_TAIL_EN.pattern})?"
        )
    return re.compile(
        rf"(?P<law_name>{names_alt})"
        rf"(?:{_ARTICLE_TAIL_KO.pattern})?"
        rf"\s*에\s*따르면"
    )


def _find_result_index(results, used, law_name, article_no, paragraph_no):
    """
    KNOWN LIMITATION: 별표 rows in this corpus commonly share the exact same
    (law_name, article_no, paragraph_no) -- they differ only in row
    *content* (the actual table condition), which this regex-based matcher
    never reads. When an answer cites the same table multiple times for
    different rows (real case: a "사회복무요원" answer cites 별표3 four
    times for four different eligibility conditions), this can only fall
    back to "first result with this law_name[/article_no] not yet used by
    an earlier citation in this same answer" -- correct IF the LLM's
    citation order follows the results order (true in every fixture
    checked so far, since results are handed to it in that order in the
    prompt), but not guaranteed for a differently-ordered answer. If this
    is later found to be unreliable, a content-overlap heuristic (compare
    words in the sentence following the citation phrase against each
    candidate's `text`) would be the next thing to try -- not implemented
    here, flagged instead.
    """
    if article_no is not None:
        candidates = [
            i for i, r in enumerate(results)
            if r["law_name"] == law_name and r["article_no"] == article_no
        ]
    else:
        # No "제N조" in the citation phrase -- either a table citation
        # (law_name already fully identifies the row's article_no) or a
        # law-only citation with no article number at all.
        candidates = [i for i, r in enumerate(results) if r["law_name"] == law_name]

    if paragraph_no:
        exact = [i for i in candidates if results[i]["paragraph_no"] == paragraph_no]
        if exact:
            return exact[0]

    for i in candidates:
        if i not in used:
            return i
    return candidates[0] if candidates else None


def parse_citations(answer_text, results, language="ko"):
    if not answer_text or not results:
        return []

    law_names = {r["law_name"] for r in results}
    pattern = _build_citation_pattern(law_names, language)
    if pattern is None:
        return [{"type": "text", "content": answer_text}] if answer_text.strip() else []

    segments = []
    used = set()
    cursor = 0

    for m in pattern.finditer(answer_text):
        if m.start() > cursor:
            leading = answer_text[cursor:m.start()]
            if leading.strip():
                segments.append({"type": "text", "content": leading})

        law_name = m.group("law_name")
        raw_article_no = m.group("article_no")
        if raw_article_no is not None:
            article_no = raw_article_no
            if m.group("sub_no"):
                article_no = f"{article_no}의{m.group('sub_no')}"
            paragraph_no = m.group("paragraph_no")
        else:
            article_no = None
            paragraph_no = None

        result_index = _find_result_index(results, used, law_name, article_no, paragraph_no)
        if result_index is not None:
            used.add(result_index)
            # For table citations (article_no is None from the regex), the
            # matched result carries the real article_no ("별표N") --
            # article_no/paragraph_no we emit should describe the actual
            # chunk being pointed at, not just what the sentence spelled out.
            article_no = results[result_index]["article_no"]
            paragraph_no = results[result_index]["paragraph_no"]

        segments.append({
            "type": "citation",
            "law_name": law_name,
            "article_no": article_no,
            "paragraph_no": paragraph_no,
            "result_index": result_index,
        })
        cursor = m.end()

    if cursor < len(answer_text):
        trailing = answer_text[cursor:]
        if trailing.strip():
            segments.append({"type": "text", "content": trailing})

    return segments
