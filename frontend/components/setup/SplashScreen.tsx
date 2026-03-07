"use client";
import { useState, useEffect } from "react";
import BrandLogo from "@/components/ui/BrandLogo";

/**
 * Full-screen splash shown on first app launch.
 * Black background, centered "Sir HENRY" with brand subtitle.
 * Loading dots are absolutely positioned so they never shift the logo.
 * Holds for at least 2s, then fades out and calls onComplete.
 */
export default function SplashScreen({
  onComplete,
  ready = true,
}: {
  onComplete: () => void;
  ready?: boolean;
}) {
  const [minTimeElapsed, setMinTimeElapsed] = useState(false);

  // Minimum display time: 2s
  useEffect(() => {
    const timer = setTimeout(() => setMinTimeElapsed(true), 2000);
    return () => clearTimeout(timer);
  }, []);

  // Proceed immediately when ready — no fade-out.
  // LoginScreen starts with brand in same position, so the cut is seamless.
  useEffect(() => {
    if (minTimeElapsed && ready) {
      onComplete();
    }
  }, [minTimeElapsed, ready, onComplete]);

  return (
    <div className="fixed inset-0 z-50 bg-black">
      {/* Centered brand — uses absolute positioning so nothing shifts it */}
      <div className="absolute inset-0">
        <BrandLogo className="h-full" />
      </div>

      {/* Loading indicator — absolutely positioned below center, never shifts logo */}
      <div
        className={`absolute left-1/2 top-[calc(50%+72px)] -translate-x-1/2 flex items-center gap-1.5 transition-opacity duration-500 ${
          !ready && minTimeElapsed ? "opacity-100" : "opacity-0"
        }`}
      >
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
    </div>
  );
}
