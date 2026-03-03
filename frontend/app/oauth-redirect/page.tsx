"use client";

/**
 * Plaid OAuth Redirect Handler
 *
 * Capital One, Chase, and other OAuth-flow institutions redirect back here
 * after the user authenticates on their external site. We re-initialize
 * Plaid Link with `receivedRedirectUri` set to the current URL, which
 * contains the `oauth_state_id` query param Plaid needs to complete the flow.
 *
 * Flow:
 *   1. User clicks "Link bank" on /accounts → Link opens
 *   2. Plaid detects OAuth institution, redirects to bank's site
 *   3. Bank redirects back to /oauth-redirect?oauth_state_id=...
 *   4. This page reads `link_token` from sessionStorage + current URL
 *   5. Re-opens Link with `receivedRedirectUri` → Link completes
 *   6. onSuccess fires → public token exchanged → redirect to /accounts
 */

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { usePlaidLink } from "react-plaid-link";
import { exchangePlaidPublicToken } from "@/lib/api";
import { getErrorMessage } from "@/lib/errors";
import { Loader2, AlertCircle } from "lucide-react";

const LINK_TOKEN_KEY = "plaid_oauth_link_token";
const INSTITUTION_KEY = "plaid_oauth_institution";

export default function OAuthRedirectPage() {
  const router = useRouter();
  const [linkToken, setLinkToken] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState("Completing bank connection...");

  // The full current URL (including ?oauth_state_id=...) is the receivedRedirectUri.
  const receivedRedirectUri =
    typeof window !== "undefined" ? window.location.href : "";

  useEffect(() => {
    const token = sessionStorage.getItem(LINK_TOKEN_KEY);
    if (!token) {
      setError(
        "No Plaid session found. Please return to Accounts and try connecting again."
      );
      return;
    }
    setLinkToken(token);
  }, []);

  const { open, ready } = usePlaidLink({
    token: linkToken,
    receivedRedirectUri,
    onSuccess: async (publicToken, metadata) => {
      const institutionName =
        sessionStorage.getItem(INSTITUTION_KEY) ??
        metadata?.institution?.name ??
        "your bank";
      sessionStorage.removeItem(LINK_TOKEN_KEY);
      sessionStorage.removeItem(INSTITUTION_KEY);
      setStatus(`Connected to ${institutionName}! Saving...`);
      try {
        await exchangePlaidPublicToken(publicToken, institutionName);
        router.push("/accounts?connected=1");
      } catch (e: unknown) {
        setError(`Failed to save connection: ${getErrorMessage(e)}`);
      }
    },
    onExit: (err) => {
      sessionStorage.removeItem(LINK_TOKEN_KEY);
      sessionStorage.removeItem(INSTITUTION_KEY);
      if (err) {
        setError(
          err.display_message || err.error_message || "Connection cancelled."
        );
      } else {
        router.push("/accounts");
      }
    },
  });

  // Open Link as soon as token + ready — this is the re-entry point
  useEffect(() => {
    if (linkToken && ready) open();
  }, [linkToken, ready, open]);

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-stone-50">
        <div className="max-w-md w-full mx-4 bg-white rounded-2xl shadow-sm border border-stone-200 p-8 text-center space-y-4">
          <AlertCircle className="mx-auto text-red-500" size={40} />
          <h1 className="text-lg font-semibold text-stone-800">
            Connection error
          </h1>
          <p className="text-sm text-stone-500">{error}</p>
          <button
            onClick={() => router.push("/accounts")}
            className="mt-4 px-5 py-2.5 bg-[#16A34A] text-white rounded-lg text-sm font-medium hover:bg-[#15803D]"
          >
            Back to Accounts
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-stone-50">
      <div className="max-w-md w-full mx-4 bg-white rounded-2xl shadow-sm border border-stone-200 p-8 text-center space-y-4">
        <Loader2 className="mx-auto animate-spin text-[#16A34A]" size={40} />
        <h1 className="text-lg font-semibold text-stone-800">
          Finishing connection
        </h1>
        <p className="text-sm text-stone-500">{status}</p>
      </div>
    </div>
  );
}

// Exported helpers for the accounts page to persist state across the redirect
export { LINK_TOKEN_KEY, INSTITUTION_KEY };
