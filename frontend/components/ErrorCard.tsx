"use client";

import { useTranslations } from "next-intl";

export default function ErrorCard({ onRetry }: { onRetry: () => void }) {
  const t = useTranslations("error");

  return (
    <div
      style={{
        background: "var(--error-bg)",
        backdropFilter: "blur(16px)",
        WebkitBackdropFilter: "blur(16px)",
        border: "1px solid var(--error-border)",
        boxShadow: "0 6px 18px var(--error-shadow)",
        borderRadius: 14,
        padding: "16px 18px",
        display: "flex",
        flexDirection: "column",
        gap: 10,
      }}
    >
      <div style={{ fontSize: 13.5, color: "var(--error-text)", lineHeight: 1.6 }}>
        {t("message")}
      </div>
      <div
        onClick={onRetry}
        style={{
          alignSelf: "flex-start",
          background:
            "linear-gradient(160deg, rgba(180,60,42,0.9), rgba(140,40,26,0.92))",
          color: "#fff",
          fontSize: 12.5,
          fontWeight: 600,
          padding: "7px 14px",
          borderRadius: 8,
          cursor: "pointer",
          boxShadow: "inset 0 1px 0 rgba(255,255,255,0.2)",
        }}
      >
        {t("retry")}
      </div>
    </div>
  );
}
