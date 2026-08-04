"use client";

import { useAnswerReveal } from "@/hooks/useAnswerReveal";
import type { AnswerPart } from "@/lib/types";
import CitationChip from "./CitationChip";

// Ported from DutyCompass.dc.html's renderVals() answer-part mapping: text
// parts are progressively truncated as `revealed` grows; citation parts pop
// in whole once the reveal counter passes their unit position (not
// partially revealed) and are omitted entirely before that.
export default function AnswerCard({
  parts,
  onCite,
}: {
  parts: AnswerPart[];
  onCite: (refIndex: number) => void;
}) {
  const revealed = useAnswerReveal(parts);

  // Threaded via reduce (not a mutable running counter) so this stays pure
  // during render -- react-hooks/immutability flags reassigning a captured
  // variable across .map() iterations.
  const visible = parts
    .reduce<{ used: number; rows: Array<
      | { kind: "cite"; key: string; part: Extract<AnswerPart, { isCite: true }>; show: boolean }
      | { kind: "text"; key: string; text: string; show: true }
    > }>(
      (acc, part, i) => {
        if (part.isCite) {
          const unitPos = acc.used;
          return {
            used: acc.used + 1,
            rows: [...acc.rows, { kind: "cite", key: `c-${i}`, part, show: revealed > unitPos }],
          };
        }
        const remaining = Math.max(0, revealed - acc.used);
        const shown = part.text.slice(0, remaining);
        return {
          used: acc.used + part.text.length,
          rows: [...acc.rows, { kind: "text", key: `t-${i}`, text: shown, show: true }],
        };
      },
      { used: 0, rows: [] },
    )
    .rows.filter((p) => p.show);

  return (
    <div
      style={{
        background: "var(--answer-bg)",
        backdropFilter: "blur(18px) saturate(180%)",
        WebkitBackdropFilter: "blur(18px) saturate(180%)",
        border: "1px solid var(--answer-border)",
        boxShadow: "0 8px 24px var(--answer-shadow), inset 0 1px 0 rgba(255,255,255,0.15)",
        borderRadius: 14,
        padding: "16px 18px",
        fontSize: 14,
        lineHeight: 1.75,
        color: "var(--answer-text)",
      }}
    >
      {visible.map((p) =>
        p.kind === "cite" ? (
          <CitationChip key={p.key} label={p.part.label} refIndex={p.part.refIndex} onClick={onCite} />
        ) : (
          <span key={p.key}>{p.text}</span>
        ),
      )}
    </div>
  );
}
