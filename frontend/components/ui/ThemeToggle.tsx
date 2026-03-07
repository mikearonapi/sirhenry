"use client";
import { useTheme } from "next-themes";
import { useEffect, useState } from "react";
import { Sun, Moon, Monitor } from "lucide-react";

type ThemeOption = "system" | "light" | "dark";

const OPTIONS: { value: ThemeOption; icon: typeof Sun; label: string }[] = [
  { value: "system", icon: Monitor, label: "Auto" },
  { value: "light", icon: Sun, label: "Light" },
  { value: "dark", icon: Moon, label: "Dark" },
];

export default function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);
  if (!mounted) return <div className="w-[76px] h-8" />;

  const cycle = () => {
    const idx = OPTIONS.findIndex((o) => o.value === theme);
    setTheme(OPTIONS[(idx + 1) % OPTIONS.length].value);
  };

  const current = OPTIONS.find((o) => o.value === theme) ?? OPTIONS[0];
  const Icon = current.icon;

  return (
    <button
      onClick={cycle}
      title={`Theme: ${current.label}. Click to cycle.`}
      className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-text-secondary hover:text-text-primary hover:bg-surface border border-transparent hover:border-border transition-all text-xs font-medium"
    >
      <Icon size={14} />
      <span className="hidden sm:inline">{current.label}</span>
    </button>
  );
}
