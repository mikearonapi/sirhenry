"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard, List, Upload,
  Wallet, ArrowLeftRight,
  RotateCcw, Target, Building2,
  PieChart, ChevronLeft, ChevronRight, Activity, X,
  Compass, FileText, ChevronDown,
  Briefcase, Users, Settings, Zap, Landmark, Calendar, ShieldCheck,
  ChevronUp, Sparkles, MessageCircle,
} from "lucide-react";
import { useState, useRef, useEffect, useCallback } from "react";
import { request } from "@/lib/api-client";

interface FamilyMember {
  id: number;
  name: string;
  relationship: string;
}

// ---------------------------------------------------------------------------
// Navigation structure
// ---------------------------------------------------------------------------

const NAV_PINNED = [
  { href: "/sir-henry", label: "Chat", icon: MessageCircle },
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
];

const NAV_SECTIONS = [
  {
    label: "Money",
    items: [
      { href: "/cashflow", label: "Cash Flow", icon: ArrowLeftRight },
      { href: "/budget", label: "Budget", icon: Wallet },
      { href: "/recurring", label: "Recurring", icon: RotateCcw },
      { href: "/transactions", label: "Transactions", icon: List },
    ],
  },
  {
    label: "Wealth & Planning",
    items: [
      { href: "/goals", label: "Goals", icon: Target },
      { href: "/portfolio", label: "Portfolio", icon: PieChart },
      { href: "/retirement", label: "Retirement", icon: Landmark },
      { href: "/market", label: "Market Pulse", icon: Activity },
      { href: "/equity-comp", label: "Equity Comp", icon: Briefcase },
      { href: "/life-planner", label: "Life Planner", icon: Compass },
    ],
  },
  {
    label: "Taxes & Business",
    items: [
      { href: "/tax-strategy", label: "Tax Strategy", icon: Zap },
      { href: "/tax-documents", label: "Tax Documents", icon: FileText },
      { href: "/business", label: "My Businesses", icon: Building2 },
    ],
  },
];

const SETUP_MENU_ITEMS = [
  { href: "/setup", label: "Setup Wizard", icon: Sparkles },
  { href: "/accounts", label: "Accounts", icon: Building2 },
  { href: "/household", label: "Household", icon: Users },
  { href: "/life-events", label: "Life Events", icon: Calendar },
  { href: "/insurance", label: "Policies", icon: ShieldCheck },
];

const UTILITY_MENU_ITEMS = [
  { href: "/import", label: "Import", icon: Upload },
  { href: "/admin", label: "Settings", icon: Settings },
];

// ---------------------------------------------------------------------------
// localStorage helpers for collapsed sections
// ---------------------------------------------------------------------------

const STORAGE_KEY = "sidebar.collapsed";
const ALL_SECTION_LABELS = NAV_SECTIONS.map((s) => s.label);

function getStoredCollapsed(): Set<string> {
  try {
    const raw = typeof window !== "undefined" ? localStorage.getItem(STORAGE_KEY) : null;
    // Default: all sections collapsed until the user expands them
    return raw ? new Set(JSON.parse(raw) as string[]) : new Set(ALL_SECTION_LABELS);
  } catch { return new Set(ALL_SECTION_LABELS); }
}

function persistCollapsed(sections: Set<string>) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify([...sections]));
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function isRouteActive(pathname: string, href: string) {
  return pathname === href || (href !== "/dashboard" && pathname.startsWith(href + "/"));
}

