import { Loader2 } from "lucide-react";

export default function CalcButton({ loading, onClick, label = "Calculate" }: {
  loading: boolean;
  onClick: () => void;
  label?: string;
}) {
  return (
    <button
      onClick={onClick}
      disabled={loading}
      className="bg-[#16A34A] text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-[#15803D] disabled:opacity-60"
    >
      {loading ? (
        <span className="flex items-center gap-2">
          <Loader2 size={14} className="animate-spin" /> Calculating...
        </span>
      ) : label}
    </button>
  );
}
