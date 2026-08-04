import type { Metadata } from "next";
import { hasLocale } from "next-intl";
import { NextIntlClientProvider } from "next-intl";
import { notFound } from "next/navigation";

import { routing } from "@/i18n/routing";
import "../globals.css";

export const metadata: Metadata = {
  title: "DutyCompass",
  description: "재외국민 병역 안내 챗봇",
};

// This IS the root layout (every route lives under app/[locale]/) -- there
// is no separate top-level app/layout.tsx, per next-intl's App Router setup.
export default async function RootLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  if (!hasLocale(routing.locales, locale)) {
    notFound();
  }

  return (
    <html lang={locale} className="h-full">
      <head>
        <link
          rel="stylesheet"
          crossOrigin="anonymous"
          href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css"
        />
      </head>
      <body className="h-full min-h-full">
        <NextIntlClientProvider>{children}</NextIntlClientProvider>
      </body>
    </html>
  );
}
