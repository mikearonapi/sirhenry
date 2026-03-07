"use client";

import { Building2, ChevronDown, ChevronRight, Pencil, Trash2 } from "lucide-react";
import { formatCurrency } from "@/lib/utils";
import Card from "@/components/ui/Card";
import type { UnifiedGroup } from "./accounts-types";

interface AccountGroupListProps {
  groups: UnifiedGroup[];
  collapsedGroups: Set<string>;
  onToggleGroup: (key: string) => void;
}

export default function AccountGroupList({ groups, collapsedGroups, onToggleGroup }: AccountGroupListProps) {
  return (
    <>
      {groups.map((group) => {
        const isCollapsed = collapsedGroups.has(group.key);
        return (
          <Card key={group.key} padding="none">
            <button
              onClick={() => onToggleGroup(group.key)}
              className="w-full flex items-center justify-between px-5 py-4 hover:bg-surface"
            >
              <div className="flex items-center gap-3">
                {isCollapsed ? <ChevronRight size={16} className="text-text-muted" /> : <ChevronDown size={16} className="text-text-muted" />}
                {group.icon}
                <span className="font-semibold text-text-primary">{group.label}</span>
                <span className="text-xs text-text-muted">
                  {group.items.length} {group.items.length === 1 ? "item" : "items"}
                </span>
              </div>
              <span className={`font-bold tabular-nums ${group.isLiability ? "text-red-600" : "text-text-primary"}`}>
                {group.isLiability ? "-" : ""}{formatCurrency(group.total)}
              </span>
            </button>
            {!isCollapsed && (
              <div className="border-t border-border-light divide-y divide-border-light">
                {group.items.map((item) => (
                  <div key={item.id} className="flex items-center justify-between px-5 py-3.5 hover:bg-surface group/item">
                    <div className="flex items-center gap-3 flex-1 min-w-0">
                      <div className="w-8 h-8 rounded-full bg-surface flex items-center justify-center text-text-secondary text-xs font-bold shrink-0">
                        {item.name.charAt(0)}
                      </div>
                      <div className="min-w-0">
                        <div className="flex items-center gap-1.5">
                          <p className="text-sm font-medium text-text-primary truncate">{item.name}</p>
                          {item.badge && (
                            <span className="inline-flex items-center gap-0.5 text-xs font-medium bg-blue-50 text-blue-600 px-1.5 py-0.5 rounded shrink-0">
                              <Building2 size={9} />
                              {item.badge}
                            </span>
                          )}
                        </div>
                        <p className="text-xs text-text-muted truncate capitalize">{item.subtitle}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      <div className="text-right">
                        <p className={`text-sm font-semibold tabular-nums ${group.isLiability ? "text-red-600" : "text-text-primary"}`}>
                          {group.isLiability ? "-" : ""}{formatCurrency(item.value)}
                        </p>
                        {item.detail && (
                          <p className="text-xs text-text-muted">{item.detail}</p>
                        )}
                      </div>
                      {item.canEdit && (
                        <div className="flex items-center gap-1 opacity-0 group-hover/item:opacity-100 transition-opacity">
                          <button
                            onClick={(e) => { e.stopPropagation(); item.onEdit?.(); }}
                            className="p-1.5 rounded-md hover:bg-surface text-text-muted hover:text-text-secondary"
                            title="Edit"
                          >
                            <Pencil size={14} />
                          </button>
                          <button
                            onClick={(e) => { e.stopPropagation(); item.onDelete?.(); }}
                            className="p-1.5 rounded-md hover:bg-red-50 text-text-muted hover:text-red-500"
                            title="Delete"
                          >
                            <Trash2 size={14} />
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>
        );
      })}
    </>
  );
}
