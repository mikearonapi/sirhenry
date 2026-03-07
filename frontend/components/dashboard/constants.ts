import type { TabDef } from "@/components/ui/TabBar";
import { LayoutDashboard, Lightbulb } from "lucide-react";

export const DASHBOARD_TABS: TabDef[] = [
  { id: "overview", label: "Overview", icon: LayoutDashboard },
  { id: "insights", label: "Insights", icon: Lightbulb },
];
