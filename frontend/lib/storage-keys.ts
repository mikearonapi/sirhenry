/**
 * Centralized localStorage key constants.
 * All localStorage access should use these keys to prevent typos and
 * make it easy to find/audit all persisted state.
 */

// ─── Onboarding & App State ──────────────────────────────────────────
export const FIRST_RUN_KEY = "henry.first-run-complete";
export const SPLASH_SEEN_KEY = "henry.splash-seen";
export const DEMO_MODE_KEY = "henry.demo-mode";
export const ONBOARDING_GOALS_KEY = "henry.onboarding-goals";

// ─── Sidebar ─────────────────────────────────────────────────────────
export const SIDEBAR_COLLAPSED_KEY = "sidebar.main-collapsed";
export const SIDEBAR_SECTIONS_KEY = "sidebar.collapsed-sections";
export const SIDEBAR_SECTION_COLLAPSE_KEY = "sidebar.collapsed";

// ─── Dashboard ───────────────────────────────────────────────────────
export const DISMISSED_INSIGHTS_KEY = "dismissed-insights";

// ─── Business ────────────────────────────────────────────────────────
export const BUSINESS_GUIDANCE_KEY = "business.guidance-dismissed";

// ─── Tax Strategy ────────────────────────────────────────────────────
export const TAX_INTERVIEW_STEP_KEY = "tax-interview-step";

// ─── Admin Settings ──────────────────────────────────────────────────
/** Prefix for admin settings — usage: `${SETTINGS_PREFIX}.${key}` */
export const SETTINGS_PREFIX = "settings";
