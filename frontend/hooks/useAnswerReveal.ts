"use client";

import { useEffect, useState } from "react";

import { ANSWER_REVEAL_TICK_MS, ANSWER_REVEAL_UNITS_PER_TICK } from "@/lib/constants";
import type { AnswerPart } from "@/lib/types";

function totalUnits(parts: AnswerPart[]): number {
  return parts.reduce((sum, p) => sum + (p.isText ? p.text.length : 1), 0);
}

// Ported from DutyCompass.dc.html's typeAnswer(): a citation chip counts as
// 1 reveal unit, text counts 1 unit per character, advancing
// ANSWER_REVEAL_UNITS_PER_TICK units every ANSWER_REVEAL_TICK_MS. Runs once
// per mount (messages are append-only and never remount), matching "the
// answer types itself in once, right when it first arrives."
export function useAnswerReveal(parts: AnswerPart[]): number {
  // Reset as a render-time state adjustment (see useTypewriter for the same
  // pattern/rationale) rather than a leading setState inside the effect.
  const [resetKey, setResetKey] = useState(parts);
  const [revealed, setRevealed] = useState(0);
  if (resetKey !== parts) {
    setResetKey(parts);
    setRevealed(0);
  }

  useEffect(() => {
    const total = totalUnits(parts);
    if (total === 0) return;
    let n = 0;
    const interval = setInterval(() => {
      n += ANSWER_REVEAL_UNITS_PER_TICK;
      setRevealed(Math.min(n, total));
      if (n >= total) clearInterval(interval);
    }, ANSWER_REVEAL_TICK_MS);
    return () => clearInterval(interval);
  }, [parts]);

  return revealed;
}
