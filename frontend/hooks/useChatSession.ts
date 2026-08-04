"use client";

import { useCallback, useEffect, useReducer, useRef, useState } from "react";

import { queryApi } from "@/lib/api";
import {
  EN_HINT_MS,
  FAST_FORWARD_HOLD_MS,
  HIGHLIGHT_MS,
  STAGE_COUNT,
  STAGE_INTERVAL_MS,
} from "@/lib/constants";
import { mapResponseToViewModel } from "@/lib/mapResponse";
import type { ViewModel } from "@/lib/types";

export interface ChatMessage {
  id: string;
  question: string;
  status: "loading" | "done" | "error";
  // 0..STAGE_COUNT-1 while animating; STAGE_COUNT is a "all stages visually
  // done, holding before finalize" sentinel (see the fast-forward path
  // below) -- never persisted past FINALIZE.
  loadingStage: number;
  response: ViewModel | null;
}

type SettleResult =
  | { ok: true; viewModel: ViewModel }
  | { ok: false };

interface InternalMessage extends ChatMessage {
  pendingFinalize: SettleResult | null;
}

type Action =
  | { type: "ADD"; id: string; question: string }
  | { type: "STAGE"; id: string; stage: number }
  | { type: "SETTLED"; id: string; result: SettleResult }
  | { type: "FINALIZE"; id: string };

function applyResult(m: InternalMessage, result: SettleResult): InternalMessage {
  return {
    ...m,
    status: result.ok ? "done" : "error",
    response: result.ok ? result.viewModel : null,
    pendingFinalize: null,
  };
}

function reducer(state: InternalMessage[], action: Action): InternalMessage[] {
  switch (action.type) {
    case "ADD":
      return [
        ...state,
        {
          id: action.id,
          question: action.question,
          status: "loading",
          loadingStage: 0,
          response: null,
          pendingFinalize: null,
        },
      ];
    case "STAGE":
      return state.map((m) =>
        m.id === action.id && m.status === "loading" && m.pendingFinalize === null
          ? { ...m, loadingStage: action.stage }
          : m,
      );
    case "SETTLED":
      return state.map((m) => {
        if (m.id !== action.id || m.status !== "loading") return m;
        if (m.loadingStage >= STAGE_COUNT - 1) {
          // Already animating (or past) the last stage -- real
          // retrieval+generation normally takes multiple seconds, well
          // past the ~2s the stage timers take to reach index 3. Apply
          // immediately, no artificial delay.
          return applyResult(m, action.result);
        }
        // Resolved fast (e.g. an out-of-scope short-circuit that never
        // reaches Gemini) -- snap every stage to "done" and hold briefly
        // rather than jumping straight from stage 0/1/2 to a finished
        // answer, which would read as skipped steps.
        return { ...m, loadingStage: STAGE_COUNT, pendingFinalize: action.result };
      });
    case "FINALIZE":
      return state.map((m) =>
        m.id === action.id && m.pendingFinalize
          ? applyResult(m, m.pendingFinalize)
          : m,
      );
    default:
      return state;
  }
}

export function useChatSession() {
  const [messages, dispatch] = useReducer(reducer, [] as InternalMessage[]);
  const [input, setInput] = useState("");
  const [highlightedKey, setHighlightedKey] = useState<string | null>(null);
  const [showEnHint, setShowEnHint] = useState(false);
  const [dark, setDark] = useState(false);

  const containerRef = useRef<HTMLDivElement | null>(null);
  const stageTimers = useRef<Map<string, ReturnType<typeof setTimeout>[]>>(new Map());
  const finalizeTimers = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());
  const enHintTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const highlightTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  const scrollToBottom = useCallback(() => {
    const el = containerRef.current;
    if (el) el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
  }, []);

  const runLoadingSequence = useCallback((id: string, question: string) => {
    const timers: ReturnType<typeof setTimeout>[] = [];
    [1, 2, 3].forEach((stage, i) => {
      timers.push(
        setTimeout(() => dispatch({ type: "STAGE", id, stage }), STAGE_INTERVAL_MS * (i + 1)),
      );
    });
    stageTimers.current.set(id, timers);

    queryApi(question)
      .then((raw) => {
        dispatch({ type: "SETTLED", id, result: { ok: true, viewModel: mapResponseToViewModel(raw) } });
      })
      .catch(() => {
        dispatch({ type: "SETTLED", id, result: { ok: false } });
      });
  }, []);

  const submitText = useCallback(
    (question: string) => {
      const q = question.trim();
      if (!q) return;
      const id = `${Date.now()}-${Math.random().toString(36).slice(2)}`;
      dispatch({ type: "ADD", id, question: q });
      setInput("");
      scrollToBottom();
      runLoadingSequence(id, q);
    },
    [runLoadingSequence, scrollToBottom],
  );

  const submit = useCallback(() => submitText(input), [submitText, input]);
  const retry = useCallback((question: string) => submitText(question), [submitText]);

  // Fires once per message that enters the fast-forward "hold" state.
  useEffect(() => {
    for (const m of messages) {
      if (m.pendingFinalize && !finalizeTimers.current.has(m.id)) {
        const t = setTimeout(() => {
          dispatch({ type: "FINALIZE", id: m.id });
          finalizeTimers.current.delete(m.id);
        }, FAST_FORWARD_HOLD_MS);
        finalizeTimers.current.set(m.id, t);
      }
    }
  }, [messages]);

  // Auto-scroll whenever a message finishes (mirrors the DC prototype's
  // scrollToBottom() call inside runLoading's final setState callback).
  useEffect(() => {
    if (messages.some((m) => m.status !== "loading")) {
      scrollToBottom();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [messages.map((m) => m.status).join(",")]);

  const tryEn = useCallback(() => {
    setShowEnHint(true);
    clearTimeout(enHintTimer.current);
    enHintTimer.current = setTimeout(() => setShowEnHint(false), EN_HINT_MS);
  }, []);

  const toggleDark = useCallback(() => setDark((d) => !d), []);

  const scrollToCard = useCallback((msgId: string, refIndex: number) => {
    const domId = `card-${msgId}-n-${refIndex}`;
    const el = document.getElementById(domId);
    const container = containerRef.current;
    if (el && container) {
      const cRect = container.getBoundingClientRect();
      const eRect = el.getBoundingClientRect();
      const target = eRect.top - cRect.top + container.scrollTop - 24;
      container.scrollTo({ top: target, behavior: "smooth" });
    }
    setHighlightedKey(domId);
    clearTimeout(highlightTimer.current);
    highlightTimer.current = setTimeout(() => setHighlightedKey(null), HIGHLIGHT_MS);
  }, []);

  useEffect(() => {
    const stageTimersSnapshot = stageTimers.current;
    const finalizeTimersSnapshot = finalizeTimers.current;
    return () => {
      stageTimersSnapshot.forEach((timers) => timers.forEach(clearTimeout));
      finalizeTimersSnapshot.forEach(clearTimeout);
      clearTimeout(enHintTimer.current);
      clearTimeout(highlightTimer.current);
    };
  }, []);

  return {
    messages: messages as ChatMessage[],
    input,
    setInput,
    submit,
    submitText,
    retry,
    highlightedKey,
    showEnHint,
    tryEn,
    dark,
    toggleDark,
    containerRef,
    scrollToCard,
  };
}
