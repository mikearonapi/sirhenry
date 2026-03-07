"use server";

/**
 * Feedback submission — posts to Supabase `user_feedback` table.
 * Runs server-side only (Next.js Server Action).
 */
import { createClient } from "@supabase/supabase-js";

type FeedbackType = "bug" | "feature" | "general";

interface FeedbackPayload {
  feedback_type: FeedbackType;
  message: string;
  email: string;
  page_url: string;
}

const VALID_TYPES: FeedbackType[] = ["bug", "feature", "general"];

export async function submitFeedback(
  payload: FeedbackPayload
): Promise<{ success: boolean; message: string }> {
  const trimmedMessage = payload.message.trim();
  if (!trimmedMessage) {
    return { success: false, message: "Please enter a message." };
  }

  if (!VALID_TYPES.includes(payload.feedback_type)) {
    return { success: false, message: "Invalid feedback type." };
  }

  const trimmedEmail = payload.email.trim().toLowerCase();
  if (trimmedEmail && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(trimmedEmail)) {
    return { success: false, message: "Please enter a valid email address." };
  }

  try {
    const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
    const supabaseKey = process.env.SUPABASE_SERVICE_ROLE_KEY || process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

    if (!supabaseUrl || !supabaseKey) {
      console.warn("[feedback] Supabase not configured — feedback not saved");
      return { success: true, message: "Thank you for your feedback!" };
    }

    const supabase = createClient(supabaseUrl, supabaseKey);

    const { error } = await supabase.from("user_feedback").insert({
      feedback_type: payload.feedback_type,
      message: trimmedMessage,
      email: trimmedEmail || null,
      page_url: payload.page_url || null,
    });

    if (error) {
      console.error("[feedback] Supabase insert error:", error.message);
      return { success: false, message: "Something went wrong. Please try again." };
    }

    return { success: true, message: "Thank you for your feedback!" };
  } catch (error: unknown) {
    console.error("[feedback] Failed to save feedback:", error);
    return { success: false, message: "Something went wrong. Please try again." };
  }
}
