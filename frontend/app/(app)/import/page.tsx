"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  Upload,
  FileText,
  CheckCircle,
  XCircle,
  Clock,
  Loader2,
  RefreshCw,
  AlertCircle,
  Sparkles,
  Trash2,
  Search,
  Database,
} from "lucide-react";
import { getDocuments, deleteDocument, runCategorization, uploadFile } from "@/lib/api";
import { formatDate, statusColor } from "@/lib/utils";
import type { Document, ImportResult } from "@/types/api";
import { getErrorMessage } from "@/lib/errors";

type DocumentType = "credit_card" | "tax_document" | "investment" | "amazon" | "monarch";

const DOC_TYPE_OPTIONS: { value: DocumentType; label: string; accept: string; hint: string }[] = [
  {
    value: "credit_card",
    label: "Credit Card Statement",
    accept: ".csv",
    hint: "Chase, Amex, Capital One, Citi, BofA, Discover CSV formats supported",
  },
  {
    value: "tax_document",
    label: "Tax Document",
    accept: ".pdf",
    hint: "W-2, 1099-NEC, 1099-DIV, 1099-B, 1099-INT",
  },
  {
    value: "investment",
    label: "Investment Statement",
    accept: ".pdf,.csv",
    hint: "Fidelity, Schwab, Vanguard, E*Trade brokerage statements",
  },
  {
    value: "amazon",
    label: "Amazon Orders",
    accept: ".csv",
    hint: "Amazon Order History CSV (from amazon.com/privacy/data-request). AI categorizes every item.",
  },
  {
    value: "monarch",
    label: "Monarch Money Export",
    accept: ".csv",
    hint: "Monarch Money transaction export. Accounts auto-created; duplicates with card CSVs auto-detected.",
  },
];

const STATUS_ICONS: Record<string, React.ReactNode> = {
  completed: <CheckCircle size={14} className="text-green-500" />,
  failed: <XCircle size={14} className="text-red-500" />,
  processing: <Loader2 size={14} className="animate-spin text-yellow-500" />,
  pending: <Clock size={14} className="text-stone-400" />,
  duplicate: <AlertCircle size={14} className="text-stone-400" />,
};

