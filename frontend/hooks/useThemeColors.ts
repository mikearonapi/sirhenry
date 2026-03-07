"use client";
import { useTheme } from "next-themes";
import { useEffect, useState } from "react";

export interface ThemeColors {
  axisText: string;
  gridLine: string;
  tooltipBorder: string;
  tooltipBg: string;
  tooltipText: string;
  positive: string;
  negative: string;
  warning: string;
  neutral: string;
  accent: string;
  gold: string;
}

const LIGHT: ThemeColors = {
  axisText: "#9CA3AF",
  gridLine: "#F3F4F6",
  tooltipBorder: "#E5E7EB",
  tooltipBg: "#ffffff",
  tooltipText: "#111827",
  positive: "#16A34A",
  negative: "#DC2626",
  warning: "#D97706",
  neutral: "#6B7280",
  accent: "#16A34A",
  gold: "#CA8A04",
};

const DARK: ThemeColors = {
  axisText: "#71717a",
  gridLine: "#2a2a2d",
  tooltipBorder: "#3f3f46",
  tooltipBg: "#1e1e20",
  tooltipText: "#f0f0ef",
  positive: "#22c55e",
  negative: "#f87171",
  warning: "#fbbf24",
  neutral: "#71717a",
  accent: "#22c55e",
  gold: "#eab308",
};

export function useThemeColors(): ThemeColors {
  const { resolvedTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);

  if (!mounted) return LIGHT;
  return resolvedTheme === "dark" ? DARK : LIGHT;
}
