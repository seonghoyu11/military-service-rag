"use client";

import { useTranslations } from "next-intl";

import { useTypewriter } from "@/hooks/useTypewriter";
import { circleStyleFor, labelStyleFor, type StageStatus } from "@/lib/styleHelpers";

function StageRow({
  status,
  label,
  dark,
}: {
  status: StageStatus;
  label: string;
  dark: boolean;
}) {
  const typed = useTypewriter(label, status === "current");
  const display = status === "done" ? label : status === "current" ? typed : "";
  const showCursor = status === "current" && typed.length < label.length;

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
      <div style={circleStyleFor(status, dark)}>{status === "done" ? "✓" : ""}</div>
      <div style={labelStyleFor(status, dark)}>
        {display}
        {showCursor && <span style={{ opacity: 0.5 }}>|</span>}
      </div>
    </div>
  );
}

export default function LoadingStages({
  loadingStage,
  dark,
}: {
  loadingStage: number;
  dark: boolean;
}) {
  const t = useTranslations("loading");
  const labels = t.raw("stages") as string[];

  return (
    <div
      style={{
        background: "var(--loading-bg)",
        backdropFilter: "blur(18px) saturate(180%)",
        WebkitBackdropFilter: "blur(18px) saturate(180%)",
        border: "1px solid var(--loading-border)",
        boxShadow: "0 8px 24px var(--loading-shadow), inset 0 1px 0 rgba(255,255,255,0.15)",
        borderRadius: 16,
        padding: "20px 20px",
        display: "flex",
        flexDirection: "column",
        gap: 14,
      }}
    >
      {labels.map((label, i) => {
        const status: StageStatus = i < loadingStage ? "done" : i === loadingStage ? "current" : "pending";
        return <StageRow key={i} status={status} label={label} dark={dark} />;
      })}
    </div>
  );
}
