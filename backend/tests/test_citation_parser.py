"""
Unit tests for generation/citation_parser.py, against two real /api/query
responses (not hand-written text) captured live on 2026-08-03 with
DEFAULT_MODEL=gemini-3.6-flash -- see tests/fixtures/citation_case*.json.

Case 1 (사회복무요원인데 해외 갈 수 있나요) is the interesting one: the
answer cites 병역법 시행령 별표 3 four times for four different eligibility
conditions, but all four 별표3 rows in `results` share the exact same
(law_name, article_no, paragraph_no) -- see citation_parser.py's
_find_result_index docstring for why that's a known limitation (order-based
fallback, not content-based). This test checks the fallback actually landed
on the *content-correct* row for each of the four citations, not just that
some non-null result_index came back.

Case 2 (유학 중인데 휴학하면...) is the regression case: two citations
against two different law names, one of which
("병역의무자 국외여행 업무처리 규정") has an internal space directly before
its "규정" suffix -- the kind of law name a generic `[\\w가-힣]+규정`-shaped
regex can't match across (see citation_parser.py's module docstring for why
this parser matches literal law_name strings from `results` instead).
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from generation.citation_parser import parse_citations

FIXTURES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


def _load_fixture(name):
    with open(os.path.join(FIXTURES_DIR, name), encoding="utf-8") as f:
        data = json.load(f)
    return data["answer"], data["results"]


def test_case1_table_citations_map_to_content_correct_rows():
    answer, results = _load_fixture("citation_case1.json")
    segments = parse_citations(answer, results)

    citations = [s for s in segments if s["type"] == "citation"]
    assert len(citations) == 5

    # citation 1: 135조⑧, the only non-별표 result -- unambiguous.
    assert citations[0]["law_name"] == "병역법 시행령"
    assert citations[0]["article_no"] == "135"
    assert citations[0]["result_index"] == 0

    # citations 2-5: four 별표3 rows sharing (law_name, article_no,
    # paragraph_no) -- must land on result_index 1, 2, 3, 4 IN ORDER, and
    # each one's result_index must point at the row whose `text` actually
    # matches what that specific citation's trailing sentence describes
    # (not just "some unused 별표3 row").
    assert [c["result_index"] for c in citations[1:]] == [1, 2, 3, 4]
    for c in citations[1:]:
        assert c["law_name"] == "병역법 시행령 별표 3"
        assert c["article_no"] == "별표3"

    text_segments = [s["content"] for s in segments if s["type"] == "text"]

    # Content check for each 별표3 citation: the result row matched by
    # result_index must actually be the one the surrounding text is talking
    # about -- this is the part a "result_index is not None" check alone
    # would miss.
    expectations = [
        (1, "해외이주신고를 한 사람", "3년 범위에서 한 번만"),
        (2, "해외이주신고를 하고 출국 대기기간", "3년 이상"),
        (3, "5년 이상 국외에서 거주", "주재원"),
        (4, "조건부 또는 임시영주권", "6개월"),
    ]
    for citation, (expected_index, *keywords) in zip(citations[1:], expectations):
        assert citation["result_index"] == expected_index
        matched_row_text = results[citation["result_index"]]["text"]
        for kw in keywords:
            assert kw in matched_row_text

    # And the answer's own trailing prose after each citation should mention
    # the same condition as the row it's now linked to (cross-checking the
    # segmenter split the text in the right places, not just that the
    # citation lookup happened to be right).
    assert "해외이주신고를 한 사람" in text_segments[1]
    assert "5년 이상" in text_segments[3]


def test_case2_multi_word_law_name_with_internal_space_matches():
    answer, results = _load_fixture("citation_case2.json")
    segments = parse_citations(answer, results)

    citations = [s for s in segments if s["type"] == "citation"]
    assert len(citations) == 2

    # "병역의무자 국외여행 업무처리 규정" has a space directly before its
    # "규정" suffix -- the regression this test guards against is a
    # generic-regex matcher failing to see this as one law name at all and
    # silently downgrading the whole citation to plain text.
    assert citations[0]["law_name"] == "병역의무자 국외여행 업무처리 규정"
    assert citations[0]["article_no"] == "27"
    assert citations[0]["paragraph_no"] == "3"
    assert citations[0]["result_index"] == 0
    assert results[0]["law_name"] == "병역의무자 국외여행 업무처리 규정"
    assert results[0]["article_no"] == "27"
    assert results[0]["paragraph_no"] == "3"

    assert citations[1]["law_name"] == "병역법 시행령"
    assert citations[1]["article_no"] == "125"
    assert citations[1]["paragraph_no"] == "2"
    assert citations[1]["result_index"] == 3
    assert results[3]["law_name"] == "병역법 시행령"
    assert results[3]["article_no"] == "125"
    assert results[3]["paragraph_no"] == "2"

    # No part of the answer should have silently fallen through to
    # unlabeled text because of a match failure -- the only "text" segments
    # should be the prose between/after the two citations, and neither of
    # them should still contain an unmatched "...에 따르면" citation phrase
    # (which would indicate the regex missed it).
    for s in segments:
        if s["type"] == "text":
            assert "에 따르면" not in s["content"]


def test_empty_answer_returns_no_segments():
    _, results = _load_fixture("citation_case1.json")
    assert parse_citations(None, results) == []
    assert parse_citations("", results) == []


def test_empty_results_returns_no_segments():
    assert parse_citations("병역법 제1조에 따르면 어쩌구", []) == []


def test_unmatchable_citation_gets_null_result_index_not_a_crash():
    results = [{
        "law_name": "병역법",
        "article_no": "1",
        "paragraph_no": "1",
        "text": "...",
        "score": 0.5,
    }]
    # Cites a law that isn't in `results` at all -- shouldn't happen if
    # generate_answer() only cites what it was given, but the parser must
    # not crash on it; the whole thing should just come back as plain text
    # since it doesn't match any known law_name.
    segments = parse_citations("존재하지않는법 제5조에 따르면 그렇다.", results)
    assert all(s["type"] == "text" for s in segments)
