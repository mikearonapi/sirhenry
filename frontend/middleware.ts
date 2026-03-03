import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

/**
 * Pre-launch middleware.
 * - On Vercel (production): only the landing page is accessible, everything else 404s.
 * - Locally: all routes are accessible for development.
 */
export function middleware(request: NextRequest) {
  if (!process.env.VERCEL) {
    return NextResponse.next();
  }

  const { pathname } = request.nextUrl;

  if (
    pathname === "/" ||
    pathname.startsWith("/_next") ||
    pathname === "/favicon.ico"
  ) {
    return NextResponse.next();
  }

  return new NextResponse(null, { status: 404 });
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
