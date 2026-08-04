"use client";

import { useTranslations } from "next-intl";

import EvidenceCardList from "./EvidenceCardList";
import type { RelatedScopeItem } from "@/lib/types";

export default function OosCard({
  message,
  relatedScopeInfo,
  msgId,
  dark,
  highlightedKey,
}: {
  message: string;
  relatedScopeInfo: RelatedScopeItem[];
  msgId: string;
  dark: boolean;
  highlightedKey: string | null;
}) {
  const t = useTranslations("oos");

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div
        style={{
          background: "var(--oos-bg)",
          backdropFilter: "blur(16px)",
          WebkitBackdropFilter: "blur(16px)",
          border: "1px solid var(--oos-border)",
          boxShadow: "0 6px 18px var(--oos-shadow)",
          borderRadius: 14,
          padding: "16px 18px",
          fontSize: 13.5,
          color: "var(--oos-text)",
          lineHeight: 1.7,
        }}
      >
        {message}
      </div>
      {relatedScopeInfo.length > 0 && (
        <EvidenceCardList
          items={relatedScopeInfo}
          msgId={msgId}
          variant="related"
          dark={dark}
          highlightedKey={highlightedKey}
          label={t("relatedLabel")}
        />
      )}
    </div>
  );
}
