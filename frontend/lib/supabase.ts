import { createClient, type SupabaseClient } from "@supabase/supabase-js";

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";
const SUPABASE_ANON_KEY = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? "";

/** Returns true if Supabase env vars are configured. */
export function isSupabaseConfigured(): boolean {
  return !!(SUPABASE_URL && SUPABASE_ANON_KEY);
}

/**
 * Supabase client singleton.
 * Safe to import even when env vars aren't set — auth calls will fail gracefully.
 */
export const supabase: SupabaseClient = createClient(
  SUPABASE_URL || "https://placeholder.supabase.co",
  SUPABASE_ANON_KEY || "placeholder",
  {
    auth: {
      persistSession: true,
      autoRefreshToken: true,
      detectSessionInUrl: false, // desktop app — no OAuth redirect handling
    },
  },
);
