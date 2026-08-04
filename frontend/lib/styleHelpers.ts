// Ported from DutyCompass.dc.html's circleStyleFor/labelStyleFor/dotsFor,
// converted from inline style strings to CSSProperties objects (idiomatic
// React) with identical values/logic.
import type { CSSProperties } from "react";

export type StageStatus = "pending" | "current" | "done";
export type RelevanceLevel = "low" | "medium" | "high";

export function circleStyleFor(status: StageStatus, dark: boolean): CSSProperties {
  const base: CSSProperties = {
    width: 20,
    height: 20,
    borderRadius: "50%",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: 11,
    color: "#fff",
    flexShrink: 0,
    transition: "background .3s ease",
  };
  if (status === "done") {
    return {
      ...base,
      background:
        "linear-gradient(160deg, rgba(46,64,102,0.95), rgba(18,29,52,0.95))",
      boxShadow: "inset 0 1px 0 rgba(255,255,255,0.25)",
    };
  }
  if (status === "current") {
    return {
      ...base,
      background:
        "linear-gradient(160deg, rgba(46,64,102,0.95), rgba(18,29,52,0.95))",
      boxShadow: "inset 0 1px 0 rgba(255,255,255,0.25)",
      animation: "dcPulse 1.1s ease-in-out infinite",
    };
  }
  return {
    ...base,
    background: dark ? "rgba(255,255,255,0.1)" : "rgba(231,231,228,0.7)",
  };
}

export function labelStyleFor(status: StageStatus, dark: boolean): CSSProperties {
  if (status === "done") {
    return { fontSize: 13.5, color: dark ? "#8C9096" : "#9A9EA2" };
  }
  if (status === "current") {
    return {
      fontSize: 14,
      color: dark ? "#9DB4E8" : "#1B2A4A",
      fontWeight: 700,
    };
  }
  return { fontSize: 13.5, color: dark ? "#4D5157" : "#C7CACC" };
}

export function dotsFor(level: RelevanceLevel, dark: boolean): CSSProperties[] {
  const count = level === "high" ? 3 : level === "medium" ? 2 : 1;
  return [0, 1, 2].map((i) => ({
    width: 5,
    height: 5,
    borderRadius: "50%",
    background:
      i < count
        ? dark
          ? "#9DB4E8"
          : "#1B2A4A"
        : dark
          ? "rgba(255,255,255,0.14)"
          : "rgba(226,226,222,0.8)",
  }));
}
