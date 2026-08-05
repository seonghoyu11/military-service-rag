import { describe, expect, it } from "vitest";

import {
  formatArticleLabel,
  linkifyText,
  mapAnswerSegments,
  mapResponseToViewModel,
  rankRelevance,
} from "./mapResponse";
import type { QueryApiResponse, ResultItem } from "./types";

const baseResult: ResultItem = {
  law_name: "병역법",
  article_no: "70",
  article_title: "국외이주 목적 허가",
  paragraph_no: "3",
  text: "본문",
  score: 0.5,
};

describe("formatArticleLabel", () => {
  it("별표 sources never get a '제…조' suffix appended", () => {
    // Regression test for the duplicated-label bug found via screenshot
    // verification ("병역법 시행령 별표 3 별표3").
    const label = formatArticleLabel("병역법 시행령 별표 3", "별표3", "1", {
      withLawName: true,
      withParagraph: true,
    });
    expect(label).toBe("병역법 시행령 별표 3");
    expect(label).not.toMatch(/제별표\d+조/);
  });

  it("별표 citation-chip label (no law name) is just the article_no", () => {
    const label = formatArticleLabel("병역법 시행령 별표 3", "별표3", "1", {
      withLawName: false,
      withParagraph: false,
    });
    expect(label).toBe("별표3");
  });

  it("paragraph_no of 'all' produces no 항 suffix", () => {
    const label = formatArticleLabel("병역법", "22", "all", {
      withLawName: true,
      withParagraph: true,
    });
    expect(label).toBe("병역법 제22조");
  });

  it("a normal article+paragraph renders plain text, not a circled numeral", () => {
    const label = formatArticleLabel("병역법", "27", "3", {
      withLawName: true,
      withParagraph: true,
    });
    expect(label).toBe("병역법 제27조 제3항");
  });

  it("citation labels omit the paragraph number even when present", () => {
    const label = formatArticleLabel("병역법", "27", "3", {
      withLawName: false,
      withParagraph: false,
    });
    expect(label).toBe("제27조");
  });
});

describe("linkifyText", () => {
  it("returns a single text part when there's no URL", () => {
    expect(linkifyText("이 챗봇은 입영 전 절차만 다룹니다.")).toEqual([
      { text: "이 챗봇은 입영 전 절차만 다룹니다." },
    ]);
  });

  it("splits surrounding text from a bare URL", () => {
    const text = "카투사: https://www.mma.go.kr/contents.do?mc=mma0000525 확인해 주세요";
    expect(linkifyText(text)).toEqual([
      { text: "카투사: " },
      { isLink: true, url: "https://www.mma.go.kr/contents.do?mc=mma0000525" },
      { text: " 확인해 주세요" },
    ]);
  });

  it("keeps a trailing period out of the URL", () => {
    const text = "자세한 내용은 https://www.mma.go.kr/contents.do?mc=mma0000525.";
    expect(linkifyText(text)).toEqual([
      { text: "자세한 내용은 " },
      { isLink: true, url: "https://www.mma.go.kr/contents.do?mc=mma0000525" },
      { text: "." },
    ]);
  });

  it("keeps a wrapping closing paren out of the URL", () => {
    const text = "공고(https://www.mma.go.kr/contents.do?mc=mma0000525)를 확인하세요";
    expect(linkifyText(text)).toEqual([
      { text: "공고(" },
      { isLink: true, url: "https://www.mma.go.kr/contents.do?mc=mma0000525" },
      { text: ")를 확인하세요" },
    ]);
  });

  it("handles the real multi-line OOS message shape (one link per line)", () => {
    const text =
      "카투사/어학병 등 모집병 구체적 지원자격은 이 챗봇의 법령 데이터베이스에는 " +
      "포함되어 있지 않습니다. 정확한 기준은 아래 병무청 모집공고를 확인해 주세요.\n" +
      "- 카투사: https://www.mma.go.kr/contents.do?mc=mma0000525";
    const parts = linkifyText(text);
    expect(parts[parts.length - 1]).toEqual({
      isLink: true,
      url: "https://www.mma.go.kr/contents.do?mc=mma0000525",
    });
    // The newline before "- 카투사" must survive into the text part so
    // white-space: pre-line can still render it as a real line break.
    expect(parts[parts.length - 2]).toEqual({
      text: expect.stringContaining("\n- 카투사: "),
    });
  });

  it("linkifies multiple URLs in the same message independently", () => {
    const text = "카투사: https://a.example/x\n어학병: https://b.example/y";
    expect(linkifyText(text)).toEqual([
      { text: "카투사: " },
      { isLink: true, url: "https://a.example/x" },
      { text: "\n어학병: " },
      { isLink: true, url: "https://b.example/y" },
    ]);
  });
});

