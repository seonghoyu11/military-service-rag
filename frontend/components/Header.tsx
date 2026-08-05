"use client";

import { useLocale, useTranslations } from "next-intl";

import { usePathname, useRouter } from "@/i18n/routing";

export default function Header({
  dark,
  onToggleDark,
}: {
  dark: boolean;
  onToggleDark: () => void;
}) {
  const t = useTranslations();
  const locale = useLocale();
  const router = useRouter();
  const pathname = usePathname();

  const switchLocale = (nextLocale: "ko" | "en") => {
    if (nextLocale === locale) return;
    router.replace(pathname, { locale: nextLocale });
  };

  return (
    <div
      style={{
        position: "sticky",
        top: 0,
        zIndex: 20,
        background: "var(--header-bg)",
        backdropFilter: "blur(22px) saturate(180%)",
        WebkitBackdropFilter: "blur(22px) saturate(180%)",
        borderBottom: "1px solid var(--header-border)",
        boxShadow: "0 4px 24px var(--header-shadow)",
      }}
    >
      <div
        style={{
          maxWidth: 760,
          margin: "0 auto",
          padding: "14px 20px 12px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 12,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div
            style={{
              width: 30,
              height: 30,
              borderRadius: 9,
              background:
                "linear-gradient(160deg, rgba(46,64,102,0.95), rgba(18,29,52,0.95))",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "#fff",
              fontWeight: 700,
              fontSize: 13,
              letterSpacing: "-0.02em",
              boxShadow:
                "inset 0 1px 0 rgba(255,255,255,0.3), 0 3px 8px rgba(20,30,55,0.25)",
            }}
          >
            DC
          </div>
          <div>
            <div
              style={{
                fontSize: 15,
                fontWeight: 700,
                letterSpacing: "-0.01em",
                color: "var(--text-primary)",
              }}
            >
              {t("app.title")}
            </div>
            <div style={{ fontSize: 11, color: "var(--text-secondary)" }}>
              {t("app.subtitle")}
            </div>
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <div
            onClick={onToggleDark}
            style={{
              width: 38,
              height: 22,
              borderRadius: 999,
              background: "var(--pill-wrap-bg)",
              border: "1px solid var(--pill-wrap-border)",
              boxShadow: "inset 0 1px 3px rgba(0,0,0,0.15)",
              cursor: "pointer",
              position: "relative",
            }}
          >
            <div
              style={{
                position: "absolute",
                top: 2,
                left: dark ? 18 : 2,
                width: 18,
                height: 18,
                borderRadius: "50%",
                background: dark
                  ? "linear-gradient(160deg, #9DB4E8, #4D6BAE)"
                  : "#fff",
                boxShadow: "0 1px 3px rgba(0,0,0,0.3)",
                transition: "left .2s ease, background .2s ease",
              }}
            />
          </div>
          <div
            style={{
              position: "relative",
              display: "flex",
              alignItems: "center",
              gap: 2,
              background: "var(--pill-wrap-bg)",
              backdropFilter: "blur(14px) saturate(180%)",
              WebkitBackdropFilter: "blur(14px) saturate(180%)",
              border: "1px solid var(--pill-wrap-border)",
              borderRadius: 999,
              padding: 4,
              boxShadow:
                "0 4px 14px var(--pill-wrap-shadow), inset 0 1px 0 rgba(255,255,255,0.15)",
            }}
          >
            <div
              className={locale === "ko" ? undefined : "dc-lang-pill"}
              onClick={() => switchLocale("ko")}
              style={{
                padding: "5px 13px",
                borderRadius: 999,
                fontSize: 12,
                fontWeight: locale === "ko" ? 700 : 600,
                background:
                  locale === "ko"
                    ? "linear-gradient(180deg, rgba(46,64,102,0.95), rgba(20,33,58,0.95))"
                    : "transparent",
                color: locale === "ko" ? "#FFFFFF" : "var(--pill-inactive)",
                boxShadow:
                  locale === "ko"
                    ? "0 1px 3px rgba(0,0,0,0.18), inset 0 1px 0 rgba(255,255,255,0.25)"
                    : "none",
                cursor: "pointer",
              }}
            >
              {t("langToggle.ko")}
            </div>
            <div
              className={locale === "en" ? undefined : "dc-lang-pill"}
              onClick={() => switchLocale("en")}
              style={{
                padding: "5px 13px",
                borderRadius: 999,
                fontSize: 12,
                fontWeight: locale === "en" ? 700 : 600,
                background:
                  locale === "en"
                    ? "linear-gradient(180deg, rgba(46,64,102,0.95), rgba(20,33,58,0.95))"
                    : "transparent",
                color: locale === "en" ? "#FFFFFF" : "var(--pill-inactive)",
                boxShadow:
                  locale === "en"
                    ? "0 1px 3px rgba(0,0,0,0.18), inset 0 1px 0 rgba(255,255,255,0.25)"
                    : "none",
                cursor: "pointer",
              }}
            >
              {t("langToggle.en")}
            </div>
          </div>
        </div>
      </div>
      <div
        style={{
          background: "var(--disclaimer-bg)",
          borderTop: "1px solid var(--disclaimer-border)",
          padding: "7px 20px",
        }}
      >
        <div
          style={{
            maxWidth: 760,
            margin: "0 auto",
            fontSize: 11,
            color: "var(--disclaimer-text)",
            lineHeight: 1.5,
            textAlign: "center",
          }}
        >
          {t("disclaimer")}
        </div>
      </div>
    </div>
  );
}
