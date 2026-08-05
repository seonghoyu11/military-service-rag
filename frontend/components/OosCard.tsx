"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";

import EvidenceCardList from "./EvidenceCardList";
import EvidenceToggleButton from "./EvidenceToggleButton";
import LinkifiedText from "./LinkifiedText";
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
  // Local to this card, same rationale as MessageItem's `revealed` state for
  // the "normal" evidence toggle: OOS related-article cards default to
  // hidden so the fallback message itself (the actual point of an OOS
  // response) isn't pushed off-screen by an always-expanded card list.
  const [revealed, setRevealed] = useState(false);

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
          whiteSpace: "pre-line",
        }}
      >
        <LinkifiedText text={message} />
      </div>
      {relatedScopeInfo.length > 0 && (
        <EvidenceToggleButton
          count={relatedScopeInfo.length}
          revealed={revealed}
          onClick={() => setRevealed((r) => !r)}
          namespace="oos"
        />
      )}
      {revealed && relatedScopeInfo.length > 0 && (
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
