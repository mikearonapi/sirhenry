"use client";
import { useEffect, useState } from "react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";
import { getRetirementProfiles, getTrajectoryProjection } from "@/lib/api";
import type { TrajectoryProjection } from "@/lib/api";
import Link from "next/link";
import { TrendingUp, ArrowRight } from "lucide-react";

function fmt(n: number): string {
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `$${(n / 1_000).toFixed(0)}K`;
  return `$${n.toFixed(0)}`;
}

interface ChartRow {
  age: number;
  pessimistic: number;
  base: number;
  optimistic: number;
}

function buildChartData(proj: TrajectoryProjection): ChartRow[] {
  const pess = proj.scenarios.find((s) => s.name === "Pessimistic")?.data ?? [];
  const base = proj.scenarios.find((s) => s.name === "Base")?.data ?? [];
  const opt  = proj.scenarios.find((s) => s.name === "Optimistic")?.data ?? [];

  return base.map((row, i) => ({
    age: row.age,
    pessimistic: pess[i]?.balance ?? 0,
    base: row.balance,
    optimistic: opt[i]?.balance ?? 0,
  }));
}

export default function TrajectoryChart() {
  const [proj, setProj] = useState<TrajectoryProjection | null>(null);
  const [loading, setLoading] = useState(true);
  const [profileId, setProfileId] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const profiles = await getRetirementProfiles();
        const primary = profiles.find((p) => p.is_primary) ?? profiles[0];
        if (!primary || cancelled) return;
        setProfileId(primary.id);
        const data = await getTrajectoryProjection(primary.id);
        if (!cancelled) setProj(data);
      } catch {
        // silently fail — show setup CTA
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  if (loading) {
    return (
      <div className="h-40 flex items-center justify-center">
        <div className="w-5 h-5 border-2 border-green-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!proj) {
    return (
      <div className="flex flex-col items-center justify-center py-8 text-center">
        <div className="w-12 h-12 rounded-xl bg-stone-100 flex items-center justify-center mb-3">
          <TrendingUp size={22} className="text-stone-300" />
        </div>
        <p className="text-sm font-medium text-stone-700 mb-1">No retirement profile yet</p>
        <p className="text-xs text-stone-400 mb-4 max-w-xs">
          Set up a retirement profile to see your trajectory fan chart and probability of success.
        </p>
        <Link
          href="/retirement"
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-[#16A34A] bg-[#DCFCE7] px-4 py-2 rounded-full hover:bg-[#BBF7D0] transition-colors"
        >
          Set up projection <ArrowRight size={12} />
        </Link>
      </div>
    );
  }

  const chartData = buildChartData(proj);
  const readinessPct = proj.readiness_pct;
  const statusColor = readinessPct >= 90 ? "#16A34A" : readinessPct >= 70 ? "#D97706" : "#DC2626";
  const statusLabel = readinessPct >= 90 ? "On Track" : readinessPct >= 70 ? "Needs Work" : "Behind";

  return (
    <div className="space-y-4">
      {/* Summary row */}
      <div className="grid grid-cols-3 gap-4">
        <div>
          <p className="text-[11px] text-stone-400 uppercase tracking-wide">Target Nest Egg</p>
          <p className="text-lg font-bold text-stone-900 money">{fmt(proj.target_nest_egg)}</p>
        </div>
        <div>
          <p className="text-[11px] text-stone-400 uppercase tracking-wide">Projected</p>
          <p className="text-lg font-bold money" style={{ color: statusColor }}>{fmt(proj.projected_nest_egg)}</p>
        </div>
        <div>
          <p className="text-[11px] text-stone-400 uppercase tracking-wide">Readiness</p>
          <div className="flex items-center gap-2 mt-0.5">
            <p className="text-lg font-bold money" style={{ color: statusColor }}>{readinessPct.toFixed(0)}%</p>
            <span
              className="text-[10px] font-semibold px-2 py-0.5 rounded-full"
              style={{ color: statusColor, background: readinessPct >= 90 ? "#DCFCE7" : readinessPct >= 70 ? "#FEF3C7" : "#FEE2E2" }}
            >
              {statusLabel}
            </span>
          </div>
        </div>
      </div>

      {/* Fan chart */}
      <ResponsiveContainer width="100%" height={220}>
        <AreaChart data={chartData} margin={{ top: 5, right: 5, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id="traj-opt" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#16A34A" stopOpacity={0.15} />
              <stop offset="95%" stopColor="#16A34A" stopOpacity={0.02} />
            </linearGradient>
            <linearGradient id="traj-base" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#16A34A" stopOpacity={0.35} />
              <stop offset="95%" stopColor="#16A34A" stopOpacity={0.05} />
            </linearGradient>
          </defs>
          <XAxis
            dataKey="age"
            tick={{ fontSize: 11, fill: "#9CA3AF" }}
            axisLine={false}
            tickLine={false}
            tickFormatter={(v) => `${v}`}
          />
          <YAxis
            tickFormatter={fmt}
            tick={{ fontSize: 11, fill: "#9CA3AF" }}
            axisLine={false}
            tickLine={false}
            width={55}
          />
          <Tooltip
            contentStyle={{ borderRadius: 8, border: "1px solid #E5E7EB", fontSize: 12, fontFamily: "var(--font-mono)" }}
            formatter={(v) => [fmt(Number(v ?? 0)), undefined]}
            labelFormatter={(l) => `Age ${l}`}
          />
          <ReferenceLine
            y={proj.target_nest_egg}
            stroke="#CA8A04"
            strokeDasharray="4 3"
            strokeWidth={1.5}
            label={{ value: "Target", position: "right", fontSize: 10, fill: "#CA8A04" }}
          />
          {/* Outer band — optimistic to pessimistic spread */}
          <Area
            type="monotone"
            dataKey="optimistic"
            stroke="#16A34A"
            strokeWidth={1}
            strokeDasharray="4 2"
            fill="url(#traj-opt)"
            dot={false}
            name="Optimistic"
          />
          {/* Base line */}
          <Area
            type="monotone"
            dataKey="base"
            stroke="#16A34A"
            strokeWidth={2}
            fill="url(#traj-base)"
            dot={false}
            name="Base"
          />
          {/* Lower bound */}
          <Area
            type="monotone"
            dataKey="pessimistic"
            stroke="#6B7280"
            strokeWidth={1}
            strokeDasharray="4 2"
            fill="white"
            dot={false}
            name="Pessimistic"
          />
        </AreaChart>
      </ResponsiveContainer>

      <div className="flex items-center justify-between">
        <p className="text-[11px] text-stone-400">
          Fan shows ±2% return scenarios · Target at retirement age {proj.retirement_age}
        </p>
        <Link href={`/retirement${profileId ? `?id=${profileId}` : ""}`} className="text-xs text-[#16A34A] hover:underline font-medium flex items-center gap-1">
          Full analysis <ArrowRight size={11} />
        </Link>
      </div>
    </div>
  );
}
