"use client";
import { useCallback, useEffect, useMemo, useState } from "react";
import { ChevronLeft, ChevronRight, Loader2, AlertCircle } from "lucide-react";
import { getTransactions, updateTransaction, getBusinessEntities, getBudgetCategories } from "@/lib/api";
import type { BusinessEntity, Transaction, TransactionUpdateIn } from "@/types/api";
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

  const allCategories = useMemo(() => {
    const set = new Set([...BASE_CATEGORIES, ...dbCategories]);
    return Array.from(set).sort((a, b) => a.localeCompare(b));
  }, [dbCategories]);

  useEffect(() => {
    getBusinessEntities(true).then(setEntities).catch(() => {});
    getBudgetCategories().then((meta) => setDbCategories(meta.map((m) => m.category))).catch(() => {});
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
  }

  return (
    <div className="space-y-4">
      <PageHeader
        title="Transactions"
        subtitle={`${total.toLocaleString()} transactions`}
        actions={
          <FilterToggleButton
            showFilters={showFilters}
            onToggle={() => setShowFilters(!showFilters)}
            activeFilterCount={activeFilterCount}
          />
        }
      />

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
        <div className="flex items-center justify-center h-48 gap-2 text-stone-400">
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
          <p className="text-stone-400 text-sm">No transactions found. Try adjusting your filters or import a statement.</p>
        </Card>
      ) : (
        <Card padding="none">
          {Array.from(dateGroups.entries()).map(([dateKey, txs]) => (
            <div key={dateKey}>
              <div className="px-4 py-1.5 bg-stone-50/80 border-b border-stone-100 sticky top-0 z-10">
                <span className="text-[11px] font-semibold text-stone-500 uppercase tracking-wide">{formatDateLabel(dateKey)}</span>
              </div>
              <div className="divide-y divide-stone-50">
                {txs.map((tx) => (
                  <TransactionRow
                    key={tx.id}
                    tx={tx}
                    entityMap={entityMap}
                    onSelect={(t) => setDetail({ tx: t })}
                  />
                ))}
              </div>
            </div>
          ))}
        </Card>
      )}

      {totalPages > 1 && (
        <div className="flex items-center justify-between text-sm text-stone-500">
          <span>Page {page + 1} of {totalPages}</span>
          <div className="flex gap-1">
            <button
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              disabled={page === 0}
              aria-label="Previous page"
              className="p-1.5 rounded-lg disabled:opacity-30 hover:bg-stone-100 border border-stone-200"
            >
              <ChevronLeft size={16} />
            </button>
            <button
              onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
              disabled={page >= totalPages - 1}
              aria-label="Next page"
              className="p-1.5 rounded-lg disabled:opacity-30 hover:bg-stone-100 border border-stone-200"
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
