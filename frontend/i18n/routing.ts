import { createNavigation } from "next-intl/navigation";
import { defineRouting } from "next-intl/routing";

// localePrefix: "always" keeps /ko and /en symmetric from day one -- no
// "default locale has no prefix" special case to unwind later when real
// English messages are filled in (see docs/architecture.md's next-intl
// requirement + docs/devlog.md 2026-08-03 entry for why this is scaffolded
// now with only ko/en.json content identical).
export const routing = defineRouting({
  locales: ["ko", "en"],
  defaultLocale: "ko",
  localePrefix: "always",
});

export const { Link, redirect, usePathname, useRouter } =
  createNavigation(routing);
