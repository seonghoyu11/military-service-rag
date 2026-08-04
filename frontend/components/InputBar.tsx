"use client";

import { useTranslations } from "next-intl";

export default function InputBar({
  value,
  onChange,
  onSubmit,
  disabled,
  dark,
}: {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  disabled: boolean;
  dark: boolean;
}) {
  const t = useTranslations("input");

  return (
    <div style={{ position: "relative", zIndex: 1, padding: "10px 16px calc(14px + env(safe-area-inset-bottom))" }}>
      <div
        style={{
          maxWidth: 760,
          margin: "0 auto",
          display: "flex",
          alignItems: "center",
          gap: 6,
          background: "var(--input-wrap-bg)",
          backdropFilter: "blur(26px) saturate(180%)",
          WebkitBackdropFilter: "blur(26px) saturate(180%)",
          border: "1px solid var(--input-wrap-border)",
          borderRadius: 999,
          padding: "6px 6px 6px 20px",
          boxShadow: "0 14px 34px var(--input-wrap-shadow), inset 0 1px 0 rgba(255,255,255,0.2)",
        }}
      >
        <input
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !disabled) onSubmit();
          }}
          placeholder={t("placeholder")}
          style={{
            flex: 1,
            padding: "11px 0",
            border: "none",
            background: "transparent",
            fontSize: 15,
            outline: "none",
            fontFamily: "inherit",
            color: dark ? "#EDEDEF" : "#16181D",
          }}
        />
        <div
          onClick={() => {
            if (!disabled) onSubmit();
          }}
          style={{
            width: 40,
            height: 40,
            flexShrink: 0,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            background: disabled
              ? dark
                ? "rgba(255,255,255,0.15)"
                : "rgba(183,189,196,0.9)"
              : "linear-gradient(160deg, rgba(46,64,102,0.95), rgba(18,29,52,0.95))",
            color: "#fff",
            borderRadius: "50%",
            fontWeight: 700,
            fontSize: 17,
            border: "1px solid rgba(255,255,255,0.2)",
            boxShadow: "inset 0 1px 0 rgba(255,255,255,0.25), 0 6px 16px rgba(20,30,55,0.2)",
            cursor: disabled ? "default" : "pointer",
          }}
        >
          ➤
        </div>
      </div>
    </div>
  );
}
