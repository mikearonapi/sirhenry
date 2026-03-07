import type { TabDef } from "@/components/ui/TabBar";
import { Calendar, AlertTriangle, ArrowRightLeft, Calculator, LogOut, ShoppingCart } from "lucide-react";

export const EQUITY_ANALYSIS_TABS: TabDef[] = [
  { id: "vesting", label: "Vesting Calendar", icon: Calendar },
  { id: "withholding", label: "Underwithholding", icon: AlertTriangle },
  { id: "sell", label: "Sell Strategy", icon: ArrowRightLeft },
  { id: "amt", label: "AMT Calculator", icon: Calculator },
  { id: "leave", label: "What If I Leave?", icon: LogOut },
  { id: "espp", label: "ESPP Optimizer", icon: ShoppingCart },
];
