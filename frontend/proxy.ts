import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

/**
 * Pre-launch proxy (Next.js 16).
 * - On Vercel (pre-launch): only the landing page is accessible, everything else 404s.
 * - Locally: all routes are accessible for development.
 *
 * TODO: When auth is enabled, add session validation here:
 *   - Check for a Supabase session cookie or auth header
 *   - If missing, redirect to a login page instead of returning 404
 *   - Allow unauthenticated access to `/`, `/api/`, and static assets
 */
export function proxy(request: NextRequest) {
  // In local dev, allow all routes for development
  const isPreLaunch = process.env.VERCEL && process.env.NEXT_PUBLIC_PRE_LAUNCH !== "false";
  if (!isPreLaunch) {
    return NextResponse.next();
  }

  const { pathname } = request.nextUrl;

  // Allow landing page, Next.js internals, and static assets from /public
  if (
    pathname === "/" ||
    pathname.startsWith("/_next") ||
    pathname.startsWith("/api") ||
    pathname === "/favicon.ico" ||
    pathname.startsWith("/screenshots/") ||
    /\.(png|jpg|jpeg|gif|svg|ico|webp|avif|woff|woff2|ttf|eot|css|js)$/.test(pathname)
  ) {
    return NextResponse.next();
  }

  return new NextResponse(null, { status: 404 });
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
