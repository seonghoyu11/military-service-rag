import type { CSSProperties } from "react";

import { formatArticleLabel } from "@/lib/mapResponse";
import { dotsFor } from "@/lib/styleHelpers";
import type { RankedResult, RelatedScopeItem } from "@/lib/types";

type Item = RankedResult | RelatedScopeItem;

function wrapperStyle(dark: boolean, highlighted: boolean): CSSProperties {
  const bg = dark
    ? highlighted
      ? "rgba(255,255,255,0.1)"
      : "rgba(255,255,255,0.05)"
    : highlighted
      ? "rgba(255,255,255,0.7)"
      : "rgba(255,255,255,0.5)";
  const border = highlighted
    ? dark
      ? "rgba(140,165,220,0.6)"
      : "rgba(27,42,74,0.55)"
    : dark
      ? "rgba(255,255,255,0.12)"
      : "rgba(255,255,255,0.65)";
  const shadow = highlighted
    ? dark
      ? "0 8px 24px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.15)"
      : "0 8px 24px rgba(27,42,74,0.16), inset 0 1px 0 rgba(255,255,255,0.5)"
    : dark
      ? "0 8px 20px rgba(0,0,0,0.3), inset 0 1px 0 rgba(255,255,255,0.1)"
      : "0 8px 20px rgba(20,30,55,0.07), inset 0 1px 0 rgba(255,255,255,0.5)";
  return {
    background: bg,
    backdropFilter: "blur(18px) saturate(180%)",
    WebkitBackdropFilter: "blur(18px) saturate(180%)",
    borderRadius: 16,
    padding: "18px 20px",
    border: `1.5px solid ${border}`,
    boxShadow: shadow,
    transition: "box-shadow .3s ease, border-color .3s ease, background .3s ease",
  };
}

export default function EvidenceCard({
  item,
  domId,
  highlighted,
  dark,
  variant,
}: {
  item: Item;
  domId: string;
  highlighted: boolean;
  dark: boolean;
  variant: "ranked" | "related";
}) {
  const titleLine = formatArticleLabel(item.law_name, item.article_no, item.paragraph_no, {
    withLawName: true,
    withParagraph: true,
  });

  if (variant === "related") {
    return (
      <div id={domId} style={wrapperStyle(dark, highlighted)}>
        <div
          style={{
            fontSize: 15,
            fontWeight: 700,
            color: "var(--related-title)",
            letterSpacing: "-0.01em",
          }}
        >
          {titleLine}{" "}
          <span
            style={{ fontWeight: 400, color: "var(--text-secondary)", fontSize: 12.5 }}
          >
            ({item.article_title})
          </span>
        </div>
        <div
          style={{
            fontSize: 13.5,
            lineHeight: 1.7,
            color: "var(--related-text)",
            marginTop: 8,
            whiteSpace: "pre-wrap",
          }}
        >
          {item.text}
        </div>
      </div>
    );
  }

  const dots = "relevanceLevel" in item ? dotsFor(item.relevanceLevel, dark) : [];

  return (
    <div id={domId} style={wrapperStyle(dark, highlighted)}>
      <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", gap: 10 }}>
        <div
          style={{
            fontSize: 15.5,
            fontWeight: 700,
            color: "var(--card-title)",
            letterSpacing: "-0.01em",
          }}
        >
          {titleLine}
        </div>
        {dots.length > 0 && (
          <div style={{ display: "flex", alignItems: "center", gap: 3, flexShrink: 0 }}>
            {dots.map((d, i) => (
              <div key={i} style={d} />
            ))}
          </div>
        )}
      </div>
      <div style={{ fontSize: 12, color: "var(--card-sub)", marginTop: 2 }}>
        {item.article_title}
      </div>
      <div
        style={{
          fontSize: 13.5,
          lineHeight: 1.75,
          color: "var(--card-text)",
          marginTop: 10,
          fontWeight: 300,
          whiteSpace: "pre-wrap",
        }}
      >
        {item.text}
      </div>
    </div>
  );
}