describe("mapAnswerSegments", () => {
  it("passes through a null result_index without crashing", () => {
    const parts = mapAnswerSegments([
      { type: "citation", law_name: "병역법", article_no: "70", paragraph_no: null, result_index: null },
    ]);
    expect(parts).toEqual([{ isCite: true, refIndex: null, label: "제70조" }]);
  });

  it("returns [] for null segments", () => {
    expect(mapAnswerSegments(null)).toEqual([]);
  });
});

describe("rankRelevance", () => {
  it("marks every result 'low' when allLow is true", () => {
    const results = [baseResult, { ...baseResult, score: 0.9 }];
    const ranked = rankRelevance(results, false);
    const lowRanked = rankRelevance(results, true);
    expect(ranked.map((r) => r.relevanceLevel)).toEqual(["high", "medium"]);
    expect(lowRanked.map((r) => r.relevanceLevel)).toEqual(["low", "low"]);
  });

  it("ranks by array order (index 0 = high), not by re-sorting on score", () => {
    // results[0] has a lower score than results[1] here on purpose --
    // rankRelevance must not silently re-sort; routes/query.py already
    // guarantees descending order, and this function trusts that.
    const results = [
      { ...baseResult, score: 0.01 },
      { ...baseResult, score: 0.99 },
    ];
    const ranked = rankRelevance(results, false);
    expect(ranked[0].relevanceLevel).toBe("high");
    expect(ranked[1].relevanceLevel).toBe("medium");
  });
});

describe("mapResponseToViewModel", () => {
  it("maps empty results (not oos, not low_confidence) to type 'empty'", () => {
    const raw: QueryApiResponse = {
      out_of_scope: false,
      intent: { user_type_tags: [], topic_tags: [], out_of_scope: false, fallback_message: null, related_lookup: null, anchor_lookups: [] },
      results: [],
      related_scope_info: null,
      low_confidence: false,
      low_confidence_notice: null,
      answer: null,
      answer_segments: null,
      answer_error: null,
    };
    expect(mapResponseToViewModel(raw)).toEqual({ type: "empty" });
  });

  it("maps low_confidence:true to type 'lowConf' with all-low results", () => {
    const raw: QueryApiResponse = {
      out_of_scope: false,
      intent: { user_type_tags: [], topic_tags: [], out_of_scope: false, fallback_message: null, related_lookup: null, anchor_lookups: [] },
      results: [baseResult],
      related_scope_info: null,
      low_confidence: true,
      low_confidence_notice: "확신도가 낮습니다.",
      answer: null,
      answer_segments: null,
      answer_error: null,
    };
    const vm = mapResponseToViewModel(raw);
    expect(vm.type).toBe("lowConf");
    if (vm.type === "lowConf") {
      expect(vm.notice).toBe("확신도가 낮습니다.");
      expect(vm.results[0].relevanceLevel).toBe("low");
    }
  });

  it("maps answer_error (answer null, answer_error set) to hasAnswerError:true with no answerParts", () => {
    const raw: QueryApiResponse = {
      out_of_scope: false,
      intent: { user_type_tags: [], topic_tags: [], out_of_scope: false, fallback_message: null, related_lookup: null, anchor_lookups: [] },
      results: [baseResult],
      related_scope_info: null,
      low_confidence: false,
      low_confidence_notice: null,
      answer: null,
      answer_segments: null,
      answer_error: "GeminiError: quota exceeded",
    };
    const vm = mapResponseToViewModel(raw);
    expect(vm.type).toBe("normal");
    if (vm.type === "normal") {
      expect(vm.hasAnswerError).toBe(true);
      expect(vm.answerParts).toEqual([]);
      expect(vm.results).toHaveLength(1);
    }
  });

  it("maps out_of_scope:true to type 'oos'", () => {
    const raw: QueryApiResponse = {
      out_of_scope: true,
      message: "이 서비스는 입영 전 절차만 다룹니다.",
      intent: { user_type_tags: [], topic_tags: [], out_of_scope: true, fallback_message: "...", related_lookup: null, anchor_lookups: [] },
      related_scope_info: null,
    };
    expect(mapResponseToViewModel(raw)).toEqual({
      type: "oos",
      message: "이 서비스는 입영 전 절차만 다룹니다.",
      relatedScopeInfo: [],
    });
  });
});
