"use server";

import { neon } from "@neondatabase/serverless";

export async function joinWaitlist(email: string): Promise<{ success: boolean; message: string }> {
  const trimmed = email.trim().toLowerCase();

  if (!trimmed || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(trimmed)) {
    return { success: false, message: "Please enter a valid email address." };
  }

  const databaseUrl = process.env.DATABASE_URL;
  if (!databaseUrl) {
    // Graceful fallback: if no DB configured yet, still show success
    // so the form works during local dev / before Neon is connected
    console.warn("[waitlist] DATABASE_URL not set — email not saved:", trimmed);
    return { success: true, message: "You're on the list!" };
  }

  try {
    const sql = neon(databaseUrl);

    await sql`
      CREATE TABLE IF NOT EXISTS waitlist (
        id SERIAL PRIMARY KEY,
        email TEXT UNIQUE NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
      )
    `;

    await sql`
      INSERT INTO waitlist (email)
      VALUES (${trimmed})
      ON CONFLICT (email) DO NOTHING
    `;

    return { success: true, message: "You're on the list!" };
  } catch (error: unknown) {
    console.error("[waitlist] Failed to save email:", error);
    return { success: false, message: "Something went wrong. Please try again." };
  }
}
