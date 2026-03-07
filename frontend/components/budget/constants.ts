import type { TabDef } from "@/components/ui/TabBar";
import { Target, TrendingUp } from "lucide-react";

export const BUDGET_TABS: TabDef[] = [
  { id: "budget", label: "Budget", icon: Target },
  { id: "forecast", label: "Forecast", icon: TrendingUp },
];
