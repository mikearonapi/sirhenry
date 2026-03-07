"use client";
import { Search, Filter } from "lucide-react";
import { monthName } from "@/lib/utils";
import type { BusinessEntity } from "@/types/api";
import Card from "@/components/ui/Card";
import { SEGMENTS } from "./constants";

interface Props {
  search: string;
  onSearchChange: (value: string) => void;
  segment: string;
  onSegmentChange: (value: string) => void;
  categoryFilter: string;
  onCategoryFilterChange: (value: string) => void;
  entityFilter: number | undefined;
  onEntityFilterChange: (value: number | undefined) => void;
  year: number | undefined;
  onYearChange: (value: number | undefined) => void;
  month: number | undefined;
  onMonthChange: (value: number | undefined) => void;
  entities: BusinessEntity[];
  allCategories: string[];
  showFilters: boolean;
  onToggleFilters: () => void;
  activeFilterCount: number;
  onClearAll: () => void;
}

export default function TransactionFilters({
  search, onSearchChange,
  segment, onSegmentChange,
  categoryFilter, onCategoryFilterChange,
  entityFilter, onEntityFilterChange,
  year, onYearChange,
  month, onMonthChange,
  entities, allCategories,
  showFilters, onToggleFilters,
  activeFilterCount, onClearAll,
}: Props) {
  const currentYear = new Date().getFullYear();
  const years = [currentYear, currentYear - 1, currentYear - 2, currentYear - 3];
  const months = Array.from({ length: 12 }, (_, i) => i + 1);

  return (
    <>
      {/* Filter toggle button — rendered in PageHeader via parent */}
      <Card padding="none">
        <div className="px-4 py-2.5 flex items-center gap-3">
          <div className="flex-1 relative">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted" />
            <input
              type="text"
              value={search}
              onChange={(e) => onSearchChange(e.target.value)}
              placeholder="Search transactions..."
              className="w-full pl-9 pr-3 py-1.5 text-sm border border-border rounded-lg focus:outline-none focus:ring-2 focus:ring-accent/20 focus:border-accent"
            />
          </div>
          <select
            value={segment}
            onChange={(e) => onSegmentChange(e.target.value)}
            className="text-sm border border-border rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-accent/20 focus:border-accent bg-card"
          >
            <option value="">All segments</option>
            {SEGMENTS.slice(1).map((s) => (
              <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>
            ))}
          </select>
        </div>

        {showFilters && (
          <div className="px-4 py-2.5 border-t border-card-border flex flex-wrap gap-3">
            <div>
              <label className="block text-xs text-text-secondary mb-1">Category</label>
              <select
                value={categoryFilter}
                onChange={(e) => onCategoryFilterChange(e.target.value)}
                className="text-sm border border-border rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-accent/20 bg-card max-w-[200px]"
              >
                <option value="">All categories</option>
                {allCategories.map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs text-text-secondary mb-1">Entity</label>
              <select
                value={entityFilter ?? ""}
                onChange={(e) => onEntityFilterChange(e.target.value ? Number(e.target.value) : undefined)}
                className="text-sm border border-border rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-accent/20 bg-card"
              >
                <option value="">All entities</option>
                {entities.map((e) => <option key={e.id} value={e.id}>{e.name}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs text-text-secondary mb-1">Year</label>
              <select
                value={year ?? ""}
                onChange={(e) => onYearChange(e.target.value ? Number(e.target.value) : undefined)}
                className="text-sm border border-border rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-accent/20 bg-card"
              >
                <option value="">All years</option>
                {years.map((y) => <option key={y} value={y}>{y}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs text-text-secondary mb-1">Month</label>
              <select
                value={month ?? ""}
                onChange={(e) => onMonthChange(e.target.value ? Number(e.target.value) : undefined)}
                className="text-sm border border-border rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-accent/20 bg-card"
              >
                <option value="">All months</option>
                {months.map((m) => <option key={m} value={m}>{monthName(m)}</option>)}
              </select>
            </div>
            {activeFilterCount > 0 && (
              <div className="flex items-end">
                <button
                  onClick={onClearAll}
                  className="text-xs text-accent hover:underline font-medium py-1.5"
                >
                  Clear all
                </button>
              </div>
            )}
          </div>
        )}
      </Card>
    </>
  );
}

/** Filter toggle button for use in PageHeader actions */
export function FilterToggleButton({
  showFilters, onToggle, activeFilterCount,
}: {
  showFilters: boolean;
  onToggle: () => void;
  activeFilterCount: number;
}) {
  return (
    <button
      onClick={onToggle}
      className={`flex items-center gap-2 text-sm border rounded-lg px-3 py-2 transition-colors ${
        showFilters || activeFilterCount > 0
          ? "border-accent text-accent bg-accent-light"
          : "border-border text-text-secondary hover:bg-surface"
      }`}
    >
      <Filter size={14} />
      Filters
      {activeFilterCount > 0 && (
        <span className="w-5 h-5 rounded-full bg-accent text-white text-xs flex items-center justify-center">
          {activeFilterCount}
        </span>
      )}
    </button>
  );
}
