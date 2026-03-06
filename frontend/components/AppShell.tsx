"use client";
import { useState, useEffect, useCallback } from "react";
import dynamic from "next/dynamic";
import SidebarLayout from "@/components/SidebarLayout";
import SplashScreen from "@/components/setup/SplashScreen";
import WelcomeScreen from "@/components/setup/WelcomeScreen";
import PrivacyScreen from "@/components/setup/PrivacyScreen";

// Lazy-load the full wizard — only needed during first-run onboarding
const SetupWizard = dynamic(() => import("@/components/setup/SetupWizard"), {
  loading: () => (
    <div className="flex items-center justify-center min-h-[60vh]">
      <div className="animate-pulse text-stone-400 text-sm">Loading...</div>
    </div>
  ),
});

const FIRST_RUN_KEY = "henry.first-run-complete";
const SPLASH_SEEN_KEY = "henry.splash-seen";

type OnboardingPhase = "splash" | "welcome" | "privacy" | "setup" | "done";

export default function AppShell({ children }: { children: React.ReactNode }) {
  const [phase, setPhase] = useState<OnboardingPhase | null>(null);

  useEffect(() => {
    const splashSeen = localStorage.getItem(SPLASH_SEEN_KEY);
    const firstRunDone = localStorage.getItem(FIRST_RUN_KEY);

    if (!splashSeen) {
      setPhase("splash");
    } else if (!firstRunDone) {
      // Splash was seen (e.g. browser refreshed mid-setup) but setup isn't done
      setPhase("setup");
    } else {
      setPhase("done");
    }
  }, []);

  const onSplashComplete = useCallback(() => {
    localStorage.setItem(SPLASH_SEEN_KEY, "true");
    setPhase("welcome");
  }, []);

  const onWelcomeStart = useCallback(() => {
    setPhase("privacy");
  }, []);

  const onPrivacyContinue = useCallback(() => {
    setPhase("setup");
  }, []);

  const onSetupComplete = useCallback(() => {
    localStorage.setItem(FIRST_RUN_KEY, "true");
    setPhase("done");
  }, []);

  // Avoid flash before we determine the phase
  if (phase === null) {
    return <div className="min-h-screen bg-black" />;
  }

  // Phase 1: Splash screen
  if (phase === "splash") {
    return <SplashScreen onComplete={onSplashComplete} />;
  }

  // Phase 2: Welcome screen
  if (phase === "welcome") {
    return <WelcomeScreen onStart={onWelcomeStart} />;
  }

  // Phase 3: Privacy & security
  if (phase === "privacy") {
    return <PrivacyScreen onContinue={onPrivacyContinue} />;
  }

  // Phase 4: Full-screen setup wizard (no sidebar)
  if (phase === "setup") {
    return (
      <div className="min-h-screen bg-[#faf9f7]">
        <div className="max-w-2xl mx-auto px-6 py-10">
          <SetupWizard onComplete={onSetupComplete} />
        </div>
      </div>
    );
  }

  // Phase 5: Normal app with sidebar
  return <SidebarLayout>{children}</SidebarLayout>;
}

/**
 * Call this when the setup wizard is completed to mark first-run as done.
 * Prevents the splash screen from redirecting to setup on future visits.
 */
export function markSetupComplete() {
  localStorage.setItem(FIRST_RUN_KEY, "true");
}

/**
 * Check whether the user has completed first-run setup.
 */
export function isSetupComplete(): boolean {
  return localStorage.getItem(FIRST_RUN_KEY) === "true";
}
