"use client";
import { useState, useEffect, useCallback } from "react";
import dynamic from "next/dynamic";
import { RefreshCw } from "lucide-react";
import SidebarLayout from "@/components/SidebarLayout";
import ErrorBoundary from "@/components/ui/ErrorBoundary";
import BrandLogo from "@/components/ui/BrandLogo";
import SplashScreen from "@/components/setup/SplashScreen";
import LoginScreen from "@/components/setup/LoginScreen";
import WelcomeScreen from "@/components/setup/WelcomeScreen";
import GoalsScreen from "@/components/setup/GoalsScreen";
import { isTauri, waitForApi } from "@/lib/tauri-bridge";
import { selectMode } from "@/lib/api-demo";
import { fetchApiKey } from "@/lib/auth";
import { request } from "@/lib/api-client";
import { getSetupStatus } from "@/lib/api-setup";
import { FIRST_RUN_KEY, SPLASH_SEEN_KEY, DEMO_MODE_KEY } from "@/lib/storage-keys";

// Lazy-load the full wizard — only needed during first-run onboarding
const SetupWizard = dynamic(() => import("@/components/setup/SetupWizard"), {
  loading: () => (
    <div className="flex items-center justify-center min-h-[60vh]">
      <div className="animate-pulse text-text-muted text-sm">Loading...</div>
    </div>
  ),
});

type OnboardingPhase = "splash" | "auth" | "welcome" | "goals" | "setup" | "done";

