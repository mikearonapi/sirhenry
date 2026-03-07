import { AlertTriangle, AlertCircle, CheckCircle2 } from "lucide-react";

export const POLICY_TYPES = [
  { value: "health", label: "Health", icon: "\u{1F3E5}", color: "bg-red-50 text-red-700 border-red-100" },
  { value: "life", label: "Life", icon: "\u2764\uFE0F", color: "bg-pink-50 text-pink-700 border-pink-100" },
  { value: "disability", label: "Disability", icon: "\u{1F9BA}", color: "bg-orange-50 text-orange-700 border-orange-100" },
  { value: "auto", label: "Auto", icon: "\u{1F697}", color: "bg-blue-50 text-blue-700 border-blue-100" },
  { value: "home", label: "Home", icon: "\u{1F3E0}", color: "bg-green-50 text-green-700 border-green-100" },
  { value: "umbrella", label: "Umbrella", icon: "\u2602\uFE0F", color: "bg-indigo-50 text-indigo-700 border-indigo-100" },
  { value: "vision", label: "Vision", icon: "\u{1F441}\uFE0F", color: "bg-cyan-50 text-cyan-700 border-cyan-100" },
  { value: "dental", label: "Dental", icon: "\u{1F9B7}", color: "bg-teal-50 text-teal-700 border-teal-100" },
  { value: "ltc", label: "Long-Term Care", icon: "\u{1F3E8}", color: "bg-purple-50 text-purple-700 border-purple-100" },
  { value: "pet", label: "Pet", icon: "\u{1F43E}", color: "bg-amber-50 text-amber-700 border-amber-100" },
  { value: "other", label: "Other", icon: "\u{1F4CB}", color: "bg-surface text-text-secondary border-border" },
] as const;

export function getPolicyConfig(type: string) {
  return POLICY_TYPES.find((p) => p.value === type) || POLICY_TYPES[POLICY_TYPES.length - 1];
}

export const SEVERITY_CONFIG = {
  high: { label: "High Priority", color: "text-red-600", bg: "bg-red-50 border-red-100", icon: AlertTriangle },
  medium: { label: "Review Needed", color: "text-amber-600", bg: "bg-amber-50 border-amber-100", icon: AlertCircle },
  low: { label: "OK", color: "text-green-600", bg: "bg-green-50 border-green-100", icon: CheckCircle2 },
} as const;
