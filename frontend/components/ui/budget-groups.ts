/** Shared expense group definitions used by Budget and Retirement pages. */

export const EXPENSE_GROUPS: Record<string, string[]> = {
  "Food & Dining": [
    "Groceries", "Groceries & Food", "Restaurants & Bars", "Restaurants & Dining",
    "Fast Food", "Coffee Shops", "Coffee & Beverages",
  ],
  "Home & Home Services": [
    "Mortgage", "HOA Dues", "Home Security", "House Cleaners", "House Keeper",
    "Home Improvement", "Lawn Care", "Pest Control", "Water",
    "Home & Garden", "Kitchen & Dining", "Cleaning & Household",
  ],
  "Bills & Utilities": ["Internet", "Internet & Phone", "Phone", "Phone & Internet", "Electric", "Gas Utility"],
  "Gifts & Donations": ["Charity", "Charitable Donations", "Birthday Gifts", "Christmas Gifts", "Tithe", "Gifts & Flowers", "Gift"],
  "Family & Children": [
    "Kid's Clothing", "Child Activities", "Babysitting", "Pets", "Pet Insurance",
    "Pet Care", "Baby & Child", "Baby & Kids", "Destiny School", "Childcare & Education",
    "Family Photography",
  ],
  "Shopping": ["Amazon", "Shopping", "Shopping & Retail", "Postage & Shipping", "Electronics & Technology", "Tools & Hardware"],
  "Health & Wellness": ["Dentist", "Fitness", "Fitness & Gym", "Medical", "Health & Medical", "Health & Fitness", "Personal Care & Spa", "Personal Care & Beauty", "Sports & Fitness"],
  "Discretionary": ["Discretionary", "Christine's Discretionary"],
  "Travel & Lifestyle": [
    "TV, Streaming & Entertainment", "Streaming & Subscriptions", "Streaming & Digital",
    "Vacation", "Haircut", "Entertainment & Recreation", "Hotel & Lodging",
    "Airline & Travel", "Toys & Games", "Books & Media",
  ],
  "Education": ["Education", "Education - Other", "Education & Tuition"],
  "Auto & Transport": ["Gas", "Gas & Fuel", "Parking & Tolls", "Auto Maintenance", "Vehicle Purchase", "Auto & Transportation", "Automotive"],
  "Financial": ["Financial Fees", "Financial & Legal Services", "Insurance", "Taxes", "Tax Payments", "Personal Property Tax", "Vivant Taxes", "Bank Fees & Interest"],
};

export const GROUP_ICONS: Record<string, string> = {
  "Food & Dining": "🍽️",
  "Bills & Utilities": "💡",
  "Shopping": "🛍️",
  "Health & Wellness": "💊",
  "Home & Home Services": "🏠",
  "Travel & Lifestyle": "✈️",
  "Family & Children": "👨‍👩‍👧‍👦",
  "Education": "🎓",
  "Auto & Transport": "🚗",
  "Financial": "🏦",
  "Discretionary": "💳",
  "Gifts & Donations": "❤️",
  "Other": "📦",
};

export function getExpenseGroup(category: string): string {
  for (const [group, cats] of Object.entries(EXPENSE_GROUPS)) {
    if (cats.includes(category)) return group;
  }
  if (category.includes("Discretionary")) return "Discretionary";
  if (category.startsWith("Gen AI") || category.startsWith("Office")) return "Other";
  return "Other";
}
