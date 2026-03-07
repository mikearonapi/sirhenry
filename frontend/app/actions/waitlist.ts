/**
 * Waitlist signup — stores emails in Supabase.
 * In desktop builds (static export), this becomes a no-op since the landing
 * page is not part of the desktop app.
 */
import { supabase, isSupabaseConfigured } from "@/lib/supabase";

export async function joinWaitlist(email: string): Promise<{ success: boolean; message: string }> {
  const trimmed = email.trim().toLowerCase();

  if (!trimmed || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(trimmed)) {
    return { success: false, message: "Please enter a valid email address." };
  }

  try {
    if (!isSupabaseConfigured()) {
      console.warn("[waitlist] Supabase not configured — email not saved:", trimmed);
      return { success: true, message: "You're on the list!" };
    }

    const { error } = await supabase
      .from("waitlist")
      .upsert({ email: trimmed }, { onConflict: "email" });

    if (error) {
      console.error("[waitlist] Supabase error:", error.message);
      return { success: false, message: "Something went wrong. Please try again." };
    }

    return { success: true, message: "You're on the list!" };
  } catch (error: unknown) {
    console.error("[waitlist] Failed to save email:", error);
    return { success: false, message: "Something went wrong. Please try again." };
  }
}
