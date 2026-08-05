import type {
  AnswerPart,
  AnswerSegment,
  LinkPart,
  QueryApiResponse,
  RankedResult,
  ResultItem,
  ViewModel,
} from "./types";

/**
 * Single shared formatter for both evidence-card titles and citation chip
 * labels, so the "별표 (table) sources must never render as 제별표N조" fix
 * lives in exactly one place -- this is the same bug
 * generation/answer.py's _format_articles() already had to fix on the
 * backend once, and DutyCompass.dc.html's buildCard() had it unconditionally
 * ("`${law_name} 제${article_no}조${paragraphStr}`").
 *
 * Paragraph numbers are rendered as plain "제N항" text, not circled
 * numerals -- DutyCompass.dc.html's buildCard() itself uses
 * `paragraphStr = ' 제${c.paragraph_no}항'`, plain text, confirmed by
 * re-reading the source (an earlier instruction assumed circled numerals
 * ①②③ "matching card.titleLine" -- that assumption didn't match the actual
 * source, resolved in favor of the source).
 *
 * Citation chip labels omit both the law name and the paragraph number
 * (e.g. "제70조", never "병역법 제70조 제3항") -- matching every example in
 * mock-data.js's answerParts, which never include either even when the
 * cited result has a non-"all" paragraph_no. This doesn't lose information:
 * refIndex still ties the chip to the exact result card regardless of what
 * the label says.
 *
 * Second 별표 wrinkle, only caught by actually looking at a rendered
 * screenshot (not just grepping for "제별표"): `law_name` for table-shaped
 * chunks already contains the full "별표 N" text (e.g. "병역법 시행령 별표
 * 3"), so naively prepending it before `article_no` ("별표3") produced a
 * visible duplicate -- "병역법 시행령 별표 3 별표3". Fixed by returning just
 * `lawName` for the withLawName case when article_no starts with "별표".
 */
export function formatArticleLabel(
  lawName: string,
  articleNo: string,
  paragraphNo: string | null,
  options: { withLawName: boolean; withParagraph: boolean },
): string {
  if (articleNo.startsWith("별표")) {
    // law_name for table-shaped chunks already embeds "별표 N" (e.g.
    // "병역법 시행령 별표 3") -- `${lawName} ${articleNo}` would duplicate
    // it ("병역법 시행령 별표 3 별표3"). Same discovery already made on the
    // backend, see generation/citation_parser.py's module docstring.
    return options.withLawName ? lawName : articleNo;
  }
  const namePart = options.withLawName ? `${lawName} ` : "";
  const paragraphPart =
    options.withParagraph && paragraphNo && paragraphNo !== "all"
      ? ` 제${paragraphNo}항`
      : "";
  return `${namePart}제${articleNo}조${paragraphPart}`;
}

// ")" is excluded from the URL body itself (not just trimmed after the
// fact) so a link wrapped in parens -- "공고(https://...)를 확인" -- doesn't
// swallow the closing paren and whatever text touches it with no space in
// between ("...0525)를").
const URL_PATTERN = /https?:\/\/[^\s)]+/g;
// Sentence punctuation that commonly rides along on the match when it isn't
// followed by whitespace or ")" (a period ending the sentence) -- not part
// of the URL itself, so it must fall back into the surrounding text part
// instead of getting swallowed into the href.
const TRAILING_PUNCTUATION = /[.,]+$/;

/**
 * Splits OOS fallback messages (plain text from the backend, e.g.
 * intent.fallback_message) into text/link segments so URLs render as
 * clickable `<a>` tags. Mirrors mapAnswerSegments' text-vs-chip split above
 * -- kept as a plain string->segments function here (not wired through the
 * backend) since these messages are free-form guidance text, not
 * structured citations the backend already knows the boundaries of.
 */
export function linkifyText(text: string): LinkPart[] {
  const parts: LinkPart[] = [];
  let lastIndex = 0;

  for (const match of text.matchAll(URL_PATTERN)) {
    const start = match.index ?? 0;
    const trailingMatch = match[0].match(TRAILING_PUNCTUATION);
    const url = trailingMatch ? match[0].slice(0, -trailingMatch[0].length) : match[0];
    if (!url) continue;

    if (start > lastIndex) {
      parts.push({ text: text.slice(lastIndex, start) });
    }
    parts.push({ isLink: true, url });
    lastIndex = start + url.length;
  }

  if (lastIndex < text.length) {
    parts.push({ text: text.slice(lastIndex) });
  }

  return parts;
}

export function mapAnswerSegments(segments: AnswerSegment[] | null): AnswerPart[] {
  if (!segments) return [];
  return segments.map((seg) => {
    if (seg.type === "text") {
      return { isText: true, text: seg.content };
    }
    return {
      isCite: true,
      refIndex: seg.result_index,
      label: formatArticleLabel(seg.law_name, seg.article_no, seg.paragraph_no, {
        withLawName: false,
        withParagraph: false,
      }),
    };
  });
}

/**
 * Per-message relative ranking, NOT an absolute score threshold -- raw
 * reranker scores aren't comparable across questions (see
 * docs/eval_results.md and routes/query.py's LOW_CONFIDENCE_THRESHOLD
 * comment: a 0.11 score is a true positive for one question, a 0.006 score
 * is a true positive for another). This is an intentionally temporary
 * heuristic until a better per-message confidence signal exists.
 *
 * Assumes `results` arrives already sorted descending by score, which
 * routes/query.py guarantees (reranker + boost passes are always
 * `sorted(..., key=lambda pair: -pair[1])`) -- so "index 0" and "top score"
 * are the same thing here.
 */
export function rankRelevance(
  results: ResultItem[],
  allLow: boolean,
): RankedResult[] {
  if (allLow) {
    return results.map((r) => ({ ...r, relevanceLevel: "low" as const }));
  }
  return results.map((r, i) => ({
    ...r,
    relevanceLevel: i === 0 ? ("high" as const) : ("medium" as const),
  }));
}

export function mapResponseToViewModel(raw: QueryApiResponse): ViewModel {
  if (raw.out_of_scope) {
    return {
      type: "oos",
      message: raw.message,
      relatedScopeInfo: raw.related_scope_info ?? [],
    };
  }

  if (raw.low_confidence) {
    return {
      type: "lowConf",
      notice: raw.low_confidence_notice ?? "",
      intent: raw.intent,
      results: rankRelevance(raw.results, true),
    };
  }

  if (raw.results.length === 0) {
    return { type: "empty" };
  }

  // New case (didn't exist in mock-data.js): retrieval succeeded but Gemini
  // generation failed -- show the results, skip the answer card, tell the
  // user generation failed rather than silently rendering nothing.
  const hasAnswerError = Boolean(raw.answer_error) && raw.answer === null;

  return {
    type: "normal",
    intent: raw.intent,
    results: rankRelevance(raw.results, false),
    hasAnswerError,
    answerParts: hasAnswerError
      ? []
      : mapAnswerSegments(raw.answer_segments),
  };
}
