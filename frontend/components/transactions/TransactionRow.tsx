"use client";
import { ChevronRight, Tag, AlertTriangle, Building2, Bot, Package } from "lucide-react";
import { formatCurrency, segmentColor, cleanTransactionName } from "@/lib/utils";
import type { BusinessEntity, Transaction } from "@/types/api";
import Badge from "@/components/ui/Badge";
import { CATEGORY_ICONS } from "./constants";

interface Props {
  tx: Transaction;
  entityMap: Map<number, BusinessEntity>;
  onSelect: (tx: Transaction) => void;
  selected?: boolean;
  onToggleSelect?: (id: number) => void;
}

export default function TransactionRow({ tx, entityMap, onSelect, selected, onToggleSelect }: Props) {
  const eid = tx.effective_business_entity_id ?? tx.business_entity_id;
  const entityName = eid ? (entityMap.get(eid)?.name ?? null) : null;
  const cat = tx.effective_category ?? "";
  const catIcon = CATEGORY_ICONS[cat] ?? "";
  const isUncategorized = !cat || cat === "Uncategorized";
  const hasLowConfidence = tx.ai_confidence !== null && tx.ai_confidence < 0.7 && !tx.is_manually_reviewed;
  const logoUrl = tx.merchant_logo_url;
  const displayName = cleanTransactionName(tx.description, tx.merchant_name);

  return (
    <button
      onClick={() => onSelect(tx)}
      className={`flex items-center w-full text-left px-4 py-2 hover:bg-stone-50/70 transition-colors ${tx.is_excluded ? "opacity-40" : ""} ${selected ? "bg-green-50/50" : ""}`}
    >
      {onToggleSelect && (
        <input
          type="checkbox"
          checked={selected ?? false}
          onChange={(e) => { e.stopPropagation(); onToggleSelect(tx.id); }}
          onClick={(e) => e.stopPropagation()}
          className="mr-2 rounded border-stone-300 text-[#16A34A] focus:ring-[#16A34A]/20 shrink-0"
        />
      )}
      {logoUrl ? (
        <img
          src={logoUrl}
          alt=""
          className="w-7 h-7 rounded-full shrink-0 mr-3 object-cover"
          onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
        />
      ) : (
        <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs shrink-0 mr-3 ${
          tx.amount >= 0 ? "bg-green-50 text-green-600" : "bg-stone-100 text-stone-500"
        }`}>
          {catIcon || displayName.charAt(0).toUpperCase()}
        </div>
      )}

      <div className="flex-1 min-w-0 mr-3">
        <p className="text-[13px] font-medium text-stone-800 truncate leading-tight">
          {displayName}
        </p>
        <div className="flex items-center gap-1.5 mt-0.5">
          {isUncategorized ? (
            <span className="text-[11px] text-amber-600 font-medium flex items-center gap-0.5">
              <AlertTriangle size={9} /> Uncategorized
            </span>
          ) : (
            <span className="text-[11px] text-stone-400 flex items-center gap-0.5">
              <Tag size={8} /> {cat}
            </span>
          )}
          {entityName && (
            <>
              <span className="text-stone-300">&middot;</span>
              <span className="text-[11px] text-blue-500 flex items-center gap-0.5">
                <Building2 size={8} /> {entityName}
              </span>
            </>
          )}
          {tx.category_override && (
            <>
              <span className="text-stone-300">&middot;</span>
              <span className="text-[11px] text-violet-500">edited</span>
            </>
          )}
          {tx.data_source === "amazon" && tx.parent_transaction_id && (
            <>
              <span className="text-stone-300">&middot;</span>
              <span className="text-[11px] text-orange-500 flex items-center gap-0.5">
                <Package size={8} /> Amazon
              </span>
            </>
          )}
          {hasLowConfidence && (
            <>
              <span className="text-stone-300">&middot;</span>
              <span className="text-[11px] text-amber-500 flex items-center gap-0.5">
                <Bot size={8} /> Low confidence
              </span>
            </>
          )}
        </div>
      </div>

      <Badge className={`mr-3 text-[10px] px-1.5 py-0.5 ${segmentColor(tx.effective_segment)}`}>
        {tx.effective_segment ?? tx.segment}
      </Badge>

      <span className={`text-[13px] font-semibold tabular-nums min-w-[90px] text-right mr-2 ${
        tx.amount >= 0 ? "text-green-600" : "text-stone-800"
      }`}>
        {tx.amount >= 0 ? "+" : ""}{formatCurrency(tx.amount)}
      </span>

      <ChevronRight size={14} className="text-stone-300 shrink-0" />
    </button>
  );
}
