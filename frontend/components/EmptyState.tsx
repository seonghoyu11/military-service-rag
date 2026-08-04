"use client";

import { useTranslations } from "next-intl";

export default function EmptyState({ onPick }: { onPick: (question: string) => void }) {
  const t = useTranslations();
  const questions = t.raw("sampleQuestions") as string[];

  return (
    <div
      style={{
        padding: "56px 10px 8px",
        textAlign: "center",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: 14,
      }}
    >
      <div
        style={{
          width: 48,
          height: 48,
          borderRadius: 16,
          background: "var(--chip-bg)",
          backdropFilter: "blur(14px)",
          WebkitBackdropFilter: "blur(14px)",
          border: "1px solid var(--chip-border)",
          boxShadow: "0 6px 18px var(--header-shadow), inset 0 1px 0 rgba(255,255,255,0.2)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <div style={{ width: 18, height: 18, borderRadius: "50%", border: "2.5px solid #1B2A4A" }} />
      </div>
      <div style={{ fontSize: 17, fontWeight: 700, letterSpacing: "-0.01em", color: "var(--text-primary)" }}>
        {t("emptyState.heading")}
      </div>
      <div style={{ fontSize: 13, color: "var(--text-secondary)", maxWidth: 320, lineHeight: 1.65 }}>
        {t("emptyState.subtext")}
      </div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 8, justifyContent: "center", marginTop: 10 }}>
        {questions.map((q, i) => (
          <div
            key={i}
            className="dc-chip"
            onClick={() => onPick(q)}
            style={{
              background: "var(--chip-bg)",
              backdropFilter: "blur(12px)",
              WebkitBackdropFilter: "blur(12px)",
              border: "1px solid var(--chip-border)",
              boxShadow: "0 3px 10px var(--header-shadow)",
              borderRadius: 999,
              padding: "9px 15px",
              fontSize: 12.5,
              color: "var(--chip-text)",
              cursor: "pointer",
            }}
          >
            {q}
          </div>
        ))}
      </div>
    </div>
  );
}
