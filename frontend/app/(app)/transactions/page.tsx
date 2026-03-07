"use client";
import { useCallback, useEffect, useMemo, useState } from "react";
import { ChevronLeft, ChevronRight, Loader2, AlertCircle, Bot, Download, CheckSquare, X } from "lucide-react";
import { getTransactions, updateTransaction, getBusinessEntities, getBudgetCategories, getTransactionAudit, runCategorization, learnCategory } from "@/lib/api";
import type { BusinessEntity, Transaction, TransactionUpdateIn } from "@/types/api";
import type { TransactionAudit } from "@/lib/api-transactions";
import Card from "@/components/ui/Card";
import PageHeader from "@/components/ui/PageHeader";
import { getErrorMessage } from "@/lib/errors";
import { TransactionFilters, FilterToggleButton, TransactionRow, TransactionDetailPanel } from "@/components/transactions";
import { BASE_CATEGORIES, PAGE_SIZE, groupByDate, formatDateLabel } from "@/components/transactions/constants";

interface DetailState {
  tx: Transaction;
}

export default function TransactionsPage() {
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [entities, setEntities] = useState<BusinessEntity[]>([]);
  const [dbCategories, setDbCategories] = useState<string[]>([]);
  const [showFilters, setShowFilters] = useState(false);

  const [segment, setSegment] = useState("");
  const [search, setSearch] = useState("");
  const [year, setYear] = useState<number | undefined>();
  const [month, setMonth] = useState<number | undefined>();
  const [entityFilter, setEntityFilter] = useState<number | undefined>();
  const [categoryFilter, setCategoryFilter] = useState("");

  const [detail, setDetail] = useState<DetailState | null>(null);

  // AI categorization state
  const [categorizing, setCategorizing] = useState(false);
  const [catResult, setCatResult] = useState<{ categorized: number; skipped: number } | null>(null);
  const [audit, setAudit] = useState<TransactionAudit | null>(null);

  // Batch selection state
  const [batchMode, setBatchMode] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());

  // Export state
  const [exporting, setExporting] = useState(false);

  // Category learning state
  const [learnToast, setLearnToast] = useState<{
    merchant: string;
    appliedCount: number;
  } | null>(null);

  const allCategories = useMemo(() => {
    const set = new Set([...BASE_CATEGORIES, ...dbCategories]);
    return Array.from(set).sort((a, b) => a.localeCompare(b));
  }, [dbCategories]);

  useEffect(() => {
    getBusinessEntities(true).then(setEntities).catch(() => {});
    getBudgetCategories().then((meta) => setDbCategories(meta.map((m) => m.category))).catch(() => {});
    getTransactionAudit().then(setAudit).catch(() => {});
  }, []);

  const entityMap = new Map(entities.map((e) => [e.id, e]));

  const load = useCallback(async (signal?: AbortSignal) => {
    setLoading(true);
    setError(null);
    try {
      const result = await getTransactions({
        segment: segment || undefined,
        business_entity_id: entityFilter,
        category: categoryFilter || undefined,
        year, month,
        search: search.trim() || undefined,
        limit: PAGE_SIZE,
        offset: page * PAGE_SIZE,
      });
      if (signal?.aborted) return;
      setTransactions(result.items);
      setTotal(result.total);
    } catch (e: unknown) {
      if (signal?.aborted) return;
      setError(getErrorMessage(e));
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }, [segment, entityFilter, categoryFilter, year, month, page, search]);

  useEffect(() => {
    const controller = new AbortController();
    load(controller.signal);
    return () => controller.abort();
  }, [load]);

  const totalPages = Math.ceil(total / PAGE_SIZE);
  const dateGroups = groupByDate(transactions);
  const activeFilterCount = [segment, year, month, entityFilter, categoryFilter].filter(Boolean).length;

  function resetPage() { setPage(0); }

  async function handleSave(id: number, update: TransactionUpdateIn) {
    const updated = await updateTransaction(id, update);
    setTransactions((prev) => prev.map((t) => (t.id === updated.id ? updated : t)));
    setDetail({ tx: updated });

    // Trigger category learning when user overrides a category
    if (update.category_override) {
      try {
        const result = await learnCategory(
          id,
          update.category_override,
          update.tax_category_override ?? undefined,
          update.segment_override ?? undefined,
          update.business_entity_override ?? undefined,
        );
        if (result.applied_count > 0 && result.rule_id) {
          setLearnToast({ merchant: result.merchant, appliedCount: result.applied_count });
        }
      } catch {
        // Learning is best-effort, don't block the user
      }
    }
  }

  // Auto-dismiss learning toast after 4 seconds
  useEffect(() => {
    if (!learnToast) return;
    const timer = setTimeout(() => {
      setLearnToast(null);
      // Refresh to show newly categorized transactions
      const controller = new AbortController();
      load(controller.signal);
    }, 4000);
    return () => clearTimeout(timer);
  }, [learnToast]); // eslint-disable-line react-hooks/exhaustive-deps

  async function handleCategorize() {
    setCategorizing(true);
    setCatResult(null);
    try {
      const result = await runCategorization(year, month);
      setCatResult(result);
      // Refresh transactions and audit
      const controller = new AbortController();
      await load(controller.signal);
      getTransactionAudit().then(setAudit).catch(() => {});
    } catch (e: unknown) {
      setError(getErrorMessage(e));
    } finally {
      setCategorizing(false);
    }
  }

  function toggleSelect(id: number) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function selectAll() {
    setSelectedIds(new Set(transactions.map((t) => t.id)));
  }

  async function handleBatchUpdate(update: TransactionUpdateIn) {
    const promises = Array.from(selectedIds).map((id) => updateTransaction(id, update));
    await Promise.all(promises);
    setSelectedIds(new Set());
    setBatchMode(false);
    const controller = new AbortController();
    await load(controller.signal);
  }

  async function handleExportCsv() {
    setExporting(true);
    try {
      const result = await getTransactions({
        segment: segment || undefined,
        business_entity_id: entityFilter,
        category: categoryFilter || undefined,
        year, month,
        search: search.trim() || undefined,
        limit: 10000,
        offset: 0,
      });
      const rows = result.items;
      const headers = ["Date", "Description", "Amount", "Category", "Tax Category", "Segment", "Entity", "Notes", "Source"];
      const csvRows = rows.map((tx) => {
        const eid = tx.effective_business_entity_id;
        const eName = eid ? (entityMap.get(eid)?.name ?? "") : "";
        return [
          tx.date,
          `"${(tx.description || "").replace(/"/g, '""')}"`,
          tx.amount.toFixed(2),
          tx.effective_category ?? "",
          tx.effective_tax_category ?? "",
          tx.effective_segment ?? tx.segment,
          eName,
          `"${(tx.notes || "").replace(/"/g, '""')}"`,
          tx.data_source,
        ].join(",");
      });
      const csv = [headers.join(","), ...csvRows].join("\n");
      const blob = new Blob([csv], { type: "text/csv" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `transactions${year ? `-${year}` : ""}${month ? `-${String(month).padStart(2, "0")}` : ""}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e: unknown) {
      setError(getErrorMessage(e));
    } finally {
      setExporting(false);
    }
  }

  const uncategorizedCount = audit?.uncategorized ?? 0;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Transactions"
        subtitle={`${total.toLocaleString()} transactions`}
        actions={
          <div className="flex items-center gap-2">
            {/* AI Categorize button */}
            {uncategorizedCount > 0 && (
              <button
                onClick={handleCategorize}
                disabled={categorizing}
                className="flex items-center gap-1.5 bg-violet-600 text-white px-3 py-1.5 rounded-lg text-xs font-medium hover:bg-violet-700 disabled:opacity-60 shadow-sm"
              >
                {categorizing ? <Loader2 size={12} className="animate-spin" /> : <Bot size={12} />}
                {categorizing ? "Categorizing..." : `Categorize ${uncategorizedCount}`}
              </button>
            )}

            {/* Batch mode toggle */}
            <button
              onClick={() => { setBatchMode(!batchMode); setSelectedIds(new Set()); }}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border shadow-sm transition-colors ${
                batchMode ? "bg-text-primary text-white border-text-primary" : "bg-card text-text-secondary border-border hover:bg-surface"
              }`}
            >
              <CheckSquare size={12} />
              {batchMode ? "Cancel" : "Select"}
            </button>

            {/* Export CSV */}
            <button
              onClick={handleExportCsv}
              disabled={exporting || total === 0}
              className="flex items-center gap-1.5 bg-card text-text-secondary px-3 py-1.5 rounded-lg text-xs font-medium border border-border hover:bg-surface disabled:opacity-40 shadow-sm"
            >
              {exporting ? <Loader2 size={12} className="animate-spin" /> : <Download size={12} />}
              Export
            </button>

            <FilterToggleButton
              showFilters={showFilters}
              onToggle={() => setShowFilters(!showFilters)}
              activeFilterCount={activeFilterCount}
            />
          </div>
        }
      />

      {/* Categorization result banner */}
      {catResult && (
        <div className="bg-green-50 text-green-800 rounded-xl p-3 flex items-center justify-between border border-green-100">
          <div className="flex items-center gap-2 text-sm">
            <Bot size={16} />
            <span>AI categorized <strong>{catResult.categorized}</strong> transactions ({catResult.skipped} already categorized)</span>
          </div>
          <button onClick={() => setCatResult(null)} className="text-green-600 hover:text-green-800">
            <X size={14} />
          </button>
        </div>
      )}

      {/* Category learning toast */}
      {learnToast && (
        <div className="bg-green-50 text-green-800 rounded-xl p-3 flex items-center justify-between border border-green-100">
          <div className="flex items-center gap-2 text-sm">
            <CheckSquare size={16} className="text-green-600" />
            <span>
              Applied rule to <strong>{learnToast.appliedCount}</strong> transaction{learnToast.appliedCount !== 1 ? "s" : ""} from <strong>{learnToast.merchant}</strong>.
            </span>
          </div>
          <button onClick={() => setLearnToast(null)} className="text-green-400 hover:text-green-600">
            <X size={14} />
          </button>
        </div>
      )}

      {/* Batch action bar */}
      {batchMode && selectedIds.size > 0 && (
        <div className="bg-text-primary text-white rounded-xl p-3 flex items-center justify-between">
          <span className="text-sm font-medium">{selectedIds.size} selected</span>
          <div className="flex items-center gap-2">
            <button onClick={selectAll} className="text-xs text-text-muted hover:text-white">Select all on page</button>
            <select
              onChange={(e) => {
                if (e.target.value) handleBatchUpdate({ category_override: e.target.value });
              }}
              defaultValue=""
              className="text-xs bg-text-secondary text-white border border-border rounded-lg px-2 py-1"
            >
              <option value="" disabled>Set category...</option>
              {allCategories.slice(0, 30).map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
            <select
              onChange={(e) => {
                if (e.target.value) handleBatchUpdate({ segment_override: e.target.value });
              }}
              defaultValue=""
              className="text-xs bg-text-secondary text-white border border-border rounded-lg px-2 py-1"
            >
              <option value="" disabled>Set segment...</option>
              <option value="personal">Personal</option>
              <option value="business">Business</option>
              <option value="investment">Investment</option>
              <option value="reimbursable">Reimbursable</option>
            </select>
            <button
              onClick={() => handleBatchUpdate({ is_excluded: true })}
              className="text-xs bg-red-600 text-white px-2 py-1 rounded-lg hover:bg-red-700"
            >
              Exclude
            </button>
          </div>
        </div>
      )}

      {/* Categorization quality indicator */}
      {audit && audit.quality !== "good" && (
        <div className={`rounded-xl p-3 flex items-center gap-2 text-sm border ${
          audit.quality === "poor" ? "bg-red-50 text-red-700 border-red-100" : "bg-amber-50 text-amber-700 border-amber-100"
        }`}>
          <AlertCircle size={14} />
          <span>{audit.categorization_rate}% categorized — {audit.uncategorized} transactions need categorization</span>
          {!categorizing && (
            <button
              onClick={handleCategorize}
              className="ml-auto text-xs font-medium underline hover:no-underline"
            >
              Run AI categorization
            </button>
          )}
        </div>
      )}

      <TransactionFilters
        search={search}
        onSearchChange={(v) => { setSearch(v); resetPage(); }}
        segment={segment}
        onSegmentChange={(v) => { setSegment(v); resetPage(); }}
        categoryFilter={categoryFilter}
        onCategoryFilterChange={(v) => { setCategoryFilter(v); resetPage(); }}
        entityFilter={entityFilter}
        onEntityFilterChange={(v) => { setEntityFilter(v); resetPage(); }}
        year={year}
        onYearChange={(v) => { setYear(v); resetPage(); }}
        month={month}
        onMonthChange={(v) => { setMonth(v); resetPage(); }}
        entities={entities}
        allCategories={allCategories}
        showFilters={showFilters}
        onToggleFilters={() => setShowFilters(!showFilters)}
        activeFilterCount={activeFilterCount}
        onClearAll={() => {
          setSegment(""); setYear(undefined); setMonth(undefined);
          setEntityFilter(undefined); setCategoryFilter(""); resetPage();
        }}
      />

      {loading ? (
        <div className="flex items-center justify-center h-48 gap-2 text-text-muted">
          <Loader2 className="animate-spin" size={18} />
          <span className="text-sm">Loading...</span>
        </div>
      ) : error ? (
        <div className="flex items-center gap-2 text-red-600 bg-red-50 rounded-xl p-4 border border-red-100">
          <AlertCircle size={18} />
          <span className="text-sm">{error}</span>
        </div>
      ) : transactions.length === 0 ? (
        <Card className="text-center py-12">
          <p className="text-text-muted text-sm">No transactions found. Try adjusting your filters or import a statement.</p>
        </Card>
      ) : (
        <Card padding="none">
          {Array.from(dateGroups.entries()).map(([dateKey, txs]) => (
            <div key={dateKey}>
              <div className="px-4 py-1.5 bg-surface/80 border-b border-card-border sticky top-0 z-10">
                <span className="text-xs font-semibold text-text-secondary uppercase tracking-wide">{formatDateLabel(dateKey)}</span>
              </div>
              <div className="divide-y divide-border-light">
                {txs.map((tx) => (
                  <TransactionRow
                    key={tx.id}
                    tx={tx}
                    entityMap={entityMap}
                    onSelect={(t) => setDetail({ tx: t })}
                    selected={batchMode ? selectedIds.has(tx.id) : undefined}
                    onToggleSelect={batchMode ? toggleSelect : undefined}
                  />
                ))}
              </div>
            </div>
          ))}
        </Card>
      )}

      {totalPages > 1 && (
        <div className="flex items-center justify-between text-sm text-text-secondary">
          <span>Page {page + 1} of {totalPages}</span>
          <div className="flex gap-1">
            <button
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              disabled={page === 0}
              aria-label="Previous page"
              className="p-1.5 rounded-lg disabled:opacity-30 hover:bg-surface border border-border"
            >
              <ChevronLeft size={16} />
            </button>
            <button
              onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
              disabled={page >= totalPages - 1}
              aria-label="Next page"
              className="p-1.5 rounded-lg disabled:opacity-30 hover:bg-surface border border-border"
            >
              <ChevronRight size={16} />
            </button>
          </div>
        </div>
      )}

      {detail && (
        <TransactionDetailPanel
          tx={detail.tx}
          entities={entities}
          entityMap={entityMap}
          allCategories={allCategories}
          onClose={() => setDetail(null)}
          onSave={handleSave}
        />
      )}
    </div>
  );
}
