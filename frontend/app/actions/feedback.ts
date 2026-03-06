"use server";

import { neon } from "@neondatabase/serverless";

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

  const databaseUrl = process.env.DATABASE_URL;
  if (!databaseUrl) {
    console.warn("[feedback] DATABASE_URL not set — feedback not saved");
    return { success: true, message: "Thank you for your feedback!" };
  }

  try {
    const sql = neon(databaseUrl);

    await sql`
      CREATE TABLE IF NOT EXISTS user_feedback (
        id SERIAL PRIMARY KEY,
        feedback_type TEXT NOT NULL,
        message TEXT NOT NULL,
        email TEXT,
        page_url TEXT,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
      )
    `;

    await sql`
      INSERT INTO user_feedback (feedback_type, message, email, page_url)
      VALUES (
        ${payload.feedback_type},
        ${trimmedMessage},
        ${trimmedEmail || null},
        ${payload.page_url || null}
      )
    `;

    return { success: true, message: "Thank you for your feedback!" };
  } catch (error: unknown) {
    console.error("[feedback] Failed to save feedback:", error);
    return { success: false, message: "Something went wrong. Please try again." };
  }
}
