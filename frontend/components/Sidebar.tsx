"use client";
import Link from "next/link";
import Image from "next/image";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard, List, Upload,
  Wallet, ArrowLeftRight, TrendingUp,
  RotateCcw, Target, FileBarChart, Building2,
  PieChart, ChevronLeft, ChevronRight, Activity, X,
  Compass, ClipboardCheck, FileText, BarChart3,
  Briefcase, Users, Settings, Zap, Landmark, Calendar, ShieldCheck,
  ChevronUp,
} from "lucide-react";
import { useState, useRef, useEffect } from "react";

const NAV_SECTIONS = [
  {
    label: null,
    items: [
      { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
    ],
  },
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
      { href: "/investments", label: "Investments", icon: TrendingUp },
      { href: "/retirement", label: "Retirement", icon: Landmark },
      { href: "/market", label: "Market Pulse", icon: Activity },
      { href: "/equity-comp", label: "Equity Comp", icon: Briefcase },
      { href: "/life-planner", label: "Life Planner", icon: Compass },
    ],
  },
  {
    label: "Taxes",
    items: [
      { href: "/tax-strategy", label: "Tax Strategy", icon: Zap },
      { href: "/tax", label: "Tax Checklist", icon: ClipboardCheck },
      { href: "/tax-reports", label: "Tax Reports", icon: FileText },
    ],
  },
  {
    label: "Setup",
    items: [
      { href: "/accounts", label: "Accounts", icon: Building2 },
      { href: "/household", label: "Household", icon: Users },
      { href: "/life-events", label: "Life Events", icon: Calendar },
      { href: "/business", label: "Business", icon: Briefcase },
      { href: "/insurance", label: "Policies", icon: ShieldCheck },
    ],
  },
];

const USER_MENU_ITEMS = [
  { href: "/reports", label: "Reports", icon: FileBarChart },
  { href: "/statements", label: "Statements", icon: BarChart3 },
  { href: "/import", label: "Data & Docs", icon: Upload },
  { href: "/admin", label: "Settings", icon: Settings },
];

export default function Sidebar({ isOpen, onClose }: { isOpen: boolean; onClose: () => void }) {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const userMenuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (userMenuRef.current && !userMenuRef.current.contains(e.target as Node)) {
        setUserMenuOpen(false);
      }
    }
    if (userMenuOpen) document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [userMenuOpen]);

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
      <div className={`flex items-center ${collapsed ? "justify-center" : "gap-2.5"} px-4 h-16 border-b border-zinc-800`}>
        <Image
          src="/henry-icon-1024.png"
          alt="Henry"
          width={32}
          height={32}
          className="rounded-lg shrink-0"
          priority
        />
        {!collapsed && (
          <div className="min-w-0">
            <p className="text-white font-semibold text-sm leading-tight truncate" style={{ fontFamily: "var(--font-display, sans-serif)" }}>Henry</p>
            <p className="text-zinc-500 text-[11px]">sirhenry.app</p>
          </div>
        )}
      </div>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto px-2.5 py-3 space-y-4">
        {NAV_SECTIONS.map((section, si) => (
          <div key={si}>
            {section.label && !collapsed && (
              <p className="text-[10px] font-semibold uppercase tracking-wider text-zinc-600 px-2.5 mb-1.5">{section.label}</p>
            )}
            <div className="space-y-0.5">
              {section.items.map(({ href, label, icon: Icon }) => {
                const active = pathname === href || (href !== "/dashboard" && pathname.startsWith(href));
                return (
                  <Link
                    key={href}
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
              })}
            </div>
            {si < NAV_SECTIONS.length - 1 && (
              <div className="border-b border-zinc-800 mt-3" />
            )}
          </div>
        ))}
      </nav>

      {/* User section */}
      <div className="border-t border-zinc-800 p-3" ref={userMenuRef}>
        {/* User menu popup */}
        {userMenuOpen && !collapsed && (
          <div className="absolute bottom-[72px] left-3 right-3 bg-zinc-900 border border-zinc-700 rounded-xl shadow-xl overflow-hidden z-40">
            {USER_MENU_ITEMS.map(({ href, label, icon: Icon }) => (
              <Link
                key={href}
                href={href}
                onClick={() => { setUserMenuOpen(false); onClose(); }}
                className="flex items-center gap-2.5 px-3 py-2.5 text-[13px] text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200 transition-colors"
              >
                <Icon size={15} className="shrink-0" />
                <span>{label}</span>
              </Link>
            ))}
          </div>
        )}
        {userMenuOpen && collapsed && (
          <div className="absolute bottom-[72px] left-[72px] w-44 bg-zinc-900 border border-zinc-700 rounded-xl shadow-xl overflow-hidden z-40">
            {USER_MENU_ITEMS.map(({ href, label, icon: Icon }) => (
              <Link
                key={href}
                href={href}
                onClick={() => { setUserMenuOpen(false); onClose(); }}
                className="flex items-center gap-2.5 px-3 py-2.5 text-[13px] text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200 transition-colors"
              >
                <Icon size={15} className="shrink-0" />
                <span>{label}</span>
              </Link>
            ))}
          </div>
        )}
        <button
          onClick={() => setUserMenuOpen(!userMenuOpen)}
          className={`w-full flex items-center ${collapsed ? "justify-center" : "gap-2.5"} rounded-lg hover:bg-zinc-800 transition-colors p-1.5 -mx-1.5`}
          title={collapsed ? "Mike Aron" : undefined}
        >
          <div className="w-8 h-8 rounded-full bg-[#EAB308] flex items-center justify-center text-[#0a0a0b] text-xs font-bold shrink-0" style={{ fontFamily: "var(--font-display, sans-serif)" }}>
            M
          </div>
          {!collapsed && (
            <>
              <div className="flex-1 min-w-0 text-left">
                <p className="text-zinc-200 text-xs font-medium truncate">Mike Aron</p>
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
