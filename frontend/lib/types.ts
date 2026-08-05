// Raw shapes returned by POST /api/query -- confirmed against
// backend/routes/query.py::answer_question() and
// backend/generation/citation_parser.py::parse_citations().
import type { RelevanceLevel } from "./styleHelpers";

export interface IntentInfo {
  user_type_tags: string[];
  topic_tags: string[];
  out_of_scope: boolean;
  fallback_message: string | null;
  related_lookup: unknown;
  anchor_lookups: unknown[];
}

export interface ResultItem {
  law_name: string;
  article_no: string;
  article_title: string;
  // "all" is a real sentinel value meaning "no specific paragraph" -- must
  // not be rendered as a paragraph number.
  paragraph_no: string;
  text: string;
  score: number;
}

export interface RelatedScopeItem {
  law_name: string;
  article_no: string;
  article_title: string;
  paragraph_no: string;
  text: string;
}

export interface AnswerSegmentText {
  type: "text";
  content: string;
}

export interface AnswerSegmentCitation {
  type: "citation";
  law_name: string;
  article_no: string;
  paragraph_no: string | null;
  // null when the citation phrase couldn't be matched to a result -- must
  // render as plain, non-clickable text, not crash.
  result_index: number | null;
}

export type AnswerSegment = AnswerSegmentText | AnswerSegmentCitation;

export interface QueryApiResponseOos {
  out_of_scope: true;
  message: string;
  intent: IntentInfo;
  related_scope_info: RelatedScopeItem[] | null;
}

export interface QueryApiResponseInScope {
  out_of_scope: false;
  intent: IntentInfo;
  results: ResultItem[];
  related_scope_info: null;
  low_confidence: boolean;
  low_confidence_notice: string | null;
  answer: string | null;
  answer_segments: AnswerSegment[] | null;
  answer_error: string | null;
}

export type QueryApiResponse = QueryApiResponseOos | QueryApiResponseInScope;

// ---- View-model shapes the components consume (built by lib/mapResponse.ts) ----

export interface RankedResult extends ResultItem {
  relevanceLevel: RelevanceLevel;
}

export interface AnswerPartText {
  isText: true;
  isCite?: false;
  text: string;
}

export interface AnswerPartCitation {
  isCite: true;
  isText?: false;
  refIndex: number | null;
  label: string;
}

export type AnswerPart = AnswerPartText | AnswerPartCitation;

export interface LinkPartText {
  isLink?: false;
  text: string;
}

export interface LinkPartLink {
  isLink: true;
  url: string;
}

export type LinkPart = LinkPartText | LinkPartLink;

export type ViewModel =
  | { type: "oos"; message: string; relatedScopeInfo: RelatedScopeItem[] }
  | { type: "lowConf"; notice: string; intent: IntentInfo; results: RankedResult[] }
  | { type: "empty" }
  | {
      type: "normal";
      intent: IntentInfo;
      results: RankedResult[];
      hasAnswerError: boolean;
      answerParts: AnswerPart[];
    }
  | { type: "error" };
