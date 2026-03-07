import type { TabDef } from "@/components/ui/TabBar";

export const SECTOR_COLORS = [
  "#16A34A", "#3b82f6", "#22c55e", "#f59e0b", "#8b5cf6",
  "#06b6d4", "#ec4899", "#14b8a6", "#f43f5e", "#6366f1",
  "#64748b", "#a855f7",
];

export const ASSET_CLASSES = [
  { value: "stock", label: "Stock" },
  { value: "etf", label: "ETF" },
  { value: "mutual_fund", label: "Mutual Fund" },
  { value: "bond", label: "Bond" },
  { value: "reit", label: "REIT" },
  { value: "other", label: "Other" },
];

export type PortfolioTabId = "overview" | "holdings" | "performance" | "allocation" | "risk" | "networth";

export const TABS: TabDef[] = [
  { id: "overview", label: "Overview" },
  { id: "holdings", label: "Holdings" },
  { id: "performance", label: "Performance" },
  { id: "allocation", label: "Allocation" },
  { id: "risk", label: "Risk" },
  { id: "networth", label: "Net Worth" },
];
