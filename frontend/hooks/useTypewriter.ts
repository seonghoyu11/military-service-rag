"use client";

import { useEffect, useState } from "react";

import { TYPE_CHAR_MS } from "@/lib/constants";

// Generic per-character reveal, ported from DutyCompass.dc.html's
// typeStage(). Only types while `active`; resets to empty otherwise so a
// row that becomes inactive (e.g. was "current", now "done") doesn't keep
// mid-typed state around -- the caller decides what to show for non-active
// statuses (full text for "done", nothing for "pending").
export function useTypewriter(text: string, active: boolean): string {
  // Reset is done as a state adjustment during render (React's documented
  // pattern for "reset state when a prop changes"), not inside the effect
  // below -- calling setState synchronously at the top of an effect body
  // trips react-hooks/set-state-in-effect and risks an extra unnecessary
  // commit under Strict Mode's double-invoke.
  const [resetKey, setResetKey] = useState({ text, active });
  const [len, setLen] = useState(0);
  if (resetKey.text !== text || resetKey.active !== active) {
    setResetKey({ text, active });
    setLen(0);
  }

  useEffect(() => {
    if (!active) return;
    let n = 0;
    const interval = setInterval(() => {
      n++;
      setLen(n);
      if (n >= text.length) clearInterval(interval);
    }, TYPE_CHAR_MS);
    return () => clearInterval(interval);
  }, [text, active]);

  return text.slice(0, len);
}
