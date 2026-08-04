import { describe, expect, it } from "vitest";

import {
  formatArticleLabel,
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
