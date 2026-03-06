"use client";
import { useCallback, useEffect, useState } from "react";
import { Loader2, Check, MessageCircle } from "lucide-react";
import Card from "@/components/ui/Card";
import ProgressBar from "@/components/ui/ProgressBar";
import { request } from "@/lib/api-client";
import { getErrorMessage } from "@/lib/errors";
import SirHenryName from "@/components/ui/SirHenryName";

const COLORS: Record<string, string> = {
  stock: "#3b82f6",
  etf: "#22c55e",
  bond: "#f59e0b",
  crypto: "#8b5cf6",
  reit: "#06b6d4",
  mutual_fund: "#ec4899",
  other: "#64748b",
};

const LABELS: Record<string, string> = {
  stock: "Stocks",
  etf: "ETFs",
  bond: "Bonds",
  crypto: "Crypto",
  reit: "REITs",
  mutual_fund: "Mutual Funds",
  other: "Other",
};

interface Preset {
  name: string;
  allocation: Record<string, number>;
}

interface TargetAllocationEditorProps {
  onSaved?: () => void;
}

export default function TargetAllocationEditor({ onSaved }: TargetAllocationEditorProps) {
  const [allocation, setAllocation] = useState<Record<string, number>>({});
  const [name, setName] = useState("My Target Allocation");
  const [presets, setPresets] = useState<Record<string, Preset>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [current, presetsData] = await Promise.all([
        request<{ id: number | null; name: string; allocation: Record<string, number> }>("/portfolio/target-allocation"),
        request<{ presets: Record<string, Preset> }>("/portfolio/target-allocation/presets"),
      ]);
      setAllocation(current.allocation);
      setName(current.name);
      setPresets(presetsData.presets);
    } catch (e: unknown) {
      setError(getErrorMessage(e));
    }
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  function handleSliderChange(key: string, value: number) {
    const old = allocation[key] ?? 0;
    const diff = value - old;
    const others = Object.keys(allocation).filter((k) => k !== key && allocation[k] > 0);
    if (others.length === 0) return;

    const newAlloc = { ...allocation, [key]: value };
    // Distribute the difference proportionally among other asset classes
    let remaining = -diff;
    const otherTotal = others.reduce((s, k) => s + (allocation[k] ?? 0), 0);
    for (const k of others) {
      const share = otherTotal > 0 ? (allocation[k] ?? 0) / otherTotal : 1 / others.length;
      const adj = Math.round(remaining * share);
      newAlloc[k] = Math.max(0, (allocation[k] ?? 0) + adj);
    }

    // Ensure total is exactly 100
    const total = Object.values(newAlloc).reduce((s, v) => s + v, 0);
    if (total !== 100) {
      const adjustKey = others.find((k) => newAlloc[k] > 0) ?? key;
      newAlloc[adjustKey] += 100 - total;
    }

    setAllocation(newAlloc);
    setSaved(false);
  }

  function applyPreset(key: string) {
    const preset = presets[key];
    if (!preset) return;
    setAllocation(preset.allocation);
    setName(preset.name);
    setSaved(false);
  }

  async function handleSave() {
    setSaving(true);
    setError(null);
    try {
      await request("/portfolio/target-allocation", {
        method: "PUT",
        body: JSON.stringify({ name, allocation }),
      });
      setSaved(true);
      onSaved?.();
      setTimeout(() => setSaved(false), 2000);
    } catch (e: unknown) {
      setError(getErrorMessage(e));
    }
    setSaving(false);
  }

  const total = Object.values(allocation).reduce((s, v) => s + v, 0);

  if (loading) {
    return (
      <Card padding="lg">
        <div className="flex justify-center py-8"><Loader2 className="animate-spin text-stone-300" size={24} /></div>
      </Card>
    );
  }

  return (
    <Card padding="lg">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-stone-800">Target Allocation</h3>
        <button
          onClick={() => window.dispatchEvent(new CustomEvent("ask-henry", { detail: { message: "What asset allocation is best for my risk tolerance and income level as a HENRY?" } }))}
          className="flex items-center gap-1.5 text-xs text-[#16A34A] hover:text-[#15803D] transition-colors"
        >
          <MessageCircle size={12} />
          Ask <SirHenryName />
        </button>
      </div>

      {/* Presets */}
      {Object.keys(presets).length > 0 && (
        <div className="flex gap-2 mb-5">
          {Object.entries(presets).map(([key, preset]) => (
            <button
              key={key}
              onClick={() => applyPreset(key)}
              className={`text-xs px-3 py-1.5 rounded-lg border transition-colors ${
                name === preset.name
                  ? "border-[#16A34A] bg-green-50 text-[#16A34A]"
                  : "border-stone-200 text-stone-500 hover:border-stone-300"
              }`}
            >
              {preset.name}
            </button>
          ))}
        </div>
      )}

      {/* Sliders */}
      <div className="space-y-4">
        {Object.entries(allocation)
          .sort(([, a], [, b]) => b - a)
          .map(([key, value]) => (
            <div key={key}>
              <div className="flex items-center justify-between mb-1.5">
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded-sm" style={{ backgroundColor: COLORS[key] ?? "#64748b" }} />
                  <span className="text-sm text-stone-700">{LABELS[key] ?? key}</span>
                </div>
                <span className="text-sm font-semibold tabular-nums font-mono">{value}%</span>
              </div>
              <input
                type="range"
                min={0}
                max={100}
                value={value}
                onChange={(e) => handleSliderChange(key, parseInt(e.target.value))}
                className="w-full h-2 bg-stone-100 rounded-lg appearance-none cursor-pointer accent-[#16A34A]"
              />
            </div>
          ))}
      </div>

      {/* Total indicator */}
      <div className="flex items-center justify-between mt-4 pt-3 border-t border-stone-100">
        <span className="text-xs text-stone-400">Total</span>
        <span className={`text-sm font-semibold tabular-nums ${total === 100 ? "text-green-600" : "text-red-600"}`}>
          {total}%
        </span>
      </div>

      {/* Visual bar */}
      <div className="flex h-3 rounded-full overflow-hidden mt-3">
        {Object.entries(allocation)
          .filter(([, v]) => v > 0)
          .sort(([, a], [, b]) => b - a)
          .map(([key, value]) => (
            <div
              key={key}
              style={{ width: `${value}%`, backgroundColor: COLORS[key] ?? "#64748b" }}
              className="transition-all duration-200"
              title={`${LABELS[key] ?? key}: ${value}%`}
            />
          ))}
      </div>

      {error && <p className="text-xs text-red-600 mt-3">{error}</p>}

      <div className="flex items-center gap-3 mt-4">
        <button
          onClick={handleSave}
          disabled={saving || total !== 100}
          className="flex items-center gap-2 bg-[#16A34A] text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-[#15803D] disabled:opacity-60 shadow-sm"
        >
          {saving ? <Loader2 size={13} className="animate-spin" /> : saved ? <Check size={13} /> : null}
          {saved ? "Saved" : "Save Allocation"}
        </button>
        <button onClick={load} className="text-xs text-stone-400 hover:text-stone-600">Reset</button>
      </div>
    </Card>
  );
}