export default function AppShell({ children }: { children: React.ReactNode }) {
  const [phase, setPhase] = useState<OnboardingPhase | null>(null);
  const [apiReady, setApiReady] = useState(false);
  const [apiTimedOut, setApiTimedOut] = useState(false);
  const inTauri = typeof window !== "undefined" && isTauri();

  // Start API polling and determine initial phase
  useEffect(() => {
    if (inTauri) {
      // Start polling for sidecar in background — don't block UI
      waitForApi(60000, 500).then((url) => {
        if (url) {
          setApiReady(true);
        } else {
          setApiTimedOut(true);
        }
      });
      // Skip splash on subsequent Tauri launches for returning users
      const splashSeen = localStorage.getItem(SPLASH_SEEN_KEY);
      const firstRunDone = localStorage.getItem(FIRST_RUN_KEY);
      if (splashSeen && firstRunDone) {
        setPhase("done");
      } else if (splashSeen) {
        setPhase("auth");
      } else {
        setPhase("splash");
      }
    } else {
      setApiReady(true);
      // Web mode: skip splash, determine phase from localStorage
      const firstRunDone = localStorage.getItem(FIRST_RUN_KEY);
      const demoMode = localStorage.getItem(DEMO_MODE_KEY);
      if (demoMode === "true" && firstRunDone) {
        selectMode("demo")
          .then(() => setPhase("done"))
          .catch(() => setPhase("done"));
      } else if (firstRunDone) {
        selectMode("local")
          .then(() => setPhase("done"))
          .catch(() => setPhase("done"));
      } else {
        // No localStorage flag — check server-side completion as fallback
        getSetupStatus()
          .then((status) => {
            if (status.complete || status.setup_completed_at) {
              localStorage.setItem(FIRST_RUN_KEY, "true");
              selectMode("local")
                .then(() => setPhase("done"))
                .catch(() => setPhase("done"));
            } else {
              setPhase("auth");
            }
          })
          .catch(() => setPhase("auth"));
      }
    }
  }, [inTauri]);

  // When API becomes ready, select the correct database mode (background)
  useEffect(() => {
    if (!apiReady || !inTauri) return;
    const demoMode = localStorage.getItem(DEMO_MODE_KEY);
    const firstRunDone = localStorage.getItem(FIRST_RUN_KEY);

    if (demoMode === "true" && firstRunDone) {
      selectMode("demo").catch(() => {});
    } else if (firstRunDone) {
      selectMode("local").catch(() => {});
    }
  }, [apiReady, inTauri]);

  // Retry API connection after timeout
  const retryApiConnection = useCallback(() => {
    setApiTimedOut(false);
    waitForApi(60000, 500).then((url) => {
      if (url) {
        setApiReady(true);
      } else {
        setApiTimedOut(true);
      }
    });
  }, []);

  // Splash complete → check if returning user, otherwise show login screen
  const onSplashComplete = useCallback(() => {
    localStorage.setItem(SPLASH_SEEN_KEY, "true");
    const firstRunDone = localStorage.getItem(FIRST_RUN_KEY);
    if (firstRunDone) {
      setPhase("done");
    } else {
      setPhase("auth");
    }
  }, []);

  // Supabase auth complete → fetch API key, switch to local mode
  const onAuthenticated = useCallback(async () => {
    try {
      const key = await fetchApiKey();
      if (key) {
        await request("/auth/inject-api-key", {
          method: "POST",
          body: JSON.stringify({ key }),
        });
      }
    } catch {
      // Edge Function not available (dev mode)
    }

    localStorage.removeItem(DEMO_MODE_KEY);
    await selectMode("local").catch(() => {});

    const firstRunDone = localStorage.getItem(FIRST_RUN_KEY);
    if (firstRunDone) {
      setPhase("done");
    } else {
      setPhase("welcome");
    }
  }, []);

  // "Continue as Mike" — switch to local DB and enter app
  const onLocalSelected = useCallback(async () => {
    await selectMode("local").catch(() => {});
    localStorage.removeItem(DEMO_MODE_KEY);

    const firstRunDone = localStorage.getItem(FIRST_RUN_KEY);
    if (firstRunDone) {
      setPhase("done");
    } else {
      setPhase("welcome");
    }
  }, []);

  // "Explore Demo" — switch to demo DB (auto-seeds) and enter app
  const onDemoSelected = useCallback(async () => {
    try {
      await selectMode("demo");
    } catch {
      // Demo mode API switch failed — proceed anyway
    }
    localStorage.setItem(FIRST_RUN_KEY, "true");
    localStorage.setItem(DEMO_MODE_KEY, "true");
    setPhase("done");
  }, []);

  const onWelcomeStart = useCallback(() => {
    setPhase("goals");
  }, []);

  const onGoalsComplete = useCallback((_goals: string[]) => {
    setPhase("setup");
  }, []);

  const onSetupComplete = useCallback(async () => {
    localStorage.setItem(FIRST_RUN_KEY, "true");
    // Persist setup_completed_at server-side so the flag survives DB resets
    try {
      await request("/setup/complete", { method: "POST" });
    } catch {
      // Non-critical — localStorage flag is the primary gate
    }
    setPhase("done");
  }, []);

  // Avoid flash before we determine the phase
  if (phase === null) {
    return <div className="min-h-screen bg-black" />;
  }

  if (phase === "splash") {
    return <SplashScreen onComplete={onSplashComplete} />;
  }

  if (phase === "auth") {
    return (
      <LoginScreen
        apiReady={apiReady}
        apiTimedOut={apiTimedOut}
        onAuthenticated={onAuthenticated}
        onLocalSelected={onLocalSelected}
        onDemoSelected={onDemoSelected}
        onRetryConnection={retryApiConnection}
      />
    );
  }

  if (phase === "welcome") {
    return <WelcomeScreen onStart={onWelcomeStart} />;
  }

  if (phase === "goals") {
    return <GoalsScreen onContinue={onGoalsComplete} />;
  }

  if (phase === "setup") {
    // SetupWizard now handles its own full-screen layout
    return <SetupWizard onComplete={onSetupComplete} />;
  }

  // Phase "done" — show dashboard, but wait for API in Tauri
  if (inTauri && !apiReady) {
    return (
      <div className="fixed inset-0 z-50 bg-black">
        {/* Brand — same position as splash for visual continuity */}
        <div className="absolute inset-0">
          <BrandLogo className="h-full" />
        </div>

        {/* Status area — below center */}
        <div className="absolute left-1/2 top-[calc(50%+72px)] -translate-x-1/2 flex flex-col items-center gap-4">
          {apiTimedOut ? (
            <>
              <p className="text-white/40 text-sm">
                Having trouble connecting to the API
              </p>
              <button
                onClick={retryApiConnection}
                className="flex items-center gap-2 text-accent text-sm font-medium hover:text-accent transition-colors"
              >
                <RefreshCw size={14} />
                Try again
              </button>
            </>
          ) : (
            <>
              <div className="flex items-center gap-1.5">
                <div
                  className="w-1 h-1 rounded-full bg-white/30 animate-pulse"
                  style={{ animationDelay: "0ms" }}
                />
                <div
                  className="w-1 h-1 rounded-full bg-white/30 animate-pulse"
                  style={{ animationDelay: "300ms" }}
                />
                <div
                  className="w-1 h-1 rounded-full bg-white/30 animate-pulse"
                  style={{ animationDelay: "600ms" }}
                />
              </div>
              <p className="text-white/25 text-xs">Starting up...</p>
            </>
          )}
        </div>
      </div>
    );
  }

  return (
    <ErrorBoundary>
      <SidebarLayout>{children}</SidebarLayout>
    </ErrorBoundary>
  );
}

export function markSetupComplete() {
  localStorage.setItem(FIRST_RUN_KEY, "true");
}

export function isSetupComplete(): boolean {
  return localStorage.getItem(FIRST_RUN_KEY) === "true";
}
