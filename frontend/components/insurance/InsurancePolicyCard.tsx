"use client";

import { Pencil, Trash2 } from "lucide-react";
import { formatCurrency } from "@/lib/utils";
import Card from "@/components/ui/Card";
import type { InsurancePolicy } from "@/types/api";
import { getPolicyConfig } from "./constants";

interface InsurancePolicyCardProps {
  policy: InsurancePolicy;
  onEdit: (policy: InsurancePolicy) => void;
  onDelete: (id: number) => void;
}

export default function InsurancePolicyCard({ policy, onEdit, onDelete }: InsurancePolicyCardProps) {
  const cfg = getPolicyConfig(policy.policy_type);
  const today = new Date();
  const rd = policy.renewal_date ? new Date(policy.renewal_date) : null;
  const daysUntil = rd ? Math.round((rd.getTime() - today.getTime()) / (1000 * 60 * 60 * 24)) : null;
  const renewingUrgent = daysUntil !== null && daysUntil >= 0 && daysUntil <= 30;

  return (
    <Card padding="md">
      <div className="flex items-start justify-between">
        <div className="flex items-start gap-3">
          <span className="text-2xl">{cfg.icon}</span>
          <div>
            <div className="flex items-center gap-2">
              <h4 className="text-sm font-semibold text-text-primary">
                {policy.provider || cfg.label}
              </h4>
              {policy.employer_provided && (
                <span className="text-xs bg-blue-50 text-blue-600 px-2 py-0.5 rounded-full border border-blue-100">Employer</span>
              )}
              {!policy.is_active && (
                <span className="text-xs bg-surface text-text-muted px-2 py-0.5 rounded-full">Inactive</span>
              )}
            </div>
            <p className="text-xs text-text-secondary mt-0.5">
              {cfg.label}{policy.owner_spouse ? ` — Spouse ${policy.owner_spouse.toUpperCase()}` : ""}
            </p>
          </div>
        </div>
        <button onClick={() => onEdit(policy)} className="p-1.5 text-text-muted hover:text-accent rounded" title="Edit policy">
          <Pencil size={13} />
        </button>
        <button onClick={() => onDelete(policy.id)} className="p-1.5 text-text-muted hover:text-red-500 rounded">
          <Trash2 size={13} />
        </button>
      </div>

      <div className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
        {policy.coverage_amount != null && (
          <div>
            <span className="text-text-muted">Coverage: </span>
            <span className="font-medium text-text-secondary">{formatCurrency(policy.coverage_amount)}</span>
          </div>
        )}
        {policy.annual_premium != null && (
          <div>
            <span className="text-text-muted">Premium: </span>
            <span className="font-medium text-text-secondary">{formatCurrency(policy.annual_premium)}/yr</span>
          </div>
        )}
        {policy.deductible != null && (
          <div>
            <span className="text-text-muted">Deductible: </span>
            <span className="font-medium text-text-secondary">{formatCurrency(policy.deductible)}</span>
          </div>
        )}
        {policy.oop_max != null && (
          <div>
            <span className="text-text-muted">OOP Max: </span>
            <span className="font-medium text-text-secondary">{formatCurrency(policy.oop_max)}</span>
          </div>
        )}
        {rd && (
          <div className={renewingUrgent ? "text-amber-600 font-medium" : ""}>
            <span className="text-text-muted">Renews: </span>
            <span className={renewingUrgent ? "font-medium" : "font-medium text-text-secondary"}>
              {rd.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}
              {daysUntil !== null && daysUntil >= 0 && daysUntil <= 60 && (
                <span className="ml-1 text-amber-500">({daysUntil}d)</span>
              )}
            </span>
          </div>
        )}
      </div>

      {policy.notes && (
        <p className="text-xs text-text-muted mt-2 italic">{policy.notes}</p>
      )}
      {policy.beneficiaries_json && (() => {
        try {
          const bens: { name: string; relationship: string; percentage: string }[] = JSON.parse(policy.beneficiaries_json);
          return bens.length > 0 ? (
            <div className="mt-2 pt-2 border-t border-card-border">
              <p className="text-xs text-text-muted mb-1">Beneficiaries</p>
              {bens.map((b, i) => (
                <p key={i} className="text-xs text-text-secondary">
                  {b.name}{b.relationship ? ` (${b.relationship})` : ""}{b.percentage ? ` — ${b.percentage}%` : ""}
                </p>
              ))}
            </div>
          ) : null;
        } catch { return null; }
      })()}
    </Card>
  );
}
