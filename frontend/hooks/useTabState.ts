"use client";
import { useState, useEffect, useCallback } from "react";
import type { TabDef } from "@/components/ui/TabBar";

/**
 * Tab state hook with URL hash persistence.
 * Reads initial tab from `#tab=<id>` and updates the hash on change.
 */
export function useTabState(tabs: TabDef[], defaultTab?: string) {
  const fallback = defaultTab ?? tabs[0]?.id ?? "";

  const [activeTab, setActiveTab] = useState(() => {
    if (typeof window === "undefined") return fallback;
    const hash = window.location.hash.replace("#", "");
    const params = new URLSearchParams(hash);
    const tab = params.get("tab");
    if (tab && tabs.some((t) => t.id === tab)) return tab;
    return fallback;
  });

  useEffect(() => {
    if (typeof window !== "undefined") {
      window.history.replaceState(null, "", `#tab=${activeTab}`);
    }
  }, [activeTab]);

  const setTab = useCallback((id: string) => {
    if (tabs.some((t) => t.id === id)) setActiveTab(id);
  }, [tabs]);

  return [activeTab, setTab] as const;
}
