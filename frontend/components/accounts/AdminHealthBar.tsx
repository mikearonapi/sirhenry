"use client";

import type { AdminHealthSection } from "./accounts-types";

interface AdminHealthBarProps {
  adminHealth: AdminHealthSection[];
  accountsCount: number;
}

export default function AdminHealthBar({ adminHealth, accountsCount }: AdminHealthBarProps) {
  const accountStatus = accountsCount > 0 ? "complete" : "empty";

  return (
    <div className="bg-white border border-stone-100 rounded-xl p-4 shadow-sm">
      <p className="text-xs font-semibold text-stone-700 mb-3">Admin Setup Status</p>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-2">
        <a href="/accounts" className={`flex items-center gap-2 p-2.5 rounded-lg border text-xs transition-colors hover:opacity-80 ${
          accountStatus === "complete" ? "bg-green-50 border-green-100" : "bg-stone-50 border-stone-200"
        }`}>
          <div className={`w-5 h-5 rounded-full flex items-center justify-center text-white text-[9px] font-bold shrink-0 ${accountStatus === "complete" ? "bg-green-500" : "bg-stone-300"}`}>
            {accountStatus === "complete" ? "✓" : "!"}
          </div>
          <div>
            <p className={`font-semibold ${accountStatus === "complete" ? "text-green-700" : "text-stone-600"}`}>Accounts</p>
            <p className={`text-[10px] ${accountStatus === "complete" ? "text-green-600" : "text-stone-400"}`}>
              {accountsCount > 0 ? `${accountsCount} items` : "Connect accounts"}
            </p>
          </div>
        </a>
        {adminHealth.map((section) => (
          <a key={section.href} href={section.href} className={`flex items-center gap-2 p-2.5 rounded-lg border text-xs transition-colors hover:opacity-80 ${
            section.status === "complete" ? "bg-green-50 border-green-100" :
            section.status === "partial" ? "bg-amber-50 border-amber-100" :
            "bg-stone-50 border-stone-200"
          }`}>
            <div className={`w-5 h-5 rounded-full flex items-center justify-center text-white text-[9px] font-bold shrink-0 ${
              section.status === "complete" ? "bg-green-500" :
              section.status === "partial" ? "bg-amber-400" :
              "bg-stone-300"
            }`}>
              {section.status === "complete" ? "✓" : section.status === "partial" ? "~" : "!"}
            </div>
            <div>
              <p className={`font-semibold ${
                section.status === "complete" ? "text-green-700" :
                section.status === "partial" ? "text-amber-700" :
                "text-stone-600"
              }`}>{section.label}</p>
              <p className={`text-[10px] ${
                section.status === "complete" ? "text-green-600" :
                section.status === "partial" ? "text-amber-600" :
                "text-stone-400"
              }`}>
                {section.count > 0 ? `${section.count} item${section.count !== 1 ? "s" : ""}` : section.action}
              </p>
            </div>
          </a>
        ))}
      </div>
    </div>
  );
}
