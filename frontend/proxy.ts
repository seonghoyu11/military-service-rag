import createMiddleware from "next-intl/middleware";

import { routing } from "./i18n/routing";

// Next.js 16 renamed middleware.ts -> proxy.ts (export name middleware -> proxy);
// next-intl's createMiddleware() still returns a plain (NextRequest) => NextResponse
// function, which is exactly what a proxy.ts default export expects.
export default createMiddleware(routing);

export const config = {
  matcher: ["/", "/(ko|en)/:path*"],
};
