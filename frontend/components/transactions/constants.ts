export const SEGMENTS = ["", "personal", "business", "investment", "reimbursable"] as const;
export const PAGE_SIZE = 50;

export const BASE_CATEGORIES = [
  "Groceries", "Restaurants & Bars", "Coffee Shops", "Fast Food",
  "Gas", "Auto Maintenance", "Parking & Tolls",
  "Airline & Travel", "Hotel & Lodging", "Vacation",
  "Shopping", "Clothing & Apparel",
  "Health & Medical", "Dentist", "Fitness", "Pharmacy & Prescriptions",
  "Home Improvement", "Home Security", "Lawn Care", "Pest Control",
  "Electric", "Gas Utility", "Water", "Internet", "Phone",
  "TV, Streaming & Entertainment", "Gen AI",
  "Education - Other", "Childcare & Education",
  "Charity", "Tithe", "Insurance",
  "Mortgage", "HOA Dues", "Personal Property Tax",
  "Credit Card Payment", "Financial Fees", "Financial & Legal Services",
  "Tax Payments", "Taxes",
  "Haircut", "Personal Care & Spa", "Pet Insurance", "Pets",
  "Babysitting", "Child Activities", "Kid's Clothing",
  "House Cleaners", "House Keeper", "Postage & Shipping",
  "Business Technology", "Business — Advertising & Marketing",
  "Business — Software & Subscriptions", "Business — Office Supplies",
  "Business — Professional Services", "Business — Meals (50% deductible)",
  "Business — Travel & Transportation", "Business — Education & Training",
  "Business — Dues & Memberships", "Business — Legal & Accounting",
  "Business — Equipment & Technology", "Business — Other",
  "W-2 Wages", "Dividend Income", "Interest Income", "Other Income",
  "Capital Gain", "Board / Director Income",
  "Savings", "Transfer", "Check", "Payment / Refund", "Uncategorized",
];

export const CATEGORY_ICONS: Record<string, string> = {
  "Groceries": "\u{1F6D2}", "Restaurants & Bars": "\u{1F37D}\u{FE0F}", "Coffee Shops": "\u2615",
  "Fast Food": "\u{1F354}", "Gas": "\u26FD", "Auto Maintenance": "\u{1F697}",
  "Shopping": "\u{1F6CD}\u{FE0F}", "Health & Medical": "\u{1F3E5}", "Dentist": "\u{1F9B7}",
  "Home Improvement": "\u{1F3E0}", "Electric": "\u{1F4A1}", "Internet": "\u{1F4F1}",
  "TV, Streaming & Entertainment": "\u{1F4FA}", "Airline & Travel": "\u2708\u{FE0F}",
  "Hotel & Lodging": "\u{1F3E8}", "Charity": "\u2764\u{FE0F}", "Tithe": "\u26EA",
  "W-2 Wages": "\u{1F4BC}", "Transfer": "\u{1F504}", "Interest Income": "\u{1F4B0}",
  "Dividend Income": "\u{1F4C8}", "Other Income": "\u{1F4B5}", "Education - Other": "\u{1F393}",
  "Mortgage": "\u{1F3E0}", "Insurance": "\u{1F6E1}\u{FE0F}", "Vacation": "\u{1F334}",
  "Credit Card Payment": "\u{1F4B3}", "Fitness": "\u{1F3CB}\u{FE0F}", "Pets": "\u{1F43E}",
  "Babysitting": "\u{1F476}", "Child Activities": "\u{1F3A8}", "Savings": "\u{1F3E6}",
};

export function groupByDate<T extends { date: string }>(transactions: T[]): Map<string, T[]> {
  const groups = new Map<string, T[]>();
  for (const tx of transactions) {
    const dateKey = tx.date;
    const list = groups.get(dateKey) ?? [];
    list.push(tx);
    groups.set(dateKey, list);
  }
  return groups;
}

export function formatDateLabel(dateStr: string): string {
  const d = new Date(dateStr);
  const today = new Date();
  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);
  if (d.toDateString() === today.toDateString()) return "Today";
  if (d.toDateString() === yesterday.toDateString()) return "Yesterday";
  return d.toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric", year: "numeric" });
}
