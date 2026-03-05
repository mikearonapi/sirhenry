"use client";
import { Suspense, useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import {
  Building2, Plus, Pencil, Trash2, AlertCircle, Loader2, X,
  Zap, FileText, Tag, ChevronRight,
  Laptop, Rocket, Award, MessageCircle,
  Home as HomeIcon,
} from "lucide-react";
import Card from "@/components/ui/Card";
import PageHeader from "@/components/ui/PageHeader";
import EmptyState from "@/components/ui/EmptyState";
import {
  getBusinessEntities, createBusinessEntity, updateBusinessEntity, deleteBusinessEntity,
} from "@/lib/api";
import type { BusinessEntity, BusinessEntityCreateIn } from "@/types/api";

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------

const ENTITY_TYPES = [
  { value: "sole_prop", label: "Sole Proprietorship" },
  { value: "llc", label: "LLC" },
  { value: "s_corp", label: "S-Corporation" },
  { value: "c_corp", label: "C-Corporation" },
  { value: "partnership", label: "Partnership" },
  { value: "other", label: "Other" },
];

const TAX_TREATMENTS = [
  { value: "schedule_c", label: "Schedule C (Sole Prop / Single-Member LLC)" },
  { value: "s_corp", label: "S-Corp (Form 1120-S)" },
  { value: "partnership", label: "Partnership (Form 1065)" },
  { value: "c_corp", label: "C-Corp (Form 1120)" },
  { value: "1099_nec", label: "1099-NEC / Board Income" },
  { value: "other", label: "Other" },
];

// What each tax treatment means for the user's broader finances
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
    effect: "Corporate-level tax at 21% flat rate. Dividends are taxed again at distribution.",
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

// ---------------------------------------------------------------------------
// Quick-start templates for the empty state
// ---------------------------------------------------------------------------

const BUSINESS_TEMPLATES = [
  {
    key: "freelance",
    name: "Freelance / Consulting",
    entityType: "sole_prop",
    taxTreatment: "schedule_c",
    description: "Side consulting, freelance projects, or 1099 contract work",
    icon: Laptop,
  },
  {
    key: "startup",
    name: "Side Startup",
    entityType: "llc",
    taxTreatment: "schedule_c",
    description: "Building a product or service alongside your day job",
    icon: Rocket,
  },
  {
    key: "rental",
    name: "Rental Property",
    entityType: "llc",
    taxTreatment: "schedule_c",
    description: "Income from residential or commercial rental properties",
    icon: HomeIcon,
  },
  {
    key: "advisory",
    name: "Board / Advisory Roles",
    entityType: "sole_prop",
    taxTreatment: "1099_nec",
    description: "Paid board seats, advisory roles, or speaking engagements",
    icon: Award,
  },
];

// ---------------------------------------------------------------------------
// Dismissible guidance cards
// ---------------------------------------------------------------------------

const GUIDANCE_KEY = "business.dismissed_guidance";

function getDismissedCards(): Set<string> {
  try {
    const raw = typeof window !== "undefined" ? localStorage.getItem(GUIDANCE_KEY) : null;
    return raw ? new Set(JSON.parse(raw) as string[]) : new Set();
  } catch { return new Set(); }
}

function persistDismiss(key: string) {
  const current = getDismissedCards();
  current.add(key);
  localStorage.setItem(GUIDANCE_KEY, JSON.stringify([...current]));
}

interface GuidanceCard {
  key: string;
  title: string;
  description: string;
  linkLabel?: string;
  linkHref?: string;
  askHenry?: string;
  show: (entities: BusinessEntity[]) => boolean;
}

const GUIDANCE_CARDS: GuidanceCard[] = [
  {
    key: "ein",
    title: "Get an EIN",
    description: "Free from IRS.gov. You'll need one if you have employees, file certain tax returns, or want a business bank account.",
    linkLabel: "Apply at IRS.gov →",
    linkHref: "https://www.irs.gov/businesses/small-businesses-self-employed/apply-for-an-employer-identification-number-ein-online",
    show: (entities) => entities.some((e) => !e.ein),
  },
  {
    key: "bank_account",
    title: "Open a Business Account",
    description: "Separating business and personal spending makes tax time easier and protects your liability shield.",
    askHenry: "What should I look for in a business bank account? Do I need one for a sole proprietorship?",
    show: () => true,
  },
  {
    key: "credit_card",
    title: "Use a Dedicated Card",
    description: "A card used only for business purchases simplifies expense tracking and creates a clean audit trail.",
    askHenry: "What should I look for in a business credit card? What rewards or features matter most for a side business?",
    show: () => true,
  },
];

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function BusinessPage() {
  return (
    <Suspense>
      <BusinessPageContent />
    </Suspense>
  );
}

function BusinessPageContent() {
  const searchParams = useSearchParams();
  const [entities, setEntities] = useState<BusinessEntity[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showInactive, setShowInactive] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [editingEntity, setEditingEntity] = useState<BusinessEntity | null>(null);
  const [saving, setSaving] = useState(false);

  // Form state
  const [fName, setFName] = useState("");
  const [fEntityType, setFEntityType] = useState("sole_prop");
  const [fTaxTreatment, setFTaxTreatment] = useState("schedule_c");
  const [fEin, setFEin] = useState("");
  const [fActiveFrom, setFActiveFrom] = useState("");
  const [fActiveTo, setFActiveTo] = useState("");
  const [fNotes, setFNotes] = useState("");
  const [fDescription, setFDescription] = useState("");
  const [fExpectedExpenses, setFExpectedExpenses] = useState("");
  const [dismissedCards, setDismissedCards] = useState<Set<string>>(new Set());

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getBusinessEntities(showInactive);
      setEntities(Array.isArray(data) ? data : []);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [showInactive]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { setDismissedCards(getDismissedCards()); }, []);

  // Auto-open edit form when arriving via ?edit=ID (from detail page Edit button)
  useEffect(() => {
    const editId = searchParams.get("edit");
    if (editId && entities.length > 0 && !editingEntity) {
      const target = entities.find((e) => e.id === Number(editId));
      if (target) openEdit(target);
    }
  }, [searchParams, entities]); // eslint-disable-line react-hooks/exhaustive-deps

  function resetForm() {
    setFName(""); setFEntityType("sole_prop"); setFTaxTreatment("schedule_c");
    setFEin(""); setFActiveFrom(""); setFActiveTo(""); setFNotes("");
    setFDescription(""); setFExpectedExpenses("");
    setEditingEntity(null);
    setShowForm(false);
  }

  function openEdit(entity: BusinessEntity) {
    setEditingEntity(entity);
    setFName(entity.name);
    setFEntityType(entity.entity_type || "sole_prop");
    setFTaxTreatment(entity.tax_treatment || "schedule_c");
    setFEin(entity.ein || "");
    setFActiveFrom(entity.active_from || "");
    setFActiveTo(entity.active_to || "");
    setFNotes(entity.notes || "");
    setFDescription(entity.description || "");
    setFExpectedExpenses(entity.expected_expenses || "");
    setShowForm(true);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  async function handleSave() {
    if (!fName.trim()) return;
    setSaving(true);
    setError(null);
    try {
      const body: BusinessEntityCreateIn = {
        name: fName.trim(),
        entity_type: fEntityType,
        tax_treatment: fTaxTreatment,
        ein: fEin || null,
        active_from: fActiveFrom || null,
        active_to: fActiveTo || null,
        notes: fNotes || null,
        description: fDescription || null,
        expected_expenses: fExpectedExpenses || null,
      };
      if (editingEntity) {
        await updateBusinessEntity(editingEntity.id, body);
      } else {
        await createBusinessEntity(body);
      }
      await load();
      resetForm();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(id: number) {
    if (!confirm("Delete this business entity? Transactions tagged to it will be untagged.")) return;
    try {
      await deleteBusinessEntity(id);
      await load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  function handleTemplateSelect(template: typeof BUSINESS_TEMPLATES[number]) {
    setFName(template.name);
    setFEntityType(template.entityType);
    setFTaxTreatment(template.taxTreatment);
    setFDescription(template.description);
    setShowForm(true);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function handleDismissCard(key: string) {
    persistDismiss(key);
    setDismissedCards((prev) => new Set([...prev, key]));
  }

  function getCompletenessSteps(entity: BusinessEntity) {
    return [
      { label: "Description", done: !!entity.description, action: "Add a description" },
      { label: "Tax Setup", done: !!(entity.tax_treatment && entity.tax_treatment !== "other"), action: "Set tax treatment" },
      { label: "EIN", done: !!entity.ein, action: "Add EIN (when ready)" },
      { label: "Expense Types", done: !!entity.expected_expenses, action: "Define expected expenses" },
    ];
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="My Businesses"
        subtitle="Track side ventures, manage expenses, and connect to your tax strategy"
        actions={
          <button
            onClick={() => { if (showForm) resetForm(); else setShowForm(true); }}
            className="flex items-center gap-2 bg-[#16A34A] text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-[#15803D] shadow-sm"
          >
            {showForm ? <X size={14} /> : <Plus size={14} />}
            {showForm ? "Cancel" : "Add Business"}
          </button>
        }
      />

      {error && (
        <div className="bg-red-50 text-red-700 rounded-xl p-4 flex items-center gap-3 border border-red-100">
          <AlertCircle size={18} />
          <p className="text-sm flex-1">{error}</p>
          <button onClick={() => setError(null)} className="text-red-400"><X size={14} /></button>
        </div>
      )}

      {/* How this section connects to the rest of the app */}
      <div className="bg-stone-50 border border-stone-100 rounded-xl px-4 py-3">
        <p className="text-xs font-semibold text-stone-700">Why this matters</p>
        <p className="text-xs text-stone-500 mt-0.5">
          Business entities connect your financial data across the app.
          Transactions tagged to a business entity appear in Tax Strategy (Schedule C / QBI), in Reports (annual business expense detail), and can be filtered in Transactions.
        </p>
        <div className="flex gap-4 mt-2">
          <a href="/tax-strategy" className="text-xs font-medium text-[#16A34A] hover:underline flex items-center gap-1"><Zap size={11} /> Tax Strategy</a>
          <a href="/transactions" className="text-xs font-medium text-[#16A34A] hover:underline flex items-center gap-1"><Tag size={11} /> Transactions</a>
          <a href="/reports" className="text-xs font-medium text-[#16A34A] hover:underline flex items-center gap-1"><FileText size={11} /> Reports</a>
        </div>
      </div>

      {/* Business setup completeness tracker */}
      {entities.length > 0 && (() => {
        const steps = getCompletenessSteps(entities[0]);
        const complete = steps.filter((s) => s.done).length;
        const pct = Math.round((complete / steps.length) * 100);
        if (pct === 100) return null;
        return (
          <div className="bg-white border border-stone-100 rounded-xl p-4 shadow-sm">
            <div className="flex items-center justify-between mb-3">
              <div>
                <p className="text-sm font-semibold text-stone-800">Business Setup Progress</p>
                <p className="text-xs text-stone-500">{complete} of {steps.length} steps complete</p>
              </div>
              <span className={`text-xs font-bold px-2.5 py-1 rounded-full ${pct >= 75 ? "bg-green-50 text-green-700" : pct >= 50 ? "bg-amber-50 text-amber-700" : "bg-stone-100 text-stone-600"}`}>
                {pct}%
              </span>
            </div>
            <div className="w-full bg-stone-100 rounded-full h-1.5 mb-3">
              <div className="bg-[#16A34A] h-1.5 rounded-full transition-all" style={{ width: `${pct}%` }} />
            </div>
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-2">
              {steps.map((s) => (
                <div key={s.label} className={`flex items-center gap-2 p-2 rounded-lg text-xs ${s.done ? "bg-green-50" : "bg-stone-50"}`}>
                  <div className={`w-4 h-4 rounded-full flex items-center justify-center shrink-0 text-white text-[9px] font-bold ${s.done ? "bg-green-500" : "bg-stone-300"}`}>
                    {s.done ? "✓" : "!"}
                  </div>
                  <div>
                    <p className={`font-medium ${s.done ? "text-green-700" : "text-stone-600"}`}>{s.label}</p>
                    <p className={`text-[10px] ${s.done ? "text-green-600" : "text-stone-400"}`}>
                      {s.done ? "Complete" : s.action}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        );
      })()}

      {/* Guidance cards — dismissible next-steps */}
      {entities.length > 0 && (() => {
        const visible = GUIDANCE_CARDS.filter((c) => !dismissedCards.has(c.key) && c.show(entities));
        if (visible.length === 0) return null;
        return (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {visible.map((card) => (
              <div key={card.key} className="bg-blue-50/50 border border-blue-100 rounded-xl p-4 relative group">
                <button
                  onClick={() => handleDismissCard(card.key)}
                  className="absolute top-2 right-2 text-stone-300 hover:text-stone-500 opacity-0 group-hover:opacity-100 transition-opacity"
                  title="Dismiss"
                >
                  <X size={14} />
                </button>
                <p className="text-sm font-semibold text-stone-800">{card.title}</p>
                <p className="text-xs text-stone-500 mt-1">{card.description}</p>
                <div className="flex items-center gap-3 mt-2">
                  {card.linkHref && (
                    <a href={card.linkHref} target="_blank" rel="noopener noreferrer" className="text-xs font-medium text-[#16A34A] hover:underline">
                      {card.linkLabel}
                    </a>
                  )}
                  {card.askHenry && (
                    <button
                      onClick={() => window.dispatchEvent(new CustomEvent("ask-henry", { detail: { message: card.askHenry } }))}
                      className="flex items-center gap-1 text-xs text-[#16A34A]/70 hover:text-[#16A34A]"
                    >
                      <MessageCircle size={10} /> Ask Henry
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        );
      })()}

      {/* Add / Edit form */}
      {showForm && (
        <Card padding="lg">
          <h3 className="text-sm font-semibold text-stone-900 mb-4">
            {editingEntity ? "Edit Business Entity" : "Add Business Entity"}
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="md:col-span-2">
              <label className="text-xs text-stone-500">Business / Entity Name *</label>
              <input
                type="text"
                value={fName}
                onChange={(e) => setFName(e.target.value)}
                placeholder="e.g. Acme Consulting LLC"
                className="w-full mt-1 text-sm border border-stone-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20"
              />
            </div>
            <div>
              <label className="text-xs text-stone-500">Entity Type</label>
              <select
                value={fEntityType}
                onChange={(e) => setFEntityType(e.target.value)}
                className="w-full mt-1 text-sm border border-stone-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20"
              >
                {ENTITY_TYPES.map((t) => (
                  <option key={t.value} value={t.value}>{t.label}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-xs text-stone-500">Tax Treatment</label>
              <select
                value={fTaxTreatment}
                onChange={(e) => setFTaxTreatment(e.target.value)}
                className="w-full mt-1 text-sm border border-stone-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20"
              >
                {TAX_TREATMENTS.map((t) => (
                  <option key={t.value} value={t.value}>{t.label}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-xs text-stone-500">EIN (optional)</label>
              <input
                type="text"
                value={fEin}
                onChange={(e) => setFEin(e.target.value)}
                placeholder="XX-XXXXXXX"
                className="w-full mt-1 text-sm border border-stone-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20"
              />
            </div>
            <div>
              <label className="text-xs text-stone-500">Active From</label>
              <input
                type="date"
                value={fActiveFrom}
                onChange={(e) => setFActiveFrom(e.target.value)}
                className="w-full mt-1 text-sm border border-stone-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20"
              />
            </div>
            <div>
              <label className="text-xs text-stone-500">Active To (leave blank if still active)</label>
              <input
                type="date"
                value={fActiveTo}
                onChange={(e) => setFActiveTo(e.target.value)}
                className="w-full mt-1 text-sm border border-stone-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20"
              />
            </div>
          </div>

          {/* Tax treatment context */}
          {fTaxTreatment && TAX_CONNECTIONS[fTaxTreatment] && (
            <div className="mt-4 p-3 bg-blue-50 border border-blue-100 rounded-lg">
              <p className="text-xs text-blue-800 font-medium">{TAX_CONNECTIONS[fTaxTreatment].effect}</p>
              <p className="text-xs text-blue-600 mt-0.5">{TAX_CONNECTIONS[fTaxTreatment].connects}</p>
            </div>
          )}

          <div className="mt-4">
            <label className="text-xs text-stone-500">Business Description</label>
            <textarea
              value={fDescription}
              onChange={(e) => setFDescription(e.target.value)}
              rows={2}
              placeholder="e.g. AI-powered car marketplace startup"
              className="w-full mt-1 text-sm border border-stone-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20"
            />
            <p className="text-[10px] text-stone-400 mt-0.5">Helps the AI categorizer understand what this business does.</p>
          </div>

          <div className="mt-4">
            <label className="text-xs text-stone-500">Expected Expense Types</label>
            <textarea
              value={fExpectedExpenses}
              onChange={(e) => setFExpectedExpenses(e.target.value)}
              rows={2}
              placeholder="e.g. cloud hosting, AI API costs, marketing, contractors"
              className="w-full mt-1 text-sm border border-stone-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20"
            />
            <p className="text-[10px] text-stone-400 mt-0.5">Comma-separated list of expense types you expect for this business.</p>
          </div>

          <div className="mt-4">
            <label className="text-xs text-stone-500">Notes</label>
            <textarea
              value={fNotes}
              onChange={(e) => setFNotes(e.target.value)}
              rows={2}
              placeholder="State of incorporation, purpose, etc."
              className="w-full mt-1 text-sm border border-stone-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20"
            />
          </div>

          <div className="mt-4 flex items-center gap-3">
            <button
              onClick={handleSave}
              disabled={saving || !fName.trim()}
              className="flex items-center gap-2 bg-[#16A34A] text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-[#15803D] disabled:opacity-60"
            >
              {saving && <Loader2 size={14} className="animate-spin" />}
              {editingEntity ? "Update Entity" : "Save Entity"}
            </button>
            <button onClick={resetForm} className="text-sm text-stone-500 hover:text-stone-700">Cancel</button>
          </div>
        </Card>
      )}

      {/* Filter */}
      <div className="flex items-center gap-3">
        <label className="flex items-center gap-2 text-sm text-stone-600 cursor-pointer">
          <input
            type="checkbox"
            checked={showInactive}
            onChange={(e) => setShowInactive(e.target.checked)}
            className="rounded border-stone-300"
          />
          Show inactive entities
        </label>
        <span className="ml-auto text-xs text-stone-400">{entities.length} entities</span>
      </div>

      {/* Entity list */}
      {loading ? (
        <div className="flex items-center gap-2 text-stone-500 text-sm py-8">
          <Loader2 size={16} className="animate-spin" /> Loading...
        </div>
      ) : entities.length === 0 ? (
        <EmptyState
          icon={<Building2 size={40} />}
          title="Track Your Side Business"
          description="Whether you're freelancing, launching a startup, or renting property — tracking it here connects your expenses to Tax Strategy, Reports, and Transactions."
          henryTip="Most HENRYs start with a sole proprietorship. You don't need an LLC or EIN to begin tracking expenses — just a name for your venture. I can help you figure out the right structure as you grow."
          askHenryPrompt="I'm thinking about starting a side business. What entity structure would you recommend? When do I need an EIN? Do I need a separate bank account?"
          action={
            <button
              onClick={() => setShowForm(true)}
              className="flex items-center gap-2 bg-[#16A34A] text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-[#15803D] shadow-sm"
            >
              <Plus size={14} /> Add Your First Business
            </button>
          }
          templates={BUSINESS_TEMPLATES.map((t) => ({
            icon: <t.icon size={18} className="text-stone-500" />,
            label: t.name,
            description: t.description,
            onClick: () => handleTemplateSelect(t),
          }))}
        />
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {entities.map((entity) => {
            const typeLabel = ENTITY_TYPES.find((t) => t.value === entity.entity_type)?.label || entity.entity_type;
            const taxLabel = TAX_TREATMENTS.find((t) => t.value === entity.tax_treatment)?.label || entity.tax_treatment;

            return (
              <Card key={entity.id} padding="md">
                <div className="flex items-start justify-between">
                  <Link href={`/business/${entity.id}`} className="flex items-start gap-3 flex-1 min-w-0 group">
                    <Building2 size={20} className="text-stone-400 mt-0.5 shrink-0" />
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <h4 className="text-sm font-semibold text-stone-900 group-hover:text-[#16A34A] transition-colors">{entity.name}</h4>
                        {!entity.is_active && (
                          <span className="text-xs bg-stone-100 text-stone-400 px-2 py-0.5 rounded-full">Inactive</span>
                        )}
                        {entity.is_provisional && (
                          <span className="text-xs bg-amber-50 text-amber-600 px-2 py-0.5 rounded-full">Provisional</span>
                        )}
                      </div>
                      <p className="text-xs text-stone-500 mt-0.5">{typeLabel}</p>
                    </div>
                  </Link>
                  <div className="flex items-center gap-1 shrink-0">
                    <button
                      onClick={() => openEdit(entity)}
                      className="p-1.5 text-stone-400 hover:text-[#16A34A] rounded"
                      title="Edit"
                    >
                      <Pencil size={13} />
                    </button>
                    <button
                      onClick={() => handleDelete(entity.id)}
                      className="p-1.5 text-stone-400 hover:text-red-500 rounded"
                    >
                      <Trash2 size={13} />
                    </button>
                  </div>
                </div>

                <div className="mt-3 space-y-1 text-xs">
                  <div className="flex items-center gap-1 text-stone-500">
                    <FileText size={11} className="shrink-0" />
                    <span className="font-medium text-stone-700">{taxLabel}</span>
                  </div>
                  {entity.ein && (
                    <p className="text-stone-400">EIN: {entity.ein}</p>
                  )}
                  {entity.active_from && (
                    <p className="text-stone-400">
                      Active: {new Date(entity.active_from).toLocaleDateString()}{entity.active_to ? ` \u2192 ${new Date(entity.active_to).toLocaleDateString()}` : " \u2192 Present"}
                    </p>
                  )}
                </div>

                {/* Business profile info */}
                {entity.description && (
                  <div className="mt-3 pt-3 border-t border-stone-100">
                    <p className="text-xs text-stone-600 line-clamp-2">{entity.description}</p>
                  </div>
                )}

                {/* View details + quick links */}
                <div className="mt-3 pt-3 border-t border-stone-100">
                  <Link
                    href={`/business/${entity.id}`}
                    className="flex items-center gap-1.5 text-xs font-medium text-[#16A34A] hover:text-[#15803D] transition-colors"
                  >
                    View Details <ChevronRight size={12} />
                  </Link>
                </div>

                {entity.notes && (
                  <p className="text-xs text-stone-400 mt-2 italic line-clamp-1">{entity.notes}</p>
                )}
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
