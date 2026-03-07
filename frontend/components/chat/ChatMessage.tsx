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

/**
 * Streaming-safe markdown renderer.
 * Detects incomplete multi-line constructs (tables, code blocks) that are
 * still being built token-by-token and replaces them with a subtle animated
 * indicator rather than showing raw `| pipe |` or ``` syntax.
 */
export function renderStreamingMarkdown(text: string, dark = true): string {
  const lines = text.split("\n");

  // ── 1. Detect trailing incomplete table ──────────────────────────────────
  // Walk backwards past blank lines to find the last non-blank line.
  // If it starts with `|`, we're mid-table.
  let tableStart = -1;
  for (let i = lines.length - 1; i >= 0; i--) {
    const t = lines[i].trim();
    if (t === "") continue;
    if (t.startsWith("|")) {
      tableStart = i;
    } else {
      break;
    }
  }

  if (tableStart !== -1) {
    const tableLines = lines.slice(tableStart).filter((l) => l.trim());
    const hasSeparator = tableLines.some((l) => /^\|[\s\-|: ]+\|$/.test(l.trim()));
    // A complete table needs header + separator + ≥1 data row (3 pipe-lines total)
    const pipeLineCount = tableLines.filter((l) => l.trim().startsWith("|")).length;
    const isComplete = hasSeparator && pipeLineCount >= 3;

    if (!isComplete) {
      const safeText = lines.slice(0, tableStart).join("\n");
      const dotCls = dark ? "bg-zinc-500" : "bg-text-muted";
      const lblCls = dark ? "text-zinc-500" : "text-text-muted";
      const dots = [0, 150, 300]
        .map((d) => `<span class="w-1 h-1 rounded-full ${dotCls} animate-bounce" style="animation-delay:${d}ms"></span>`)
        .join("");
      const indicator = `<div class="flex items-center gap-2 mt-2 ${lblCls} text-xs"><span class="flex gap-0.5">${dots}</span><span>Building table…</span></div>`;
      return (safeText.trim() ? renderMarkdown(safeText, dark) : "") + indicator;
    }
  }

  // ── 2. Detect unclosed fenced code block ─────────────────────────────────
  const fenceCount = (text.match(/^```/gm) || []).length;
  if (fenceCount % 2 !== 0) {
    // Odd number of ``` fences — the last one is unclosed; render up to it
    const lastFence = text.lastIndexOf("\n```");
    const safeText = lastFence > 0 ? text.slice(0, lastFence) : text;
    const dotCls = dark ? "bg-zinc-500" : "bg-text-muted";
    const lblCls = dark ? "text-zinc-500" : "text-text-muted";
    const dots = [0, 150, 300]
      .map((d) => `<span class="w-1 h-1 rounded-full ${dotCls} animate-bounce" style="animation-delay:${d}ms"></span>`)
      .join("");
    const indicator = `<div class="flex items-center gap-2 mt-2 ${lblCls} text-xs"><span class="flex gap-0.5">${dots}</span><span>Loading…</span></div>`;
    return (safeText.trim() ? renderMarkdown(safeText, dark) : "") + indicator;
  }

  return renderMarkdown(text, dark);
}

export function renderMarkdown(text: string, dark = true): string {
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
        table += `<th class="text-left px-2 py-1.5 bg-surface font-semibold text-text-secondary border-b border-border">${c.trim()}</th>`;
      });
      table += "</tr></thead><tbody>";
      rows.forEach((row: string) => {
        const cells = row.split("|").filter((c: string) => c.trim());
        table += '<tr class="border-b border-border-light">';
        cells.forEach((c: string) => {
          table += `<td class="px-2 py-1.5 text-text-secondary">${c.trim()}</td>`;
        });
        table += "</tr>";
      });
      table += "</tbody></table>";
      return table;
    }
  );

  // Headers
  html = html.replace(/^### (.+)$/gm, '<h3 class="font-semibold text-text-primary text-sm mt-3 mb-1">$1</h3>');
  html = html.replace(/^## (.+)$/gm, '<h2 class="font-bold text-text-primary text-sm mt-3 mb-1.5">$1</h2>');

  // Bold
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong class="font-semibold text-text-primary">$1</strong>');

  // Italic
  html = html.replace(/(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)/g, "<em>$1</em>");

  // Inline code
  const codeClass = dark
    ? "bg-zinc-800 text-green-400 px-1 py-0.5 rounded text-xs font-mono"
    : "bg-surface text-green-700 px-1 py-0.5 rounded text-xs font-mono";
  html = html.replace(/`([^`]+)`/g, `<code class="${codeClass}">$1</code>`);

  // Bullet lists
  const listText = dark ? "text-zinc-300" : "text-text-secondary";
  const bulletColor = dark ? "text-green-400" : "text-green-600";
  html = html.replace(
    /^[•\-]\s+(.+)$/gm,
    `<li class="flex items-start gap-1.5 ${listText}"><span class="${bulletColor} mt-0.5 flex-shrink-0">•</span><span>$1</span></li>`
  );
  html = html.replace(/((?:<li[^>]*>.*<\/li>\s*)+)/g, '<ul class="space-y-0.5 my-1.5">$1</ul>');

  // Numbered lists
  html = html.replace(
    /^(\d+)\.\s+(.+)$/gm,
    `<li class="flex items-start gap-1.5 ${listText}"><span class="${bulletColor} font-semibold flex-shrink-0 min-w-[1.2em]">$1.</span><span>$2</span></li>`
  );

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
      className="rounded-full bg-[#0a0a0b] flex items-center justify-center flex-shrink-0 shadow-sm ring-1 ring-zinc-700"
      style={{ width: px, height: px }}
    >
      <span
        className="font-extrabold text-white leading-none"
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

const WRITE_TOOLS = new Set([
  "recategorize_transaction",
  "update_transaction",
  "create_transaction",
  "exclude_transactions",
  "manage_budget",
  "manage_goal",
  "create_reminder",
  "update_asset_value",
]);

function ActionCard({ action }: { action: ChatAction }) {
  const Icon = TOOL_ICONS[action.tool] || Zap;
  const label = TOOL_DONE_LABELS[action.tool] || action.tool;
  const isUpdate = WRITE_TOOLS.has(action.tool);

  let detail = "";
  if (isUpdate && action.result_preview) {
    try {
      const parsed = JSON.parse(action.result_preview);
      if (parsed.changes) {
        detail = (parsed.changes as string[]).join(", ");
      } else if (parsed.message) {
        detail = parsed.message as string;
      } else if (parsed.action) {
        detail = parsed.action as string;
      }
    } catch { /* ignore parse errors */ }
  }

  return (
    <div className={`flex items-center gap-2.5 px-3 py-2 rounded-lg border text-xs ${
      isUpdate
        ? "bg-green-50 border-green-200 text-green-700"
        : "bg-surface border-card-border text-text-secondary"
    }`}>
      <div className={`w-6 h-6 rounded-md flex items-center justify-center ${
        isUpdate ? "bg-green-100" : "bg-surface"
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
  dark?: boolean;
}

export default function ChatMessage({ message, dark = true }: ChatMessageProps) {
  if (message.role === "user") {
    const bubbleClass = dark
      ? "bg-[#1C1C1F] border border-zinc-700 text-zinc-100"
      : "bg-surface border border-border text-text-primary";
    const tsClass = dark ? "text-zinc-700" : "text-text-muted";
    const avatarClass = dark
      ? "bg-zinc-800 border-zinc-700 text-zinc-400"
      : "bg-border border-border text-text-secondary";

    return (
      <div className="flex gap-3 items-start justify-end">
        <div className="max-w-[80%]">
          <div className={`${bubbleClass} px-4 py-2.5 rounded-2xl rounded-br-md text-[13.5px] leading-relaxed`}>
            {message.content}
          </div>
          <p className={`text-xs ${tsClass} mt-1 text-right`}>
            {message.timestamp.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
          </p>
        </div>
        <div className={`w-8 h-8 rounded-full border flex items-center justify-center flex-shrink-0 ${avatarClass}`}>
          <User size={15} />
        </div>
      </div>
    );
  }

  const proseClass = dark ? "text-zinc-300" : "text-text-secondary";
  const tsClass = dark ? "text-zinc-700" : "text-text-muted";

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
          className={`prose-chat text-[13.5px] leading-relaxed ${proseClass}`}
          dangerouslySetInnerHTML={{ __html: renderMarkdown(message.content, dark) }}
        />

        <p className={`text-xs ${tsClass} mt-1.5`}>
          {message.timestamp.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
        </p>
      </div>
    </div>
  );
}
