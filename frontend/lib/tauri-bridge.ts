/**
 * Tauri desktop integration utilities.
 * Detects if running inside Tauri and provides API URL resolution
 * with polling for sidecar readiness.
 */

export function isTauri(): boolean {
  return typeof window !== "undefined" && "__TAURI__" in window;
}

export function getApiUrl(): string | undefined {
  if (typeof window === "undefined") return undefined;
  const w = window as unknown as Record<string, unknown>;
  return typeof w.__SIRHENRY_API_URL__ === "string"
    ? w.__SIRHENRY_API_URL__
    : undefined;
}

export async function waitForApi(
  timeoutMs = 60000,
  intervalMs = 500,
): Promise<string | null> {
  const start = Date.now();

  while (Date.now() - start < timeoutMs) {
    const url = getApiUrl();
    if (url) {
      try {
        const res = await fetch(`${url}/health`, {
          signal: AbortSignal.timeout(2000),
        });
        if (res.ok) return url;
      } catch {
        // API not ready yet
      }
    }
    await new Promise((r) => setTimeout(r, intervalMs));
  }

  return null;
}
