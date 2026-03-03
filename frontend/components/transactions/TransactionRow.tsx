"use client";
import { ChevronRight, Tag, AlertTriangle, Building2 } from "lucide-react";
import { formatCurrency, segmentColor } from "@/lib/utils";
import type { BusinessEntity, Transaction } from "@/types/api";
import Badge from "@/components/ui/Badge";
import { CATEGORY_ICONS } from "./constants";

interface Props {
  tx: Transaction;
  entityMap: Map<number, BusinessEntity>;
  onSelect: (tx: Transaction) => void;
}

export default function TransactionRow({ tx, entityMap, onSelect }: Props) {
  const eid = tx.effective_business_entity_id ?? tx.business_entity_id;
  const entityName = eid ? (entityMap.get(eid)?.name ?? null) : null;
  const cat = tx.effective_category ?? "";
  const catIcon = CATEGORY_ICONS[cat] ?? "";
  const isUncategorized = !cat || cat === "Uncategorized";

  return (
    <button
      onClick={() => onSelect(tx)}
      className={`flex items-center w-full text-left px-4 py-2 hover:bg-stone-50/70 transition-colors ${tx.is_excluded ? "opacity-40" : ""}`}
    >
      <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs shrink-0 mr-3 ${
        tx.amount >= 0 ? "bg-green-50 text-green-600" : "bg-stone-100 text-stone-500"
      }`}>
        {catIcon || tx.description.charAt(0).toUpperCase()}
      </div>

      <div className="flex-1 min-w-0 mr-3">
        <p className="text-[13px] font-medium text-stone-800 truncate leading-tight">
          {tx.description}
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
