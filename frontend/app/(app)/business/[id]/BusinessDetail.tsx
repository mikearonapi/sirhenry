"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  Building2, ArrowLeft, Pencil, Loader2, AlertCircle,
  FileText, Zap, Tag, BarChart3, TrendingUp, TrendingDown,
  Minus, ChevronRight, MessageCircle, X, ExternalLink,
  ShieldCheck, Calendar, Hash, Briefcase,
} from "lucide-react";
import Card from "@/components/ui/Card";
import PageHeader from "@/components/ui/PageHeader";
import {
  getBusinessEntity, getVendorRules, getEntityExpenseReport,
} from "@/lib/api";
import { formatCurrency, monthName } from "@/lib/utils";
import { getErrorMessage } from "@/lib/errors";
import type {
  BusinessEntity, VendorEntityRule, EntityExpenseReport,
} from "@/types/api";

// ---------------------------------------------------------------------------
// Config (mirrors business/page.tsx for consistency)
// ---------------------------------------------------------------------------

const ENTITY_TYPES: Record<string, string> = {
  sole_prop: "Sole Proprietorship",
  llc: "LLC",
  s_corp: "S-Corporation",
  c_corp: "C-Corporation",
  partnership: "Partnership",
  other: "Other",
};

const TAX_TREATMENTS: Record<string, string> = {
  schedule_c: "Schedule C (Sole Prop / Single-Member LLC)",
  s_corp: "S-Corp (Form 1120-S)",
  partnership: "Partnership (Form 1065)",
  c_corp: "C-Corp (Form 1120)",
  "1099_nec": "1099-NEC / Board Income",
  other: "Other",
};

const TAX_CONNECTIONS: Record<string, { effect: string; connects: string; href: string }> = {
  schedule_c: {
    effect: "Business income / loss flows to Schedule C on your personal return.",
    connects: "Transactions tagged to this entity appear in your Schedule C expense summary.",
    href: "/tax-strategy",
  },
  s_corp: {
    effect: "Pay yourself a reasonable salary + distributions. QBI deduction may apply.",
    connects: "S-Corp payroll shows on W-2. Distributions tracked separately.",
    href: "/tax-strategy",
  },
  partnership: {
    effect: "Each partner's share passes through on Schedule K-1.",
    connects: "Import K-1 data via Documents to populate your tax summary.",
    href: "/import",
  },
  c_corp: {
    effect: "Corporate-level tax at 21% flat rate. Dividends taxed again at distribution.",
    connects: "Dividends received appear as 1099-DIV income in your tax summary.",
    href: "/tax-strategy",
  },
  "1099_nec": {
    effect: "Board / director / contractor income. Self-employment tax applies.",
    connects: "1099-NEC income feeds into your self-employment tax estimate.",
    href: "/tax-strategy",
  },
  other: {
    effect: "Review tax obligations with your CPA.",
    connects: "Tag transactions to this entity to track income and expenses.",
    href: "/transactions",
  },
};

const now = new Date();

// ---------------------------------------------------------------------------
// Completeness steps
// ---------------------------------------------------------------------------

