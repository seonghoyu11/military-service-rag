import type { CSSProperties, ReactNode } from "react";

import { themeToCssVars } from "@/lib/theme";

export default function ThemeRoot({
  dark,
  children,
}: {
  dark: boolean;
  children: ReactNode;
}) {
  const style: CSSProperties = {
    height: "100vh",
    position: "relative",
    overflow: "hidden",
    display: "flex",
    flexDirection: "column",
    background: "var(--bg-page)",
    color: "var(--text-primary)",
    transition: "background .25s ease, color .25s ease",
    ...themeToCssVars(dark),
  };
  return <div style={style}>{children}</div>;
}
