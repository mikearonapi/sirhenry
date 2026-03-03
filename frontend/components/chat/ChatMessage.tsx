"use client";
import { User, Zap, CheckCircle2, Search } from "lucide-react";
import type { ChatAction } from "@/types/api";
import { TOOL_ICONS, TOOL_DONE_LABELS } from "./constants";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface DisplayMessage {
  role: "user" | "assistant";
  content: string;
  actions?: ChatAction[];
  timestamp: Date;
}

// ---------------------------------------------------------------------------
// Markdown renderer
// ---------------------------------------------------------------------------

export function renderMarkdown(text: string): string {
  // Escape HTML entities first to prevent XSS, but preserve markdown syntax
  let html = text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

  // Code blocks (```) — must come before inline code
  html = html.replace(/```(\w*)\n([\s\S]*?)```/g, (_m, _lang, code) =>
    `<pre class="bg-stone-800 text-stone-100 rounded-lg p-3 my-2 text-xs overflow-x-auto font-mono"><code>${code.trim()}</code></pre>`
  );

  // Tables: detect lines with |
  html = html.replace(
    /(?:^|\n)(\|.+\|)\n(\|[-| :]+\|)\n((?:\|.+\|\n?)+)/gm,
    (_m, header: string, _sep: string, bodyStr: string) => {
      const headerCells = header.split("|").filter((c: string) => c.trim());
      const rows = bodyStr.trim().split("\n");
      let table = '<table class="w-full text-xs my-2 border-collapse"><thead><tr>';
      headerCells.forEach((c: string) => {
        table += `<th class="text-left px-2 py-1.5 bg-stone-100 font-semibold text-stone-600 border-b border-stone-200">${c.trim()}</th>`;
      });
      table += "</tr></thead><tbody>";
      rows.forEach((row: string) => {
        const cells = row.split("|").filter((c: string) => c.trim());
        table += '<tr class="border-b border-stone-50">';
        cells.forEach((c: string) => {
          table += `<td class="px-2 py-1.5 text-stone-700">${c.trim()}</td>`;
        });
        table += "</tr>";
      });
      table += "</tbody></table>";
      return table;
    }
  );

  // Headers
  html = html.replace(/^### (.+)$/gm, '<h3 class="font-semibold text-stone-800 text-sm mt-3 mb-1">$1</h3>');
  html = html.replace(/^## (.+)$/gm, '<h2 class="font-bold text-stone-900 text-sm mt-3 mb-1.5">$1</h2>');

  // Bold
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong class="font-semibold text-stone-900">$1</strong>');

  // Italic
  html = html.replace(/(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)/g, "<em>$1</em>");

  // Inline code
  html = html.replace(/`([^`]+)`/g, '<code class="bg-zinc-800 text-green-400 px-1 py-0.5 rounded text-xs font-mono">$1</code>');

  // Bullet lists
  html = html.replace(/^[•\-]\s+(.+)$/gm, '<li class="flex items-start gap-1.5 text-zinc-300"><span class="text-green-400 mt-0.5 flex-shrink-0">•</span><span>$1</span></li>');
  html = html.replace(/((?:<li[^>]*>.*<\/li>\s*)+)/g, '<ul class="space-y-0.5 my-1.5">$1</ul>');

  // Numbered lists
  html = html.replace(/^(\d+)\.\s+(.+)$/gm, '<li class="flex items-start gap-1.5 text-zinc-300"><span class="text-green-400 font-semibold flex-shrink-0 min-w-[1.2em]">$1.</span><span>$2</span></li>');

  // Line breaks
  html = html.replace(/\n\n/g, '</p><p class="my-1.5">');
  html = html.replace(/\n/g, "<br/>");

  // Wrap in paragraph if not already wrapped
  if (!html.startsWith("<")) {
    html = `<p class="my-1.5">${html}</p>`;
  }

  return html;
}

// ---------------------------------------------------------------------------
// SirHenryAvatar
// ---------------------------------------------------------------------------

export function SirHenryAvatar({ size = 8 }: { size?: number }) {
  const px = size * 4;
  return (
    <div
      className="rounded-full bg-[#EAB308] flex items-center justify-center flex-shrink-0 shadow-sm ring-1 ring-[#EAB308]/40"
      style={{ width: px, height: px }}
    >
      <span
        className="font-bold text-[#0a0a0b] leading-none"
        style={{ fontSize: px * 0.44, fontFamily: "var(--font-display, sans-serif)" }}
      >
        H
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// ActionCard — renders a single tool-call result card
// ---------------------------------------------------------------------------

function ActionCard({ action }: { action: ChatAction }) {
  const Icon = TOOL_ICONS[action.tool] || Zap;
  const label = TOOL_DONE_LABELS[action.tool] || action.tool;
  const isUpdate = action.tool === "recategorize_transaction";

  let detail = "";
  if (isUpdate && action.result_preview) {
    try {
      const parsed = JSON.parse(action.result_preview);
      if (parsed.changes) {
        detail = (parsed.changes as string[]).join(", ");
      }
    } catch { /* ignore parse errors */ }
  }

  return (
    <div className={`flex items-center gap-2.5 px-3 py-2 rounded-lg border text-xs ${
      isUpdate
        ? "bg-green-50 border-green-200 text-green-700"
        : "bg-stone-50 border-stone-150 text-stone-500"
    }`}>
      <div className={`w-6 h-6 rounded-md flex items-center justify-center ${
        isUpdate ? "bg-green-100" : "bg-stone-100"
      }`}>
        {isUpdate ? <CheckCircle2 size={13} /> : <Icon size={13} />}
      </div>
      <div className="flex-1 min-w-0">
        <span className="font-medium">{label}</span>
        {detail && <span className="text-green-600 ml-1.5">— {detail}</span>}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// ChatMessage — renders a single user or assistant message
// ---------------------------------------------------------------------------

export interface ChatMessageProps {
  message: DisplayMessage;
}

export default function ChatMessage({ message }: ChatMessageProps) {
  if (message.role === "user") {
    return (
      <div className="flex gap-3 items-start justify-end">
        <div className="max-w-[80%]">
          <div className="bg-[#1C1C1F] border border-zinc-700 text-zinc-100 px-4 py-2.5 rounded-2xl rounded-br-md text-[13.5px] leading-relaxed">
            {message.content}
          </div>
          <p className="text-[10px] text-zinc-700 mt-1 text-right">
            {message.timestamp.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
          </p>
        </div>
        <div className="w-8 h-8 rounded-full bg-zinc-800 border border-zinc-700 flex items-center justify-center flex-shrink-0">
          <User size={15} className="text-zinc-400" />
        </div>
      </div>
    );
  }

  return (
    <div className="flex gap-3 items-start">
      <SirHenryAvatar size={8} />
      <div className="flex-1 min-w-0 max-w-[90%]">
        {/* Action cards */}
        {message.actions && message.actions.length > 0 && (
          <div className="mb-2.5 space-y-1.5">
            {message.actions.map((action, ai) => (
              <ActionCard key={ai} action={action} />
            ))}
          </div>
        )}

        {/* Message content */}
        <div
          className="prose-chat text-[13.5px] leading-relaxed text-zinc-300"
          dangerouslySetInnerHTML={{ __html: renderMarkdown(message.content) }}
        />

        <p className="text-[10px] text-zinc-700 mt-1.5">
          {message.timestamp.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
        </p>
      </div>
    </div>
  );
}
