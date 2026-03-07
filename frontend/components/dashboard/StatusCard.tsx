"use client";
import { ChevronRight } from "lucide-react";
import { formatCurrency } from "@/lib/utils";
import Card from "@/components/ui/Card";
import Link from "next/link";
import { useThemeColors } from "@/hooks/useThemeColors";

interface Props {
  effectiveSavingsRate: number;
  effectiveNetWorth: number;
  targetSavingsRate: number;
}

export default function StatusCard({
  effectiveSavingsRate, effectiveNetWorth, targetSavingsRate,
}: Props) {
  const statusLabel = effectiveSavingsRate >= targetSavingsRate
    ? "On Track"
    : effectiveSavingsRate >= targetSavingsRate * 0.5
      ? "At Risk"
      : "Behind";

  const statusMsg = effectiveSavingsRate >= targetSavingsRate
    ? `Your ${effectiveSavingsRate.toFixed(1)}% savings rate exceeds the ${targetSavingsRate}% target.`
    : effectiveSavingsRate >= targetSavingsRate * 0.5
      ? `You're saving ${effectiveSavingsRate.toFixed(1)}%. Boost to ${targetSavingsRate}% to get on track.`
      : `Savings rate is ${effectiveSavingsRate.toFixed(1)}%. Target is ${targetSavingsRate}% for your retirement goal.`;

  const colors = useThemeColors();

  const strokeColor = effectiveSavingsRate >= targetSavingsRate
    ? colors.positive
    : effectiveSavingsRate >= targetSavingsRate * 0.5
      ? colors.warning
      : colors.negative;

  const rateColor = effectiveSavingsRate >= targetSavingsRate
    ? colors.positive
    : effectiveSavingsRate >= targetSavingsRate * 0.5
      ? colors.warning
      : colors.negative;

  return (
    <Card padding="lg">
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-6">
        {/* Savings rate donut */}
        <div className="flex-shrink-0 w-32">
          <div className="relative w-24 h-24 mx-auto">
            <svg className="w-full h-full -rotate-90" viewBox="0 0 36 36">
              <path d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" fill="none" stroke={colors.gridLine} strokeWidth="2.5" />
              <path
                d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                fill="none"
                stroke={strokeColor}
                strokeWidth="2.5"
                strokeDasharray={`${Math.min(Math.max(effectiveSavingsRate, 0) / targetSavingsRate * 100, 100)} 100`}
                strokeLinecap="round"
              />
            </svg>
            <span className="absolute inset-0 flex items-center justify-center text-lg font-bold text-text-primary money">
              {effectiveSavingsRate.toFixed(0)}%
            </span>
          </div>
          <p className="text-xs text-text-secondary text-center mt-1">Savings Rate</p>
        </div>

        {/* Key metrics */}
        <div className="flex-1 grid grid-cols-2 sm:grid-cols-3 gap-4">
          <div>
            <p className="text-xs text-text-muted uppercase tracking-wide font-semibold">Net Worth</p>
            <p className="text-xl font-bold text-text-primary mt-0.5 money">{formatCurrency(effectiveNetWorth, true)}</p>
          </div>
          <div>
            <p className="text-xs text-text-muted uppercase tracking-wide font-semibold">Savings Rate</p>
            <p className="text-xl font-bold mt-0.5 money" style={{ color: rateColor }}>
              {effectiveSavingsRate.toFixed(1)}%
            </p>
            <p className="text-xs text-text-muted">Target: {targetSavingsRate}%</p>
          </div>
          <div className="col-span-2 sm:col-span-1">
            <p className="text-xs text-text-muted uppercase tracking-wide font-semibold">Status</p>
            <p className="text-sm font-medium text-text-secondary mt-1 leading-snug">{statusMsg}</p>
          </div>
        </div>

        {/* Trajectory CTA */}
        <div className="flex-shrink-0">
          <Link href="/retirement" className="flex items-center gap-1.5 text-xs font-medium text-accent hover:text-accent-hover whitespace-nowrap">
            See projection <ChevronRight size={13} />
          </Link>
        </div>
      </div>
    </Card>
  );
}
