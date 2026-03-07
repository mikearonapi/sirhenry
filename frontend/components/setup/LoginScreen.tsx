"use client";
import { useState, useEffect, useCallback } from "react";
import {
  ArrowRight,
  Play,
  Loader2,
  Lock,
  Rocket,
  LogIn,
  RefreshCw,
} from "lucide-react";
import BrandLogo from "@/components/ui/BrandLogo";
import { isSupabaseConfigured } from "@/lib/supabase";
import { getSession } from "@/lib/auth";

interface LoginScreenProps {
  apiReady: boolean;
  apiTimedOut: boolean;
  onAuthenticated: () => void;
  onLocalSelected: () => void;
  onDemoSelected: () => void;
  onRetryConnection: () => void;
}

/**
 * Full-screen login with cinematic entrance:
 * Logo starts centered (matching splash position), then lifts to upper third
 * while login options reveal below with staggered fade-in.
 */
export default function LoginScreen({
  apiReady,
  apiTimedOut,
  onAuthenticated,
  onLocalSelected,
  onDemoSelected,
  onRetryConnection,
}: LoginScreenProps) {
  const [localLoading, setLocalLoading] = useState(false);
  const [demoLoading, setDemoLoading] = useState(false);
  const [checkingSession, setCheckingSession] = useState(() => isSupabaseConfigured());
  const [entered, setEntered] = useState(false);

  // Trigger entrance animation after mount
  useEffect(() => {
    const raf = requestAnimationFrame(() => {
      setTimeout(() => setEntered(true), 80);
    });
    return () => cancelAnimationFrame(raf);
  }, []);

  // On mount, check for existing Supabase session (returning user)
  useEffect(() => {
    async function check() {
      if (!isSupabaseConfigured()) {
        setCheckingSession(false);
        return;
      }
      const session = await getSession();
      if (session) {
        onAuthenticated();
      } else {
        setCheckingSession(false);
      }
    }
    check();
  }, [onAuthenticated]);

  const handleLocal = useCallback(() => {
    if (!apiReady) {
      setLocalLoading(true);
      return;
    }
    onLocalSelected();
  }, [apiReady, onLocalSelected]);

  const handleDemo = useCallback(() => {
    if (!apiReady) {
      setDemoLoading(true);
      return;
    }
    onDemoSelected();
  }, [apiReady, onDemoSelected]);

  // If button was clicked before API ready, proceed when ready
  useEffect(() => {
    if (localLoading && apiReady) onLocalSelected();
    if (demoLoading && apiReady) onDemoSelected();
  }, [localLoading, demoLoading, apiReady, onLocalSelected, onDemoSelected]);

  // When retry is initiated (apiTimedOut goes false), reset button loading states
  useEffect(() => {
    if (!apiTimedOut) return;
    // Don't reset — we show error state. Reset happens via handleRetry below.
  }, [apiTimedOut]);

  const handleRetry = useCallback(() => {
    setLocalLoading(false);
    setDemoLoading(false);
    onRetryConnection();
  }, [onRetryConnection]);

  // Still checking for existing session
  if (checkingSession) {
    return (
      <div className="fixed inset-0 z-50 bg-black flex items-center justify-center">
        <Loader2 className="w-6 h-6 text-white/40 animate-spin" />
      </div>
    );
  }

  const supabaseReady = isSupabaseConfigured();

  // Determine button states
  const isAnyLoading = localLoading || demoLoading;
  const showTimeout = apiTimedOut && isAnyLoading;

  return (
    <div className="fixed inset-0 z-50 bg-black overflow-hidden">
      {/* Brand block — starts at vertical center (matching splash), lifts to upper third */}
      <div
        className="absolute left-0 right-0 flex flex-col items-center justify-center transition-all duration-700 ease-[cubic-bezier(0.22,1,0.36,1)]"
        style={{
          top: entered ? "30%" : "50%",
          transform: "translateY(-50%)",
        }}
      >
        <BrandLogo />
      </div>

      {/* Login options — anchored below brand, fade in + slide up */}
      <div
        className="absolute left-0 right-0 flex justify-center px-6 transition-all duration-700 ease-[cubic-bezier(0.22,1,0.36,1)]"
        style={{
          top: "46%",
          opacity: entered ? 1 : 0,
          transform: entered ? "translateY(0)" : "translateY(20px)",
          transitionDelay: "150ms",
        }}
      >
        <div className="w-full max-w-sm space-y-3">
          {/* Option 1: Sign In / Create Account — Supabase Auth */}
          <button
            disabled
            className="w-full flex items-center gap-3 bg-white/[0.03] border border-white/[0.06] text-white/25 py-3.5 px-4 rounded-xl text-sm cursor-not-allowed"
            style={{
              opacity: entered ? 1 : 0,
              transform: entered ? "translateY(0)" : "translateY(12px)",
              transition: "opacity 500ms ease-out, transform 500ms ease-out",
              transitionDelay: "250ms",
            }}
          >
            <div className="w-9 h-9 rounded-lg bg-white/[0.04] flex items-center justify-center flex-shrink-0">
              {supabaseReady ? <LogIn size={16} /> : <Lock size={14} />}
            </div>
            <div className="text-left">
              <div
                className="font-medium"
                style={{ fontFamily: "var(--font-display)" }}
              >
                Sign In / Create Account
              </div>
              <div className="text-xs text-white/15 mt-0.5">Coming soon</div>
            </div>
          </button>

          {/* Divider */}
          <div
            className="flex items-center gap-3 !mt-5 !mb-5"
            style={{
              opacity: entered ? 1 : 0,
              transition: "opacity 500ms ease-out",
              transitionDelay: "350ms",
            }}
          >
            <div className="flex-1 h-px bg-white/10" />
            <span className="text-white/30 text-xs">or continue with</span>
            <div className="flex-1 h-px bg-white/10" />
          </div>

          {/* Option 2: Get Started — fresh local database, full onboarding */}
          <button
            onClick={handleLocal}
            disabled={localLoading}
            className="w-full flex items-center gap-3 bg-accent text-white py-3.5 px-4 rounded-xl text-sm font-semibold hover:bg-accent-hover disabled:opacity-50 disabled:cursor-not-allowed transition-colors shadow-lg shadow-accent/20 group"
            style={{
              opacity: entered ? 1 : 0,
              transform: entered ? "translateY(0)" : "translateY(12px)",
              transition:
                "opacity 500ms ease-out, transform 500ms ease-out, background-color 150ms",
              transitionDelay: entered ? "400ms" : "0ms",
            }}
          >
            <div className="w-9 h-9 rounded-lg bg-white/15 flex items-center justify-center flex-shrink-0">
              {localLoading && !showTimeout ? (
                <Loader2 size={16} className="animate-spin" />
              ) : (
                <Rocket size={16} />
              )}
            </div>
            <div className="text-left flex-1">
              <div style={{ fontFamily: "var(--font-display)" }}>
                {localLoading && !showTimeout
                  ? "Connecting..."
                  : "Get Started"}
              </div>
              <div className="text-xs text-white/60 mt-0.5 font-normal">
                Build your personalized financial profile
              </div>
            </div>
            {!localLoading && (
              <ArrowRight
                size={16}
                className="text-white/60 group-hover:text-white transition-colors"
              />
            )}
          </button>

          {/* Option 3: Explore Demo — separate demo database with synthetic data */}
          <button
            onClick={handleDemo}
            disabled={demoLoading}
            className="w-full flex items-center gap-3 bg-transparent border border-white/10 text-white/70 py-3.5 px-4 rounded-xl text-sm font-medium hover:border-white/20 hover:text-white disabled:opacity-50 transition-colors group"
            style={{
              opacity: entered ? 1 : 0,
              transform: entered ? "translateY(0)" : "translateY(12px)",
              transition:
                "opacity 500ms ease-out, transform 500ms ease-out, border-color 150ms, color 150ms",
              transitionDelay: entered ? "500ms" : "0ms",
            }}
          >
            <div className="w-9 h-9 rounded-lg bg-white/[0.06] flex items-center justify-center flex-shrink-0">
              {demoLoading && !showTimeout ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                <Play size={14} />
              )}
            </div>
            <div className="text-left flex-1">
              <div style={{ fontFamily: "var(--font-display)" }}>
                {demoLoading && !showTimeout
                  ? "Loading demo..."
                  : "Explore Demo"}
              </div>
              <div className="text-xs text-white/30 mt-0.5 font-normal">
                See Sir HENRY in action with sample data
              </div>
            </div>
            {!demoLoading && (
              <ArrowRight
                size={14}
                className="text-white/30 group-hover:text-white/60 transition-colors"
              />
            )}
          </button>

          {/* Connection error — shows when API timed out after button click */}
          {showTimeout && (
            <div className="flex flex-col items-center gap-2 pt-3">
              <p className="text-white/40 text-xs">
                Could not connect to the API
              </p>
              <button
                onClick={handleRetry}
                className="flex items-center gap-1.5 text-accent text-xs font-medium hover:text-accent transition-colors"
              >
                <RefreshCw size={12} />
                Try again
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