function getCompletenessSteps(entity: BusinessEntity) {
  return [
    { label: "Description", done: !!entity.description, action: "Add a description" },
    { label: "Tax Setup", done: !!(entity.tax_treatment && entity.tax_treatment !== "other"), action: "Set tax treatment" },
    { label: "EIN", done: !!entity.ein, action: "Add EIN (when ready)" },
    { label: "Expense Types", done: !!entity.expected_expenses, action: "Define expected expenses" },
  ];
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function BusinessDetailPage() {
  const params = useParams();
  const router = useRouter();
  const entityId = Number(params.id);

  const [entity, setEntity] = useState<BusinessEntity | null>(null);
  const [rules, setRules] = useState<VendorEntityRule[]>([]);
  const [report, setReport] = useState<EntityExpenseReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [year] = useState(now.getFullYear());

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [ent, vendorRules] = await Promise.all([
        getBusinessEntity(entityId),
        getVendorRules(entityId),
      ]);
      setEntity(ent);
      setRules(vendorRules);

      // Load expense report separately — don't fail the whole page if no expenses
      try {
        const expReport = await getEntityExpenseReport(entityId, year);
        setReport(expReport);
      } catch {
        // No expenses yet — that's fine
        setReport(null);
      }
    } catch (e: unknown) {
      setError(getErrorMessage(e));
    } finally {
      setLoading(false);
    }
  }, [entityId, year]);

  useEffect(() => { load(); }, [load]);

  // Derived data
  const typeLabel = entity ? (ENTITY_TYPES[entity.entity_type] || entity.entity_type) : "";
  const taxLabel = entity ? (TAX_TREATMENTS[entity.tax_treatment] || entity.tax_treatment) : "";
  const connection = entity ? (TAX_CONNECTIONS[entity.tax_treatment] || TAX_CONNECTIONS.other) : null;
  const completeness = entity ? getCompletenessSteps(entity) : [];
  const completePct = completeness.length > 0
    ? Math.round((completeness.filter((s) => s.done).length / completeness.length) * 100)
    : 0;

  // Expense summary
  const ytdTotal = report?.year_total_expenses ?? 0;
  const txCount = report?.monthly_totals?.reduce((s, m) => s + m.transaction_count, 0) ?? 0;
  const yoyChange = report?.year_over_year_change_pct ?? null;
  const topCategories = useMemo(() => {
    if (!report) return [];
    return report.category_breakdown
      .filter((c) => c.total !== 0)
      .sort((a, b) => Math.abs(b.total) - Math.abs(a.total))
      .slice(0, 5);
  }, [report]);

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-text-secondary text-sm py-16 justify-center">
        <Loader2 size={16} className="animate-spin" /> Loading business details...
      </div>
    );
  }

  if (error || !entity) {
    return (
      <div className="space-y-6">
        <PageHeader title="Business Not Found" />
        <div className="bg-red-50 text-red-700 rounded-xl p-4 flex items-center gap-3 border border-red-100">
          <AlertCircle size={18} />
          <p className="text-sm flex-1">{error || "This business entity could not be found."}</p>
        </div>
        <Link
          href="/business"
          className="inline-flex items-center gap-1.5 text-sm text-accent hover:underline"
        >
          <ArrowLeft size={14} /> Back to My Businesses
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <PageHeader
        title={entity.name}
        subtitle={`${typeLabel}${entity.is_active ? "" : " (Inactive)"}`}
        actions={
          <div className="flex items-center gap-2">
            <Link
              href="/business"
              className="flex items-center gap-1.5 text-sm text-text-secondary hover:text-text-secondary border border-border rounded-lg px-3 py-2"
            >
              <ArrowLeft size={14} /> Back
            </Link>
            <Link
              href={`/business?edit=${entity.id}`}
              className="flex items-center gap-1.5 text-sm text-text-secondary border border-border rounded-lg px-3 py-2 hover:bg-surface"
            >
              <Pencil size={14} /> Edit
            </Link>
          </div>
        }
      />

      {/* Completeness tracker — only when not 100% */}
      {completePct < 100 && (
        <div className="bg-card border border-card-border rounded-xl p-4 shadow-sm">
          <div className="flex items-center justify-between mb-3">
            <div>
              <p className="text-sm font-semibold text-text-primary">Setup Progress</p>
              <p className="text-xs text-text-secondary">
                {completeness.filter((s) => s.done).length} of {completeness.length} steps complete
              </p>
            </div>
            <span className={`text-xs font-bold px-2.5 py-1 rounded-full ${
              completePct >= 75 ? "bg-green-50 text-green-700" :
              completePct >= 50 ? "bg-amber-50 text-amber-700" :
              "bg-surface text-text-secondary"
            }`}>
              {completePct}%
            </span>
          </div>
          <div className="w-full bg-surface rounded-full h-1.5 mb-3">
            <div className="bg-accent h-1.5 rounded-full transition-all" style={{ width: `${completePct}%` }} />
          </div>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-2">
            {completeness.map((s) => (
              <div key={s.label} className={`flex items-center gap-2 p-2 rounded-lg text-xs ${s.done ? "bg-green-50" : "bg-surface"}`}>
                <div className={`w-4 h-4 rounded-full flex items-center justify-center shrink-0 text-white text-[9px] font-bold ${s.done ? "bg-green-500" : "bg-border"}`}>
                  {s.done ? "\u2713" : "!"}
                </div>
                <div>
                  <p className={`font-medium ${s.done ? "text-green-700" : "text-text-secondary"}`}>{s.label}</p>
                  <p className={`text-xs ${s.done ? "text-green-600" : "text-text-muted"}`}>
                    {s.done ? "Complete" : s.action}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Main content — 2-column layout */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left column — Business info */}
        <div className="lg:col-span-2 space-y-4">
          {/* Business Overview */}
          <Card padding="md">
            <h3 className="text-sm font-semibold text-text-primary mb-4 flex items-center gap-2">
              <Building2 size={16} className="text-text-muted" />
              Business Overview
            </h3>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <p className="text-xs uppercase tracking-wider text-text-muted mb-1">Entity Type</p>
                <p className="text-sm text-text-primary font-medium">{typeLabel}</p>
              </div>
              <div>
                <p className="text-xs uppercase tracking-wider text-text-muted mb-1">Tax Treatment</p>
                <p className="text-sm text-text-primary font-medium">{taxLabel}</p>
              </div>
              <div>
                <p className="text-xs uppercase tracking-wider text-text-muted mb-1">EIN</p>
                {entity.ein ? (
                  <p className="text-sm text-text-primary font-mono">{entity.ein}</p>
                ) : (
                  <p className="text-sm text-text-muted italic">Not yet assigned</p>
                )}
              </div>
              <div>
                <p className="text-xs uppercase tracking-wider text-text-muted mb-1">Status</p>
                <div className="flex items-center gap-2">
                  <span className={`inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full ${
                    entity.is_active ? "bg-green-50 text-green-700" : "bg-surface text-text-secondary"
                  }`}>
                    <span className={`w-1.5 h-1.5 rounded-full ${entity.is_active ? "bg-green-500" : "bg-border"}`} />
                    {entity.is_active ? "Active" : "Inactive"}
                  </span>
                  {entity.is_provisional && (
                    <span className="text-xs bg-amber-50 text-amber-600 px-2 py-0.5 rounded-full">Provisional</span>
                  )}
                </div>
              </div>
            </div>

            {/* Active dates */}
            {(entity.active_from || entity.active_to) && (
              <div className="mt-4 pt-4 border-t border-card-border flex items-center gap-2 text-xs text-text-secondary">
                <Calendar size={12} className="shrink-0" />
                <span>
                  {entity.active_from ? new Date(entity.active_from).toLocaleDateString("en-US", { month: "long", year: "numeric" }) : "Start unknown"}
                  {" \u2192 "}
                  {entity.active_to ? new Date(entity.active_to).toLocaleDateString("en-US", { month: "long", year: "numeric" }) : "Present"}
                </span>
              </div>
            )}

            {/* Description */}
            {entity.description && (
              <div className="mt-4 pt-4 border-t border-card-border">
                <p className="text-xs uppercase tracking-wider text-text-muted mb-1">Description</p>
                <p className="text-sm text-text-secondary leading-relaxed">{entity.description}</p>
              </div>
            )}

            {/* Expected Expenses */}
            {entity.expected_expenses && (
              <div className="mt-4 pt-4 border-t border-card-border">
                <p className="text-xs uppercase tracking-wider text-text-muted mb-2">Expected Expense Types</p>
                <div className="flex flex-wrap gap-1.5">
                  {entity.expected_expenses.split(",").map((expense, i) => (
                    <span key={i} className="text-xs bg-surface text-text-secondary px-2 py-0.5 rounded-md">
                      {expense.trim()}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Notes */}
            {entity.notes && (
              <div className="mt-4 pt-4 border-t border-card-border">
                <p className="text-xs uppercase tracking-wider text-text-muted mb-1">Notes</p>
                <p className="text-sm text-text-secondary italic">{entity.notes}</p>
              </div>
            )}
          </Card>

          {/* Tax Connection */}
          {connection && (
            <Card padding="md">
              <h3 className="text-sm font-semibold text-text-primary mb-3 flex items-center gap-2">
                <Zap size={16} className="text-amber-500" />
                Tax Connection
              </h3>
              <div className="bg-blue-50 border border-blue-100 rounded-lg p-3">
                <p className="text-xs text-blue-800 font-medium">{connection.effect}</p>
                <p className="text-xs text-blue-600 mt-1">{connection.connects}</p>
              </div>
              <div className="flex items-center gap-4 mt-3">
                <Link
                  href={connection.href}
                  className="inline-flex items-center gap-1 text-xs font-medium text-accent hover:underline"
                >
                  <TrendingUp size={11} /> View Tax Strategy <ChevronRight size={11} />
                </Link>
                <Link
                  href="/transactions"
                  className="inline-flex items-center gap-1 text-xs font-medium text-accent hover:underline"
                >
                  <Tag size={11} /> Filter Transactions <ChevronRight size={11} />
                </Link>
              </div>
            </Card>
          )}

          {/* Vendor Rules */}
          <Card padding="md">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold text-text-primary flex items-center gap-2">
                <ShieldCheck size={16} className="text-text-muted" />
                Auto-Tag Rules
              </h3>
              <span className="text-xs text-text-muted">{rules.length} rule{rules.length !== 1 ? "s" : ""}</span>
            </div>
            <p className="text-xs text-text-secondary mb-3">
              Vendor rules automatically assign transactions to this business based on the merchant name.
            </p>
            {rules.length > 0 ? (
              <div className="space-y-2">
                {rules.map((rule) => (
                  <div key={rule.id} className="flex items-center gap-3 p-2.5 bg-surface rounded-lg">
                    <Hash size={12} className="text-text-muted shrink-0" />
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-medium text-text-secondary font-mono">{rule.vendor_pattern}</p>
                      {rule.segment_override && (
                        <p className="text-xs text-text-muted">Segment: {rule.segment_override}</p>
                      )}
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <span className="text-xs text-text-muted">Priority: {rule.priority}</span>
                      <span className={`w-1.5 h-1.5 rounded-full ${rule.is_active ? "bg-green-500" : "bg-border"}`} />
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="bg-surface rounded-lg p-4 text-center">
                <p className="text-xs text-text-muted">No auto-tag rules configured yet.</p>
                <button
                  onClick={() => window.dispatchEvent(new CustomEvent("ask-henry", { detail: { message: `How do I set up vendor rules to automatically tag transactions for ${entity.name}?` } }))}
                  className="inline-flex items-center gap-1 text-xs text-accent hover:underline mt-2"
                >
                  <MessageCircle size={10} /> Ask Henry how to set up rules
                </button>
              </div>
            )}
          </Card>
        </div>

        {/* Right column — Expense summary + quick actions */}
        <div className="space-y-4">
          {/* YTD Expense Summary */}
          <Card padding="md">
            <h3 className="text-sm font-semibold text-text-primary mb-3 flex items-center gap-2">
              <BarChart3 size={16} className="text-text-muted" />
              {year} Expenses
            </h3>
            {report ? (
              <>
                <div className="text-center py-2">
                  <p className="text-2xl font-bold font-mono text-text-primary">
                    {formatCurrency(Math.abs(ytdTotal))}
                  </p>
                  <p className="text-xs text-text-secondary mt-1">
                    {txCount} transaction{txCount !== 1 ? "s" : ""} this year
                  </p>
                  {yoyChange !== null && (
                    <div className="flex items-center justify-center gap-1 mt-2">
                      {yoyChange > 0 ? (
                        <TrendingUp size={12} className="text-red-500" />
                      ) : yoyChange < 0 ? (
                        <TrendingDown size={12} className="text-green-600" />
                      ) : (
                        <Minus size={12} className="text-text-muted" />
                      )}
                      <span className={`text-xs font-medium ${
                        yoyChange > 0 ? "text-red-600" : yoyChange < 0 ? "text-green-600" : "text-text-secondary"
                      }`}>
                        {yoyChange > 0 ? "+" : ""}{yoyChange.toFixed(1)}% vs {year - 1}
                      </span>
                    </div>
                  )}
                </div>

                {/* Top categories */}
                {topCategories.length > 0 && (
                  <div className="mt-3 pt-3 border-t border-card-border">
                    <p className="text-xs uppercase tracking-wider text-text-muted mb-2">Top Categories</p>
                    <div className="space-y-1.5">
                      {topCategories.map((cat) => (
                        <div key={cat.category} className="flex items-center justify-between text-xs">
                          <span className="text-text-secondary truncate flex-1">{cat.category}</span>
                          <span className="font-mono text-text-primary ml-2">{formatCurrency(Math.abs(cat.total))}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                <Link
                  href={`/business/${entity.id}/expenses`}
                  className="flex items-center justify-center gap-1.5 mt-4 text-xs font-medium text-accent hover:text-accent-hover bg-green-50 rounded-lg py-2 transition-colors"
                >
                  <BarChart3 size={12} /> Full Expense Report <ChevronRight size={12} />
                </Link>
              </>
            ) : (
              <div className="text-center py-4">
                <p className="text-xs text-text-muted">No expense data for {year}.</p>
                <p className="text-xs text-text-muted mt-1">
                  Tag transactions to this entity or set up vendor rules to auto-tag.
                </p>
                <Link
                  href={`/business/${entity.id}/expenses`}
                  className="inline-flex items-center gap-1 text-xs text-accent hover:underline mt-3"
                >
                  <BarChart3 size={12} /> View Expense Report
                </Link>
              </div>
            )}
          </Card>

          {/* Quick Actions */}
          <Card padding="md">
            <h3 className="text-sm font-semibold text-text-primary mb-3">Quick Actions</h3>
            <div className="space-y-1">
              <Link
                href={`/transactions?entity=${entity.id}`}
                className="flex items-center gap-2.5 p-2.5 rounded-lg text-xs text-text-secondary hover:bg-surface hover:text-text-primary transition-colors"
              >
                <Tag size={14} className="text-text-muted shrink-0" />
                <span className="flex-1">View Tagged Transactions</span>
                <ChevronRight size={12} className="text-text-muted" />
              </Link>
              <Link
                href="/tax-strategy"
                className="flex items-center gap-2.5 p-2.5 rounded-lg text-xs text-text-secondary hover:bg-surface hover:text-text-primary transition-colors"
              >
                <Zap size={14} className="text-text-muted shrink-0" />
                <span className="flex-1">Tax Strategy</span>
                <ChevronRight size={12} className="text-text-muted" />
              </Link>
              <Link
                href="/reports"
                className="flex items-center gap-2.5 p-2.5 rounded-lg text-xs text-text-secondary hover:bg-surface hover:text-text-primary transition-colors"
              >
                <FileText size={14} className="text-text-muted shrink-0" />
                <span className="flex-1">Generate Report</span>
                <ChevronRight size={12} className="text-text-muted" />
              </Link>
              <button
                onClick={() => window.dispatchEvent(new CustomEvent("ask-henry", { detail: { message: `Tell me about the tax implications and deductions available for my ${typeLabel} business "${entity.name}".` } }))}
                className="w-full flex items-center gap-2.5 p-2.5 rounded-lg text-xs text-text-secondary hover:bg-surface hover:text-text-primary transition-colors"
              >
                <MessageCircle size={14} className="text-text-muted shrink-0" />
                <span className="flex-1 text-left">Ask Henry about Deductions</span>
                <ChevronRight size={12} className="text-text-muted" />
              </button>
            </div>
          </Card>

          {/* EIN guidance (if missing) */}
          {!entity.ein && (
            <div className="bg-blue-50/50 border border-blue-100 rounded-xl p-4">
              <p className="text-sm font-semibold text-text-primary">Need an EIN?</p>
              <p className="text-xs text-text-secondary mt-1">
                An EIN is free from the IRS. You&apos;ll need one to open a business bank account, hire employees, or file certain tax returns.
              </p>
              <div className="flex items-center gap-3 mt-2">
                <a
                  href="https://www.irs.gov/businesses/small-businesses-self-employed/apply-for-an-employer-identification-number-ein-online"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-xs font-medium text-accent hover:underline"
                >
                  Apply at IRS.gov <ExternalLink size={10} />
                </a>
                <button
                  onClick={() => window.dispatchEvent(new CustomEvent("ask-henry", { detail: { message: "Do I need an EIN for my side business? What are the requirements and when should I get one?" } }))}
                  className="inline-flex items-center gap-1 text-xs text-accent/70 hover:text-accent"
                >
                  <MessageCircle size={10} /> Ask Henry
                </button>
              </div>
            </div>
          )}

          {/* Created date */}
          <p className="text-xs text-text-muted text-center">
            Created {new Date(entity.created_at).toLocaleDateString("en-US", { month: "long", day: "numeric", year: "numeric" })}
          </p>
        </div>
      </div>
    </div>
  );
}
