/** Resolve the API base URL dynamically (called per-request to handle Tauri's late injection). */
export function getBase(): string {
  // Explicit env var (set at build time or in .env.local)
  if (process.env.NEXT_PUBLIC_API_URL) return process.env.NEXT_PUBLIC_API_URL;

  if (typeof window === "undefined") return "http://localhost:8000";

  // Tauri injects this after sidecar is ready
  const w = window as unknown as Record<string, unknown>;
  if (typeof w.__SIRHENRY_API_URL__ === "string") return w.__SIRHENRY_API_URL__;

  // Dev fallback: same host, port 8000
  return `${window.location.protocol}//${window.location.hostname}:8000`;
}

/**
 * Get auth headers (Authorization: Bearer <token>) for API requests.
 * Returns empty object in demo mode or when Supabase is not configured.
 * Use this for raw fetch() calls that can't go through request().
 */
export async function getAuthHeaders(): Promise<Record<string, string>> {
  const isDemoMode =
    typeof window !== "undefined" &&
    localStorage.getItem("henry.demo-mode") === "true";
  if (isDemoMode) return {};
  try {
    const { getAccessToken } = await import("./auth");
    const token = await getAccessToken();
    return token ? { Authorization: `Bearer ${token}` } : {};
  } catch {
    return {};
  }
}

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const authHeaders = await getAuthHeaders();

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(init?.headers as Record<string, string>),
    ...authHeaders,
  };

  const res = await fetch(`${getBase()}${path}`, {
    ...init,
    headers,
  });
  if (!res.ok) {
    const body = await res.text();
    let message = body;
    try {
      const json = JSON.parse(body);
      if (json.detail) message = json.detail;
    } catch {
      // body wasn't JSON — use raw text
    }
    // Dispatch custom event for error capture system
    if (typeof window !== "undefined") {
      window.dispatchEvent(
        new CustomEvent("sirhenry:api-error", {
          detail: { path, status: res.status, message },
        }),
      );
    }
    throw new Error(message);
  }
  return res.json() as Promise<T>;
}