export default function ImportPage() {
  const [activeTab, setActiveTab] = useState<"upload" | "vault">("upload");
  const [docType, setDocType] = useState<DocumentType>("credit_card");
  const [accountName, setAccountName] = useState("");
  const [institution, setInstitution] = useState("");
  const [segment, setSegment] = useState<"personal" | "business">("personal");
  const [taxYear, setTaxYear] = useState<number | undefined>();
  const [runCategorize, setRunCategorize] = useState(true);

  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [results, setResults] = useState<ImportResult[]>([]);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [docsLoading, setDocsLoading] = useState(true);
  const [categorizingYear, setCategorizingYear] = useState<number | undefined>();
  const [catResult, setCatResult] = useState<{ categorized: number; skipped: number; errors: number } | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Document vault state
  const [vaultSearch, setVaultSearch] = useState("");
  const [vaultTypeFilter, setVaultTypeFilter] = useState("");
  const [vaultStatusFilter, setVaultStatusFilter] = useState("");
  const [deletingId, setDeletingId] = useState<number | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const selectedDocType = DOC_TYPE_OPTIONS.find((d) => d.value === docType)!;
  const currentYear = new Date().getFullYear();

  const loadDocuments = useCallback(async () => {
    setDocsLoading(true);
    try {
      const res = await getDocuments({ limit: 500 });
      setDocuments(res.items);
    } catch (e: unknown) {
      setError(getErrorMessage(e));
    } finally {
      setDocsLoading(false);
    }
  }, []);

  async function handleDeleteDocument(id: number) {
    if (!confirm("Delete this document record? Imported transactions will NOT be removed.")) return;
    setDeletingId(id);
    try {
      await deleteDocument(id);
      setDocuments((prev) => prev.filter((d) => d.id !== id));
    } catch (e: unknown) {
      setError(getErrorMessage(e));
    } finally {
      setDeletingId(null);
    }
  }

  const filteredDocs = documents.filter((d) => {
    if (vaultSearch && !d.filename.toLowerCase().includes(vaultSearch.toLowerCase())) return false;
    if (vaultTypeFilter && d.document_type !== vaultTypeFilter) return false;
    if (vaultStatusFilter && d.status !== vaultStatusFilter) return false;
    return true;
  });

  useEffect(() => { loadDocuments(); }, [loadDocuments]);

  async function handleFiles(files: FileList | null) {
    if (!files || files.length === 0) return;
    setUploading(true);
    const newResults: ImportResult[] = [];
    for (const file of Array.from(files)) {
      try {
        const result = await uploadFile(file, docType, {
          accountName,
          institution,
          segment,
          taxYear,
          runCategorize,
        });
        newResults.push(result);
      } catch (e: unknown) {
        newResults.push({
          document_id: 0,
          filename: file.name,
          status: "error",
          transactions_imported: 0,
          transactions_skipped: 0,
          message: e instanceof Error ? e.message : "Upload failed",
        });
      }
    }
    setResults((prev) => [...newResults, ...prev]);
    setUploading(false);
    loadDocuments();
  }

  function onDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragging(false);
    handleFiles(e.dataTransfer.files);
  }

  async function handleRunCategorization() {
    setCatResult(null);
    try {
      const res = await runCategorization(categorizingYear);
      setCatResult(res);
    } catch (e: unknown) {
      setCatResult({ categorized: -1, skipped: 0, errors: 1 });
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-stone-900">Data &amp; Documents</h1>
        <p className="text-stone-500 text-sm mt-0.5">Import data from external sources and manage your document vault</p>
      </div>

      {error && (
        <div className="bg-red-50 text-red-700 rounded-xl p-4 flex items-center gap-3 border border-red-100">
          <AlertCircle size={18} />
          <p className="text-sm flex-1">{error}</p>
          <button onClick={() => setError(null)} className="text-red-400"><XCircle size={14} /></button>
        </div>
      )}

      {/* Tab navigation */}
      <div className="flex gap-1 border-b border-stone-200">
        {([
          { id: "upload", label: "Import", icon: Upload },
          { id: "vault", label: `Document Vault (${documents.length})`, icon: Database },
        ] as { id: "upload" | "vault"; label: string; icon: React.ElementType }[]).map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => setActiveTab(id)}
            className={`flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium whitespace-nowrap border-b-2 transition-colors ${
              activeTab === id
                ? "border-[#16A34A] text-[#16A34A]"
                : "border-transparent text-stone-500 hover:text-stone-700 hover:border-stone-300"
            }`}
          >
            <Icon size={15} />
            {label}
          </button>
        ))}
      </div>

      {/* ── UPLOAD TAB ── */}
      {activeTab === "upload" && (
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Upload Form */}
        <div className="lg:col-span-2 space-y-5">
          {/* Document type selector */}
          <div className="bg-white rounded-xl border border-stone-100 shadow-sm p-5 space-y-4">
            <h2 className="font-semibold text-stone-800">Document Type</h2>
            <div className="grid grid-cols-3 lg:grid-cols-5 gap-3">
              {DOC_TYPE_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  onClick={() => setDocType(opt.value)}
                  className={`text-left p-3 rounded-lg border text-sm transition-colors ${
                    docType === opt.value
                      ? "border-[#16A34A] bg-[#DCFCE7] text-[#16A34A]"
                      : "border-stone-200 hover:border-stone-300 text-stone-600"
                  }`}
                >
                  <p className="font-medium">{opt.label}</p>
                  <p className="text-xs mt-1 opacity-70">{opt.accept.toUpperCase()}</p>
                </button>
              ))}
            </div>
            <p className="text-xs text-stone-400">{selectedDocType.hint}</p>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs text-stone-500 mb-1">Account / Issuer Name</label>
                <input
                  type="text"
                  value={accountName}
                  onChange={(e) => setAccountName(e.target.value)}
                  placeholder="e.g. Chase Sapphire"
                  className="w-full text-sm border border-stone-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20 focus:border-[#16A34A]"
                />
              </div>
              <div>
                <label className="block text-xs text-stone-500 mb-1">Institution</label>
                <input
                  type="text"
                  value={institution}
                  onChange={(e) => setInstitution(e.target.value)}
                  placeholder="e.g. JPMorgan Chase"
                  className="w-full text-sm border border-stone-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20 focus:border-[#16A34A]"
                />
              </div>
            </div>

            {(docType === "credit_card" || docType === "monarch") && (
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs text-stone-500 mb-1">Default Segment</label>
                  <select
                    value={segment}
                    onChange={(e) => setSegment(e.target.value as "personal" | "business")}
                    className="w-full text-sm border border-stone-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20 focus:border-[#16A34A]"
                  >
                    <option value="personal">Personal</option>
                    <option value="business">Business</option>
                  </select>
                </div>
              </div>
            )}

            {(docType === "tax_document" || docType === "investment") && (
              <div>
                <label className="block text-xs text-stone-500 mb-1">Tax Year (optional — auto-detected from file)</label>
                <select
                  value={taxYear ?? ""}
                  onChange={(e) => setTaxYear(e.target.value ? Number(e.target.value) : undefined)}
                  className="text-sm border border-stone-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20 focus:border-[#16A34A]"
                >
                  <option value="">Auto-detect</option>
                  {[currentYear, currentYear - 1, currentYear - 2].map((y) => (
                    <option key={y} value={y}>{y}</option>
                  ))}
                </select>
              </div>
            )}

            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="auto-cat"
                checked={runCategorize}
                onChange={(e) => setRunCategorize(e.target.checked)}
                className="rounded"
              />
              <label htmlFor="auto-cat" className="text-sm text-stone-600">
                Auto-categorize with AI after import (requires Anthropic API key)
              </label>
            </div>
          </div>

          {/* Drop zone */}
          <div
            onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={onDrop}
            onClick={() => fileInputRef.current?.click()}
            className={`rounded-xl border-2 border-dashed p-10 text-center cursor-pointer transition-colors ${
              dragging
                ? "border-[#16A34A]/50 bg-[#DCFCE7]"
                : "border-stone-200 hover:border-stone-300 bg-white"
            }`}
          >
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept={selectedDocType.accept}
              className="hidden"
              onChange={(e) => handleFiles(e.target.files)}
            />
            {uploading ? (
              <div className="flex flex-col items-center gap-3 text-[#16A34A]">
                <Loader2 className="animate-spin" size={32} />
                <p className="text-sm font-medium">Uploading and processing…</p>
              </div>
            ) : (
              <div className="flex flex-col items-center gap-3 text-stone-400">
                <Upload size={32} />
                <div>
                  <p className="text-sm font-medium text-stone-600">Drop files here or click to browse</p>
                  <p className="text-xs mt-1">Accepts: {selectedDocType.accept.toUpperCase()}</p>
                </div>
              </div>
            )}
          </div>

          {/* Import results */}
          {results.length > 0 && (
            <div className="bg-white rounded-xl border border-stone-100 shadow-sm p-5">
              <h2 className="font-semibold text-stone-800 mb-3">Import Log</h2>
              <div className="space-y-3">
                {results.map((r, i) => (
                  <div key={i} className="flex items-start gap-3 text-sm">
                    <span className="mt-0.5">
                      {r.status === "completed" ? (
                        <CheckCircle size={16} className="text-green-500" />
                      ) : r.status === "duplicate" ? (
                        <AlertCircle size={16} className="text-stone-400" />
                      ) : (
                        <XCircle size={16} className="text-red-500" />
                      )}
                    </span>
                    <div className="flex-1">
                      <p className="font-medium text-stone-700 truncate">{r.filename}</p>
                      <p className="text-stone-500 text-xs mt-0.5">{r.message}</p>
                      {r.transactions_imported > 0 && (
                        <p className="text-xs text-green-600 mt-0.5">
                          {r.transactions_imported} imported · {r.transactions_skipped} skipped
                        </p>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Sidebar: manual categorization + recent documents */}
        <div className="space-y-5">
          {/* Manual AI categorization */}
          <div className="bg-white rounded-xl border border-stone-100 shadow-sm p-5">
            <div className="flex items-center gap-2 mb-3">
              <Sparkles size={16} className="text-[#16A34A]" />
              <h2 className="font-semibold text-stone-800 text-sm">Run AI Categorization</h2>
            </div>
            <p className="text-xs text-stone-500 mb-3">
              Re-run Claude categorization on all uncategorized transactions for a given year.
            </p>
            <select
              value={categorizingYear ?? ""}
              onChange={(e) => setCategorizingYear(e.target.value ? Number(e.target.value) : undefined)}
              className="w-full text-sm border border-stone-200 rounded-lg px-3 py-2 mb-3 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20 focus:border-[#16A34A]"
            >
              <option value="">All years</option>
              {[currentYear, currentYear - 1].map((y) => <option key={y} value={y}>{y}</option>)}
            </select>
            <button
              onClick={handleRunCategorization}
              className="w-full bg-[#16A34A] text-white rounded-lg py-2 text-sm font-medium hover:bg-[#15803D] transition-colors"
            >
              Categorize Now
            </button>
            {catResult && (
              <div className="mt-3 text-xs text-stone-600">
                {catResult.categorized >= 0 ? (
                  <p>✓ {catResult.categorized} categorized · {catResult.skipped} skipped · {catResult.errors} errors</p>
                ) : (
                  <p className="text-red-500">Failed — check API logs</p>
                )}
              </div>
            )}
          </div>

          {/* Recent documents */}
          <div className="bg-white rounded-xl border border-stone-100 shadow-sm p-5">
            <div className="flex items-center justify-between mb-3">
              <h2 className="font-semibold text-stone-800 text-sm">Recent Imports</h2>
              <button onClick={loadDocuments} className="p-1 rounded hover:bg-stone-100 text-stone-400">
                <RefreshCw size={13} />
              </button>
            </div>
            {docsLoading ? (
              <div className="flex justify-center py-4">
                <Loader2 size={16} className="animate-spin text-stone-300" />
              </div>
            ) : documents.length === 0 ? (
              <p className="text-xs text-stone-400 text-center py-4">No documents yet.</p>
            ) : (
              <div className="space-y-3">
                {documents.slice(0, 10).map((doc) => (
                  <div key={doc.id} className="flex items-start gap-2 text-xs">
                    <span className="mt-0.5">{STATUS_ICONS[doc.status] ?? <Clock size={14} />}</span>
                    <div className="flex-1 min-w-0">
                      <p className="truncate font-medium text-stone-700">{doc.filename}</p>
                      <p className={`${statusColor(doc.status)} capitalize`}>
                        {doc.status} · {formatDate(doc.imported_at)}
                      </p>
                      {doc.tax_year && <p className="text-stone-400">Tax year {doc.tax_year}</p>}
                    </div>
                  </div>
                ))}
                {documents.length > 10 && (
                  <button onClick={() => setActiveTab("vault")} className="text-xs text-[#16A34A] hover:underline w-full text-center">
                    View all {documents.length} documents →
                  </button>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
      )}

      {/* ── VAULT TAB ── */}
      {activeTab === "vault" && (
        <div className="space-y-4">
          {/* Search + filters */}
          <div className="flex flex-wrap items-center gap-3">
            <div className="relative flex-1 min-w-48">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-stone-400" />
              <input
                type="text"
                value={vaultSearch}
                onChange={(e) => setVaultSearch(e.target.value)}
                placeholder="Search by filename..."
                className="w-full pl-9 pr-3 py-2 text-sm border border-stone-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20"
              />
            </div>
            <select
              value={vaultTypeFilter}
              onChange={(e) => setVaultTypeFilter(e.target.value)}
              className="text-sm border border-stone-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20"
            >
              <option value="">All Types</option>
              {DOC_TYPE_OPTIONS.map((t) => (
                <option key={t.value} value={t.value}>{t.label}</option>
              ))}
            </select>
            <select
              value={vaultStatusFilter}
              onChange={(e) => setVaultStatusFilter(e.target.value)}
              className="text-sm border border-stone-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20"
            >
              <option value="">All Statuses</option>
              <option value="completed">Completed</option>
              <option value="failed">Failed</option>
              <option value="duplicate">Duplicate</option>
              <option value="pending">Pending</option>
            </select>
            <button onClick={loadDocuments} className="p-2 text-stone-400 hover:text-stone-600 border border-stone-200 rounded-lg hover:bg-stone-50">
              <RefreshCw size={14} />
            </button>
            <span className="ml-auto text-xs text-stone-400">{filteredDocs.length} of {documents.length} documents</span>
          </div>

          {docsLoading ? (
            <div className="flex items-center gap-2 text-stone-400 text-sm py-8 justify-center">
              <Loader2 size={16} className="animate-spin" /> Loading documents...
            </div>
          ) : filteredDocs.length === 0 ? (
            <div className="text-center py-12 text-stone-400">
              <FileText size={32} className="mx-auto mb-3 text-stone-300" />
              <p className="text-sm">No documents found.</p>
            </div>
          ) : (
            <div className="bg-white rounded-xl border border-stone-100 overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-stone-50 border-b border-stone-100">
                  <tr>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-stone-500 uppercase tracking-wide">Document</th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-stone-500 uppercase tracking-wide">Type</th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-stone-500 uppercase tracking-wide">Status</th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-stone-500 uppercase tracking-wide">Tax Year</th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-stone-500 uppercase tracking-wide">Imported</th>
                    <th className="px-4 py-3" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-stone-50">
                  {filteredDocs.map((doc) => (
                    <tr key={doc.id} className="hover:bg-stone-50 transition-colors">
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          {STATUS_ICONS[doc.status] ?? <Clock size={14} />}
                          <span className="font-medium text-stone-800 truncate max-w-xs">{doc.filename}</span>
                        </div>
                        {doc.error_message && (
                          <p className="text-xs text-red-500 mt-0.5 ml-5">{doc.error_message}</p>
                        )}
                      </td>
                      <td className="px-4 py-3 text-stone-500 text-xs capitalize">{doc.document_type?.replace(/_/g, " ")}</td>
                      <td className="px-4 py-3">
                        <span className={`text-xs capitalize font-medium ${statusColor(doc.status)}`}>{doc.status}</span>
                      </td>
                      <td className="px-4 py-3 text-stone-500 text-xs">{doc.tax_year || "—"}</td>
                      <td className="px-4 py-3 text-stone-400 text-xs whitespace-nowrap">{formatDate(doc.imported_at)}</td>
                      <td className="px-4 py-3">
                        <button
                          onClick={() => handleDeleteDocument(doc.id)}
                          disabled={deletingId === doc.id}
                          className="p-1.5 text-stone-300 hover:text-red-500 rounded transition-colors disabled:opacity-40"
                          title="Delete document record"
                        >
                          {deletingId === doc.id ? <Loader2 size={13} className="animate-spin" /> : <Trash2 size={13} />}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <p className="text-xs text-stone-400">Deleting a document record removes the import entry only. Transactions already imported are not affected.</p>
        </div>
      )}
    </div>
  );
}
