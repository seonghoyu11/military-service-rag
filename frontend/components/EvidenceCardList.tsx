import EvidenceCard from "./EvidenceCard";
import type { RankedResult, RelatedScopeItem } from "@/lib/types";

export default function EvidenceCardList({
  items,
  msgId,
  variant,
  dark,
  highlightedKey,
  label,
}: {
  items: (RankedResult | RelatedScopeItem)[];
  msgId: string;
  variant: "ranked" | "related";
  dark: boolean;
  highlightedKey: string | null;
  label?: string;
}) {
  if (items.length === 0) return null;
  const prefix = variant === "related" ? "r" : "n";

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      {label && (
        <div style={{ fontSize: 12, color: "var(--text-secondary)", margin: "2px 0 -2px 2px" }}>
          {label}
        </div>
      )}
      {items.map((item, i) => {
        const domId = `card-${msgId}-${prefix}-${i}`;
        return (
          <EvidenceCard
            key={domId}
            item={item}
            domId={domId}
            highlighted={highlightedKey === domId}
            dark={dark}
            variant={variant}
          />
        );
      })}
    </div>
  );
}
