function resolveBase(): string {
  // Explicit env var (set at build time or in .env.local)
  if (process.env.NEXT_PUBLIC_API_URL) return process.env.NEXT_PUBLIC_API_URL;

  if (typeof window === "undefined") return "http://localhost:8000";

  // Tauri injects this before the app loads
  const w = window as unknown as Record<string, unknown>;
  if (typeof w.__SIRHENRY_API_URL__ === "string") return w.__SIRHENRY_API_URL__;

  // Dev fallback: same host, port 8000
  return `${window.location.protocol}//${window.location.hostname}:8000`;
}

export const BASE = resolveBase();

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...init?.headers },
    ...init,
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
    throw new Error(message);
  }
  return res.json() as Promise<T>;
}