function sectionContainsActiveRoute(pathname: string, items: { href: string }[]) {
  return items.some((item) => isRouteActive(pathname, item.href));
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function Sidebar({ isOpen, onClose }: { isOpen: boolean; onClose: () => void }) {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);
  const [collapsedSections, setCollapsedSections] = useState<Set<string>>(new Set());
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const userMenuRef = useRef<HTMLDivElement>(null);
  const [userName, setUserName] = useState<string | null>(null);

  // Load collapsed sections from localStorage
  useEffect(() => { setCollapsedSections(getStoredCollapsed()); }, []);

  // Auto-expand section containing active route
  useEffect(() => {
    for (const section of NAV_SECTIONS) {
      if (section.label && sectionContainsActiveRoute(pathname, section.items)) {
        setCollapsedSections((prev) => {
          if (!prev.has(section.label)) return prev;
          const next = new Set(prev);
          next.delete(section.label);
          persistCollapsed(next);
          return next;
        });
      }
    }
  }, [pathname]);

  function toggleSection(label: string) {
    setCollapsedSections((prev) => {
      const next = new Set(prev);
      if (next.has(label)) next.delete(label);
      else next.add(label);
      persistCollapsed(next);
      return next;
    });
  }

  const fetchUserName = useCallback(async () => {
    try {
      const members = await request<FamilyMember[]>("/family-members/");
      const primary = members.find((m) => m.relationship === "self") ?? members[0];
      if (primary) setUserName(primary.name);
    } catch {
      // silently fall back to default
    }
  }, []);

  useEffect(() => { fetchUserName(); }, [fetchUserName]);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (userMenuRef.current && !userMenuRef.current.contains(e.target as Node)) {
        setUserMenuOpen(false);
      }
    }
    if (userMenuOpen) document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [userMenuOpen]);

  const displayName = userName ?? "User";
  const displayInitial = displayName.charAt(0).toUpperCase();

  // Render a single nav link
  function NavLink({ href, label, icon: Icon }: { href: string; label: string; icon: typeof MessageCircle }) {
    const active = isRouteActive(pathname, href);
    return (
      <Link
        href={href}
        onClick={onClose}
        title={collapsed ? label : undefined}
        className={`flex items-center ${collapsed ? "justify-center" : "gap-2.5"} px-2.5 py-2 rounded-lg text-[13px] font-medium transition-all ${
          active
            ? "bg-[#16A34A]/15 text-[#22C55E] border-l-2 border-[#16A34A]"
            : "text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200 border-l-2 border-transparent"
        }`}
      >
        <Icon size={18} className="shrink-0" />
        {!collapsed && <span className="truncate">{label}</span>}
      </Link>
    );
  }

  // Render a user menu link
  function MenuLink({ href, label, icon: Icon }: { href: string; label: string; icon: typeof MessageCircle }) {
    const active = isRouteActive(pathname, href);
    return (
      <Link
        href={href}
        onClick={() => { setUserMenuOpen(false); onClose(); }}
        className={`flex items-center gap-2.5 px-3 py-2 text-[13px] transition-colors ${
          active
            ? "text-[#22C55E] bg-[#16A34A]/10"
            : "text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200"
        }`}
      >
        <Icon size={15} className="shrink-0" />
        <span>{label}</span>
      </Link>
    );
  }

  return (
    <>
    {isOpen && <div className="fixed inset-0 bg-black/50 z-10 lg:hidden" onClick={onClose} />}
    <aside
      className={`fixed inset-y-0 left-0 ${collapsed ? "w-[68px]" : "w-60"} bg-[#0a0a0b] flex flex-col z-20 transition-all duration-200 ${isOpen ? "translate-x-0" : "-translate-x-full"} lg:translate-x-0`}
    >
      {/* Mobile close */}
      <button onClick={onClose} className="absolute top-4 right-4 text-stone-400 hover:text-white lg:hidden z-30">
        <X size={20} />
      </button>

      {/* Logo */}
      <div className={`flex items-center ${collapsed ? "justify-center" : "px-5"} h-16 border-b border-zinc-800`}>
        {collapsed ? (
          <span className="text-white text-lg font-extrabold" style={{ fontFamily: "var(--font-display, sans-serif)" }}>H</span>
        ) : (
          <p className="text-white text-xl font-semibold tracking-tight" style={{ fontFamily: "var(--font-display, sans-serif)" }}>
            Sir<span className="tracking-wide font-extrabold">HENRY</span>
          </p>
        )}
      </div>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto px-2.5 py-3">
        {/* Pinned items */}
        <div className="space-y-0.5">
          {NAV_PINNED.map((item) => (
            <NavLink key={item.href} {...item} />
          ))}
        </div>

        <div className="border-b border-zinc-800 my-3" />

        {/* Collapsible sections */}
        {NAV_SECTIONS.map((section, si) => {
          const isCollapsed = collapsedSections.has(section.label);
          const hasActiveChild = sectionContainsActiveRoute(pathname, section.items);

          return (
            <div key={section.label}>
              {/* Section header — clickable toggle (hidden in icon-only mode) */}
              {!collapsed ? (
                <button
                  onClick={() => toggleSection(section.label)}
                  className="w-full flex items-center justify-between px-2.5 py-1.5 mb-0.5 group"
                >
                  <span className={`text-[10px] font-semibold uppercase tracking-wider transition-colors ${
                    hasActiveChild ? "text-zinc-400" : "text-zinc-600 group-hover:text-zinc-400"
                  }`}>
                    {section.label}
                  </span>
                  <ChevronDown
                    size={12}
                    className={`text-zinc-600 group-hover:text-zinc-400 transition-transform duration-200 ${
                      isCollapsed ? "-rotate-90" : ""
                    }`}
                  />
                </button>
              ) : (
                <div className="my-2" />
              )}

              {/* Section items */}
              <div
                className={`space-y-0.5 overflow-hidden transition-all duration-200 ${
                  isCollapsed && !collapsed ? "max-h-0 opacity-0" : "max-h-[500px] opacity-100"
                }`}
              >
                {section.items.map((item) => (
                  <NavLink key={item.href} {...item} />
                ))}
              </div>

              {si < NAV_SECTIONS.length - 1 && (
                <div className="border-b border-zinc-800 my-3" />
              )}
            </div>
          );
        })}
      </nav>

      {/* User section */}
      <div className="border-t border-zinc-800 p-3" ref={userMenuRef}>
        {/* User menu popup — expanded sidebar */}
        {userMenuOpen && !collapsed && (
          <div className="absolute bottom-[72px] left-3 right-3 bg-zinc-900 border border-zinc-700 rounded-xl shadow-xl overflow-hidden z-40">
            {SETUP_MENU_ITEMS.map((item) => (
              <MenuLink key={item.href} {...item} />
            ))}
            <div className="border-t border-zinc-700 my-0.5" />
            {UTILITY_MENU_ITEMS.map((item) => (
              <MenuLink key={item.href} {...item} />
            ))}
          </div>
        )}
        {/* User menu popup — collapsed sidebar */}
        {userMenuOpen && collapsed && (
          <div className="absolute bottom-[72px] left-[72px] w-48 bg-zinc-900 border border-zinc-700 rounded-xl shadow-xl overflow-hidden z-40">
            {SETUP_MENU_ITEMS.map((item) => (
              <MenuLink key={item.href} {...item} />
            ))}
            <div className="border-t border-zinc-700 my-0.5" />
            {UTILITY_MENU_ITEMS.map((item) => (
              <MenuLink key={item.href} {...item} />
            ))}
          </div>
        )}
        <button
          onClick={() => setUserMenuOpen(!userMenuOpen)}
          className={`w-full flex items-center ${collapsed ? "justify-center" : "gap-2.5"} rounded-lg hover:bg-zinc-800 transition-colors p-1.5 -mx-1.5`}
          title={collapsed ? displayName : undefined}
        >
          <div className="w-8 h-8 rounded-full bg-[#EAB308] flex items-center justify-center text-[#0a0a0b] text-xs font-bold shrink-0" style={{ fontFamily: "var(--font-display, sans-serif)" }}>
            {displayInitial}
          </div>
          {!collapsed && (
            <>
              <div className="flex-1 min-w-0 text-left">
                <p className="text-zinc-200 text-xs font-medium truncate">{displayName}</p>
                <p className="text-zinc-600 text-[11px]">Local &middot; Secure &middot; Private</p>
              </div>
              <ChevronUp size={14} className={`text-zinc-500 shrink-0 transition-transform ${userMenuOpen ? "rotate-180" : ""}`} />
            </>
          )}
        </button>
      </div>

      {/* Collapse toggle */}
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="absolute -right-3 top-20 w-6 h-6 bg-white border border-stone-200 rounded-full hidden lg:flex items-center justify-center shadow-sm hover:bg-stone-50 z-30"
      >
        {collapsed ? <ChevronRight size={12} className="text-zinc-500" /> : <ChevronLeft size={12} className="text-zinc-500" />}
      </button>
    </aside>
    </>
  );
}
