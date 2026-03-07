import { supabase, isSupabaseConfigured } from "./supabase";

/** Get current session (from local cache, no network call). */
export async function getSession() {
  if (!isSupabaseConfigured()) return null;
  const {
    data: { session },
  } = await supabase.auth.getSession();
  return session;
}

/** Get JWT access token for API calls. */
export async function getAccessToken(): Promise<string | null> {
  const session = await getSession();
  return session?.access_token ?? null;
}

/** Sign up with email and password. */
export async function signUp(email: string, password: string) {
  return supabase.auth.signUp({ email, password });
}

/** Sign in with email and password. */
export async function signIn(email: string, password: string) {
  return supabase.auth.signInWithPassword({ email, password });
}

/** Sign out and clear session. */
export async function signOut() {
  return supabase.auth.signOut();
}

/** Fetch user's subscription from Supabase Postgres. */
export async function getSubscription() {
  if (!isSupabaseConfigured()) return null;
  const { data, error } = await supabase
    .from("subscriptions")
    .select("tier, status, expires_at")
    .single();
  if (error) return null;
  return data as { tier: string; status: string; expires_at: string | null };
}

/** Fetch Anthropic API key from Supabase Edge Function (requires auth). */
export async function fetchApiKey(): Promise<string | null> {
  if (!isSupabaseConfigured()) return null;
  const session = await getSession();
  if (!session) return null;
  try {
    const { data, error } = await supabase.functions.invoke("get-api-key");
    if (error) return null;
    return (data as { key?: string })?.key ?? null;
  } catch {
    return null;
  }
}

/** Subscribe to auth state changes. */
export function onAuthStateChange(
  callback: (event: string, session: unknown) => void,
) {
  return supabase.auth.onAuthStateChange(callback);
}
