"use client";

import { useTranslations } from "next-intl";

export default function EmptyResultCard() {
  const t = useTranslations("empty");

  return (
    <div
      style={{
        background: "var(--empty-msg-bg)",
        backdropFilter: "blur(14px)",
        WebkitBackdropFilter: "blur(14px)",
        border: "1px dashed var(--empty-msg-border)",
        borderRadius: 14,
        padding: "24px 18px",
        textAlign: "center",
        fontSize: 13,
        color: "var(--empty-msg-text)",
      }}
    >
      {t("message")}
    </div>
  );
}
