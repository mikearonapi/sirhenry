"use client";
import { useState, useEffect } from "react";

/**
 * Full-screen splash shown on first app launch.
 * Black background, centered "Sir HENRY" with brand subtitle.
 * Fades out after a brief hold, then calls onComplete.
 */
export default function SplashScreen({ onComplete }: { onComplete: () => void }) {
  const [phase, setPhase] = useState<"hold" | "fade">("hold");

  useEffect(() => {
    // Hold the splash for 2s, then start fade-out
    const holdTimer = setTimeout(() => setPhase("fade"), 2000);
    return () => clearTimeout(holdTimer);
  }, []);

  useEffect(() => {
    if (phase === "fade") {
      const fadeTimer = setTimeout(onComplete, 600);
      return () => clearTimeout(fadeTimer);
    }
  }, [phase, onComplete]);

  return (
    <div
      className={`fixed inset-0 z-50 bg-black flex flex-col items-center justify-center transition-opacity duration-600 ${
        phase === "fade" ? "opacity-0" : "opacity-100"
      }`}
    >
      {/* Brand name */}
      <h1 className="text-white text-5xl md:text-6xl tracking-tight">
        <span
          className="italic font-light"
          style={{ fontFamily: "var(--font-display)" }}
        >
          Sir
        </span>
        <span
          className="ml-[0.2em] tracking-wide font-extrabold"
          style={{ fontFamily: "var(--font-display)" }}
        >
          HENRY
        </span>
      </h1>

      {/* Subtitle */}
      <p
        className="mt-3 text-[#16A34A] text-sm md:text-base font-medium tracking-wide"
        style={{ fontFamily: "var(--font-display)" }}
      >
        Your AI financial advisor
      </p>
    </div>
  );
}
