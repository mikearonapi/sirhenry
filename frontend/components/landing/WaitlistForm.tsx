"use client";
import { useState } from "react";
import { ArrowRight, CheckCircle, Loader2, Mail } from "lucide-react";
import { joinWaitlist } from "@/app/actions/waitlist";

interface Props {
  dark?: boolean;
}

export default function WaitlistForm({ dark = false }: Props) {
  const [email, setEmail] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!email || loading) return;

    setError("");
    setLoading(true);

    const result = await joinWaitlist(email);

    if (result.success) {
      setSubmitted(true);
    } else {
      setError(result.message);
    }

    setLoading(false);
  }

  if (submitted) {
    return (
      <div
        className={`flex items-center justify-center gap-3 py-3 px-6 rounded-lg border ${
          dark
            ? "border-[#22C55E]/30 bg-[#22C55E]/10"
            : "border-[#BBF7D0] bg-[#F0FDF4]"
        }`}
      >
        <CheckCircle size={18} className="text-[#16A34A] shrink-0" />
        <p
          className={`text-sm font-medium ${
            dark ? "text-[#22C55E]" : "text-[#15803D]"
          }`}
        >
          You&apos;re on the list. We&apos;ll be in touch soon.
        </p>
      </div>
    );
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="flex flex-col sm:flex-row gap-3 w-full max-w-md mx-auto"
    >
      <div className="relative flex-1">
        <Mail
          size={16}
          className="absolute left-3.5 top-1/2 -translate-y-1/2 text-[#6B7280]"
        />
        <input
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="your@email.com"
          disabled={loading}
          className={`w-full pl-10 pr-4 py-3 rounded-lg text-sm border focus:outline-none focus:ring-2 focus:ring-[#16A34A]/30 focus:border-[#16A34A] transition-colors disabled:opacity-60 ${
            dark
              ? "bg-[#1C1C1F] border-[#3F3F46] text-[#F9FAFB] placeholder:text-[#6B7280]"
              : "bg-white border-[#D1D5DB] text-[#111827] placeholder:text-[#9CA3AF]"
          }`}
        />
      </div>
      <button
        type="submit"
        disabled={loading}
        className="flex items-center justify-center gap-2 bg-[#16A34A] hover:bg-[#15803D] text-white font-semibold text-sm px-6 py-3 rounded-lg transition-colors whitespace-nowrap disabled:opacity-60"
      >
        {loading ? (
          <>
            <Loader2 size={16} className="animate-spin" />
            Joining...
          </>
        ) : (
          <>
            Join the waitlist
            <ArrowRight size={16} />
          </>
        )}
      </button>
      {error && (
        <p className={`text-sm text-red-500 mt-1 sm:col-span-2 ${dark ? "text-red-400" : ""}`}>
          {error}
        </p>
      )}
    </form>
  );
}
