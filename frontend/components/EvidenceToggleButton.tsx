"use client";

import { useTranslations } from "next-intl";

export default function EvidenceToggleButton({
  count,
  revealed,
  onClick,
}: {
  count: number;
  revealed: boolean;
  onClick: () => void;
}) {
  const t = useTranslations("evidence");

  return (
    <div
      onClick={onClick}
      style={{
        alignSelf: "flex-start",
        background: "var(--toggle-btn-bg)",
        backdropFilter: "blur(12px)",
        WebkitBackdropFilter: "blur(12px)",
        border: "1px solid var(--toggle-btn-border)",
        color: "var(--toggle-btn-text)",
        fontSize: 12.5,
        fontWeight: 600,
        padding: "7px 14px",
        borderRadius: 999,
        cursor: "pointer",
        boxShadow: "0 3px 10px var(--toggle-btn-shadow)",
      }}
    >
      {revealed ? t("hideToggle") : t("showToggle", { count })}
    </div>
  );
}
