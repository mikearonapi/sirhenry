"use client";
import Link from "next/link";
import {
  CheckCircle, Circle, CircleDot, MinusCircle, FileText, MessageCircle,
} from "lucide-react";
import type { TaxChecklist, Document as DocType } from "@/types/api";
import ProgressBar from "@/components/ui/ProgressBar";
import Card from "@/components/ui/Card";

const TAX_FORM_IDS = new Set([
  "import_w2", "import_1099_nec", "import_1099_div", "import_1099_b", "import_1099_int",
  "import_k1", "import_1099_r", "import_1099_g", "import_1099_k", "import_1098",
]);

function askHenry(message: string) {
  window.dispatchEvent(new CustomEvent("ask-henry", { detail: { message } }));
}

const CATEGORY_LABELS: Record<string, string> = {
  documents: "Data Collection",
  preparation: "Tax Preparation",
  filing: "Filing",
  payments: "Payments",
};

const CHECKLIST_LINKS: Record<string, { href: string; label: string }> = {
  import_transactions: { href: "/import", label: "Go to Import" },
  categorize_transactions: { href: "/transactions", label: "View Transactions" },
  review_business_expenses: { href: "/transactions?segment=business", label: "Review Business Expenses" },
  run_ai_analysis: { href: "/tax-strategy", label: "Go to Tax Strategy" },
};

interface Props {
  checklist: TaxChecklist;
  documents: DocType[];
  year: number;
}

export default function FilingChecklist({ checklist, documents, year }: Props) {
  const nonFormItems = checklist.items.filter((i) => !TAX_FORM_IDS.has(i.id));
  const yearDocs = documents.filter((d) => d.tax_year === year);

  return (
    <div className="space-y-5">
      {/* Documents on file */}
      <Card padding="lg">
        <div className="flex items-center gap-2 mb-4">
          <FileText size={18} className="text-amber-500" />
          <h3 className="text-sm font-semibold text-stone-800">Documents on File ({yearDocs.length})</h3>
        </div>
        {yearDocs.length === 0 ? (
          <p className="text-sm text-stone-400 text-center py-4">No tax documents uploaded for {year}.</p>
        ) : (
          <div className="space-y-1.5">
            {yearDocs.map((doc) => (
              <div key={doc.id} className="flex items-center justify-between py-2 px-3 rounded-lg hover:bg-stone-50 text-sm">
                <div className="flex items-center gap-3">
                  <FileText size={16} className="text-stone-400 flex-shrink-0" />
                  <div>
                    <p className="font-medium text-stone-700 truncate max-w-xs">{doc.filename}</p>
                    <p className="text-xs text-stone-400 capitalize">{(doc.document_type === "processing" ? "tax document" : doc.document_type).replace(/_/g, " ")} · {doc.status}</p>
                  </div>
                </div>
                <StatusBadge status={doc.status} />
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* Filing readiness */}
      {nonFormItems.length > 0 && (
        <Card padding="lg">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-stone-800">Filing Readiness</h3>
            <span className="text-sm font-semibold text-stone-600">{checklist.completed}/{checklist.total} complete</span>
          </div>
          <div className="mb-4">
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-sm text-stone-600">Overall Progress</span>
              <span className="text-sm font-semibold text-stone-800">{checklist.progress_pct}%</span>
            </div>
            <ProgressBar value={checklist.progress_pct} size="md" />
          </div>

          {(["documents", "preparation", "filing", "payments"] as const).map((cat) => {
            const catItems = nonFormItems.filter((ci) => ci.category === cat);
            if (catItems.length === 0) return null;
            return (
              <div key={cat} className="mb-4 last:mb-0">
                <h4 className="text-xs font-semibold text-stone-500 uppercase tracking-wide mb-2">{CATEGORY_LABELS[cat]}</h4>
                <div className="space-y-1.5">
                  {catItems.map((ci) => (
                    <div key={ci.id} className={`flex items-start gap-3 rounded-lg px-3 py-2 text-sm ${
                      ci.status === "complete" ? "bg-green-50/50" : ci.status === "partial" ? "bg-amber-50/50" : ci.status === "not_applicable" ? "bg-stone-50/50 opacity-50" : "bg-stone-50/30"
                    }`}>
                      <div className="mt-0.5 flex-shrink-0">
                        {ci.status === "complete" ? <CheckCircle size={16} className="text-green-500" /> :
                         ci.status === "partial" ? <CircleDot size={16} className="text-amber-500" /> :
                         ci.status === "not_applicable" ? <MinusCircle size={16} className="text-stone-300" /> :
                         <Circle size={16} className="text-stone-300" />}
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className={`font-medium ${ci.status === "complete" ? "text-green-800" : ci.status === "not_applicable" ? "text-stone-400" : "text-stone-700"}`}>{ci.label}</p>
                        {ci.detail && <p className="text-xs text-stone-400 mt-0.5">{ci.detail}</p>}
                        {ci.status !== "complete" && ci.status !== "not_applicable" && CHECKLIST_LINKS[ci.id] && (
                          <Link href={CHECKLIST_LINKS[ci.id].href} className="text-xs text-[#16A34A] hover:underline mt-0.5 inline-block">
                            {CHECKLIST_LINKS[ci.id].label} &rarr;
                          </Link>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </Card>
      )}

      <button
        type="button"
        onClick={() => askHenry("Looking at my tax filing checklist, what's the most important item I should work on next?")}
        className="flex items-center gap-1.5 text-xs text-[#16A34A] hover:underline print:hidden"
      >
        <MessageCircle size={12} /> What should I focus on next?
      </button>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    completed: "bg-green-50 text-green-600",
    processing: "bg-blue-50 text-blue-600",
    pending: "bg-stone-50 text-stone-500",
    failed: "bg-red-50 text-red-600",
    duplicate: "bg-amber-50 text-amber-600",
  };
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full ${colors[status] ?? "bg-stone-50 text-stone-500"}`}>
      {status}
    </span>
  );
}
