"use client";
import { ReactNode } from "react";
import { MessageCircle } from "lucide-react";
import SirHenryName from "@/components/ui/SirHenryName";

interface TemplateItem {
  icon: ReactNode;
  label: string;
  description: string;
  onClick: () => void;
}

interface EmptyStateProps {
  icon: ReactNode;
  title: string;
  description?: string;
  action?: ReactNode;
  /** Sir Henry branded tip shown below the description */
  henryTip?: string;
  /** Pre-filled message for Ask Sir Henry chat. Renders an "Ask Sir Henry" button. */
  askHenryPrompt?: string;
  /** Quick-start template cards shown in a grid below */
  templates?: TemplateItem[];
}

function askHenry(message: string) {
  window.dispatchEvent(new CustomEvent("ask-henry", { detail: { message } }));
}

export default function EmptyState({
  icon,
  title,
  description,
  action,
  henryTip,
  askHenryPrompt,
  templates,
}: EmptyStateProps) {
  return (
    <div className="bg-white rounded-xl border border-dashed border-stone-200 p-12 text-center">
      <div className="text-stone-200 mb-4 flex justify-center">{icon}</div>
      <h3 className="font-semibold text-stone-700 mb-2">{title}</h3>
      {description && (
        <p className="text-stone-400 text-sm mb-6 max-w-md mx-auto">{description}</p>
      )}

      {/* Sir Henry tip callout */}
      {henryTip && (
        <div className="flex items-start gap-3 bg-stone-50 rounded-lg p-4 mb-6 max-w-lg mx-auto text-left">
          <div className="flex-shrink-0 w-7 h-7 rounded-full bg-[#0a0a0b] flex items-center justify-center">
            <span className="text-white font-extrabold text-xs" style={{ fontFamily: "var(--font-display, sans-serif)" }}>H</span>
          </div>
          <p className="text-xs text-stone-600 leading-relaxed">{henryTip}</p>
        </div>
      )}

      {action}

      {/* Ask Sir Henry button */}
      {askHenryPrompt && (
        <button
          onClick={() => askHenry(askHenryPrompt)}
          className="flex items-center gap-1.5 mx-auto mt-4 text-xs text-[#16A34A] hover:text-[#15803D] transition-colors"
        >
          <MessageCircle size={12} />
          Ask <SirHenryName /> for guidance
        </button>
      )}

      {/* Quick-start template cards */}
      {templates && templates.length > 0 && (
        <div className="mt-8 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 max-w-3xl mx-auto">
          {templates.map((t, i) => (
            <button
              key={i}
              onClick={t.onClick}
              className="flex items-start gap-3 text-left p-4 rounded-xl border border-stone-100 hover:border-[#16A34A]/30 hover:bg-green-50/30 transition-all group"
            >
              <div className="flex-shrink-0 w-9 h-9 rounded-lg bg-stone-100 group-hover:bg-green-100 flex items-center justify-center transition-colors">
                {t.icon}
              </div>
              <div className="min-w-0">
                <p className="text-sm font-medium text-stone-700 group-hover:text-[#16A34A] transition-colors">
                  {t.label}
                </p>
                <p className="text-xs text-stone-400 mt-0.5 line-clamp-2">{t.description}</p>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
