import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

/**
 * Pre-launch middleware: only the public landing page is accessible.
 * All app routes return 404 so they are not discoverable.
 */
export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Allow: landing page, static assets, Next.js internals, favicon
  if (
    pathname === "/" ||
    pathname.startsWith("/_next") ||
    pathname.startsWith("/api") ||
    pathname === "/favicon.ico"
  ) {
    return NextResponse.next();
  }

  // Everything else → 404 (not found)
  return new NextResponse(null, { status: 404 });
}

export const config = {
  // Run on all routes except static files and Next.js internals
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
