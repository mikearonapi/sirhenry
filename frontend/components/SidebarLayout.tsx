"use client";
import { useState, useEffect, useCallback } from "react";
import { usePathname } from "next/navigation";
import { Menu } from "lucide-react";
import Sidebar from "@/components/Sidebar";
import AiChat from "@/components/AiChat";
import ThemeToggle from "@/components/ui/ThemeToggle";
import DemoBanner from "@/components/ui/DemoBanner";
import ErrorBoundary from "@/components/ui/ErrorBoundary";
import { selectMode } from "@/lib/api-demo";
import { signOut } from "@/lib/auth";
import { DEMO_MODE_KEY, FIRST_RUN_KEY, SPLASH_SEEN_KEY, SIDEBAR_COLLAPSED_KEY } from "@/lib/storage-keys";

export default function SidebarLayout({ children }: { children: React.ReactNode }) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [isDemoMode, setIsDemoMode] = useState(false);
  const pathname = usePathname();
  // Full-height pages manage their own padding/layout
  const isFullHeight = pathname === "/sir-henry";

  // Check demo mode + sidebar collapsed state on mount
  useEffect(() => {
    setIsDemoMode(localStorage.getItem(DEMO_MODE_KEY) === "true");
    setSidebarCollapsed(localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === "true");
  }, []);

  // Allow child pages to open the app sidebar via custom event
  useEffect(() => {
    const handler = () => setSidebarOpen(true);
    window.addEventListener("open-app-sidebar", handler);
    return () => window.removeEventListener("open-app-sidebar", handler);
  }, []);

  const handleExitDemo = useCallback(async () => {
    // Switch API back to local database
    try {
      await selectMode("local");
    } catch {
      // Best effort
    }
    localStorage.removeItem(DEMO_MODE_KEY);
    localStorage.removeItem(FIRST_RUN_KEY);
    localStorage.removeItem(SPLASH_SEEN_KEY);
    try {
      await signOut();
    } catch {
      // Not authenticated in demo mode
    }
    window.location.reload();
  }, []);

  return (
    <div className="min-h-screen bg-background">
      <Sidebar
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        collapsed={sidebarCollapsed}
        onToggleCollapse={() => {
          setSidebarCollapsed((prev) => {
            const next = !prev;
            localStorage.setItem(SIDEBAR_COLLAPSED_KEY, String(next));
            return next;
          });
        }}
      />
      {!isFullHeight && (
        <button
          onClick={() => setSidebarOpen(true)}
          className="fixed top-4 left-4 z-10 p-2 bg-card rounded-lg shadow-md border border-border lg:hidden"
        >
          <Menu size={20} className="text-text-primary" />
        </button>
      )}
      <main className={`${sidebarCollapsed ? "lg:ml-[68px]" : "lg:ml-60"} min-h-screen transition-all duration-200`}>
        <div className="fixed top-3 right-4 z-10">
          <ThemeToggle />
        </div>
        {isDemoMode && <DemoBanner onExitDemo={handleExitDemo} />}
        <ErrorBoundary>
          {isFullHeight ? children : (
            <div className="max-w-7xl mx-auto px-8 pb-8 pt-20 lg:pt-8">{children}</div>
          )}
        </ErrorBoundary>
      </main>
      <AiChat />
    </div>
  );
}
