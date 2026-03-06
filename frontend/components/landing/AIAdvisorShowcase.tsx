import { DEMO_CHAT_EXCHANGES } from "./demo-data";
import MockupFrame from "./MockupFrame";
import SirHenryName from "@/components/ui/SirHenryName";

export default function AIAdvisorShowcase() {
  const chat = DEMO_CHAT_EXCHANGES[1]; // RSU vest question — most impressive

  return (
    <MockupFrame title="SirHENRY \u2014 Sir Henry AI" fadeBottom={false}>
      <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
        {/* Chat messages — main area */}
        <div className="md:col-span-3 space-y-4">
          {/* User message */}
          <div className="flex gap-3">
            <div className="w-7 h-7 rounded-full bg-[#27272A] flex items-center justify-center shrink-0 text-[10px] font-bold text-[#9CA3AF]">
              S
            </div>
            <div className="flex-1">
              <p className="text-[10px] text-[#6B7280] mb-1">Sarah</p>
              <div className="bg-[#1C1C1F] rounded-lg rounded-tl-sm p-3 border border-[#27272A]">
                <p className="text-[#D1D5DB] text-sm">{chat.question}</p>
              </div>
            </div>
          </div>

          {/* Tool calls */}
          <div className="flex gap-3">
            <div className="w-7 shrink-0" />
            <div className="flex gap-2 flex-wrap">
              {chat.tools.map((tool) => (
                <span
                  key={tool}
                  className="inline-flex items-center gap-1.5 text-[10px] font-medium px-2.5 py-1 rounded-full bg-[#22C55E]/10 text-[#22C55E] border border-[#22C55E]/20"
                >
                  <span className="w-1.5 h-1.5 rounded-full bg-[#22C55E]" />
                  {tool.replace(/_/g, " ")}
                </span>
              ))}
            </div>
          </div>

          {/* Assistant message */}
          <div className="flex gap-3">
            <div className="w-7 h-7 rounded-full bg-[#22C55E]/20 flex items-center justify-center shrink-0">
              <span className="text-[10px] font-bold text-[#22C55E]">H</span>
            </div>
            <div className="flex-1">
              <p className="text-[10px] text-[#6B7280] mb-1"><SirHenryName /></p>
              <div className="bg-[#1C1C1F] rounded-lg rounded-tl-sm p-3 border border-[#22C55E]/20">
                <p className="text-[#D1D5DB] text-sm leading-relaxed">{chat.answer}</p>
              </div>
            </div>
          </div>

          {/* Input bar */}
          <div className="flex items-center gap-2 bg-[#1C1C1F] rounded-lg p-3 border border-[#27272A]">
            <span className="text-[#6B7280] text-sm flex-1">Ask Sir Henry anything...</span>
            <div className="w-7 h-7 rounded-lg bg-[#22C55E] flex items-center justify-center shrink-0">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round">
                <path d="M22 2L11 13" />
                <path d="M22 2L15 22L11 13L2 9L22 2Z" />
              </svg>
            </div>
          </div>
        </div>

        {/* Suggestion sidebar */}
        <div className="md:col-span-2 space-y-3">
          <p className="text-[#6B7280] text-[10px] font-semibold uppercase tracking-wider">
            Suggested questions
          </p>
          {DEMO_CHAT_EXCHANGES.map((ex, i) => (
            <div
              key={i}
              className="bg-[#1C1C1F] rounded-lg p-3 border border-[#27272A] hover:border-[#22C55E]/30 transition-colors cursor-default"
            >
              <p className="text-[#D1D5DB] text-xs leading-relaxed">{ex.question}</p>
            </div>
          ))}
        </div>
      </div>
    </MockupFrame>
  );
}
