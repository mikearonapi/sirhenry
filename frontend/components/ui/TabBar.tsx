"use client";
import type { LucideIcon } from "lucide-react";

export interface TabDef {
  id: string;
  label: string;
  icon?: LucideIcon;
}

interface TabBarProps {
  tabs: TabDef[];
  activeTab: string;
  onChange: (id: string) => void;
  variant?: "underline" | "pill";
}

export default function TabBar({ tabs, activeTab, onChange, variant = "underline" }: TabBarProps) {
  if (variant === "pill") {
    return (
      <div className="flex bg-surface rounded-lg p-0.5">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => onChange(tab.id)}
            className={`flex-1 flex items-center justify-center gap-1.5 py-2.5 px-4 rounded-md text-sm font-medium transition-colors ${
              activeTab === tab.id
                ? "bg-card text-text-primary shadow-sm"
                : "text-text-secondary hover:text-text-primary"
            }`}
          >
            {tab.icon && <tab.icon size={15} />}
            {tab.label}
          </button>
        ))}
      </div>
    );
  }

  return (
    <div className="flex gap-1 border-b border-border overflow-x-auto">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          onClick={() => onChange(tab.id)}
          className={`flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium whitespace-nowrap border-b-2 transition-colors ${
            activeTab === tab.id
              ? "border-accent text-accent"
              : "border-transparent text-text-secondary hover:text-text-primary hover:border-border"
          }`}
        >
          {tab.icon && <tab.icon size={15} />}
          {tab.label}
        </button>
      ))}
    </div>
  );
}
