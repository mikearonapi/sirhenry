export function formatCurrency(amount: number, compact = false): string {
  if (compact && Math.abs(amount) >= 1000) {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
      notation: "compact",
      maximumFractionDigits: 1,
    }).format(amount);
  }
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(amount);
}

export function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export function monthName(month: number): string {
  return new Date(2000, month - 1, 1).toLocaleString("en-US", { month: "long" });
}

export function segmentColor(segment: string | null): string {
  switch (segment) {
    case "business":
      return "bg-blue-50 text-blue-700";
    case "investment":
      return "bg-purple-50 text-purple-700";
    case "reimbursable":
      return "bg-amber-50 text-amber-700";
    case "personal":
    default:
      return "bg-stone-100 text-stone-600";
  }
}

export function formatPercent(value: number, decimals = 1): string {
  return `${value.toFixed(decimals)}%`;
}

export function formatCompactCurrency(amount: number): string {
  if (Math.abs(amount) >= 1_000_000) {
    return `$${(amount / 1_000_000).toFixed(2)}M`;
  }
  if (Math.abs(amount) >= 1_000) {
    return `$${(amount / 1_000).toFixed(0)}K`;
  }
  return formatCurrency(amount);
}

export const CATEGORY_COLORS: Record<string, string> = {
  "Groceries & Food": "#16a34a",
  "Restaurants & Dining": "#f59e0b",
  "Shopping & Retail": "#3b82f6",
  "Home & Garden": "#8b5cf6",
  "Auto & Transportation": "#06b6d4",
  "Entertainment & Recreation": "#ec4899",
  "Health & Medical": "#14b8a6",
  "Utilities": "#6366f1",
  "Education & Tuition": "#a855f7",
  "Charitable Donations": "#f43f5e",
  "Insurance Premiums": "#64748b",
  "Travel & Lifestyle": "#0ea5e9",
  "W-2 Wages": "#16a34a",
  "Dividend Income": "#8b5cf6",
  "Interest Income": "#06b6d4",
  "Mortgage": "#16A34A",
  "Tithe": "#f59e0b",
  "House Keeper": "#ec4899",
  "Vacation": "#16A34A",
};

export function statusColor(status: string): string {
  switch (status) {
    case "completed":
      return "text-green-600";
    case "processing":
      return "text-yellow-600";
    case "failed":
      return "text-red-600";
    case "duplicate":
      return "text-gray-500";
    default:
      return "text-gray-600";
  }
}

export function priorityLabel(p: number): string {
  const labels: Record<number, string> = { 1: "Critical", 2: "High", 3: "Medium", 4: "Low", 5: "Optional" };
  return labels[p] ?? "Medium";
}

export function priorityColor(p: number): string {
  if (p === 1) return "bg-red-100 text-red-800";
  if (p === 2) return "bg-orange-100 text-orange-800";
  if (p === 3) return "bg-yellow-100 text-yellow-800";
  if (p === 4) return "bg-blue-100 text-blue-800";
  return "bg-gray-100 text-gray-600";
}

export function safeJsonParse<T>(json: string | null | undefined, fallback: T): T {
  if (!json) return fallback;
  try {
    return JSON.parse(json) as T;
  } catch {
    return fallback;
  }
}
