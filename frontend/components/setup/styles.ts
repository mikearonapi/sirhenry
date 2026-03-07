/**
 * Shared Tailwind class constants for the onboarding flow.
 * Ensures visual consistency across all setup screens.
 */

export const OB_INPUT =
  "w-full rounded-xl border-2 border-border px-4 py-3 text-sm " +
  "focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent bg-card " +
  "placeholder:text-text-muted transition-colors";

export const OB_DOLLAR =
  "w-full rounded-xl border-2 border-border pl-8 pr-4 py-3 text-sm " +
  "focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent bg-card " +
  "placeholder:text-text-muted transition-colors";

export const OB_SELECT = OB_INPUT;

export const OB_CTA =
  "bg-text-primary text-white dark:text-black px-8 py-3.5 rounded-xl text-base font-semibold font-display " +
  "hover:bg-text-primary/90 shadow-sm transition-colors flex items-center justify-center gap-2 " +
  "disabled:opacity-50";

export const OB_CTA_SECONDARY =
  "bg-card text-text-secondary px-6 py-3 rounded-xl text-sm font-medium border-2 border-border " +
  "hover:border-text-muted hover:bg-surface transition-colors flex items-center justify-center gap-2";

export const OB_CARD_SELECTED =
  "border-2 border-accent bg-green-50 ring-1 ring-accent/20";

export const OB_CARD_UNSELECTED =
  "border-2 border-border bg-card hover:border-text-muted";

export const OB_HEADING =
  "text-2xl md:text-3xl font-bold text-text-primary font-display tracking-tight";

export const OB_SUBTITLE =
  "text-sm text-text-secondary mt-1.5 leading-relaxed";

export const OB_LABEL =
  "text-xs font-medium text-text-secondary uppercase tracking-wider mb-2 block";
