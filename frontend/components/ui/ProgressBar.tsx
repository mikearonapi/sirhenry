interface ProgressBarProps {
  value: number;
  max?: number;
  color?: string;
  size?: "xs" | "sm" | "md";
  showOverflow?: boolean;
}

export default function ProgressBar({
  value,
  max = 100,
  color,
  size = "sm",
  showOverflow = false,
}: ProgressBarProps) {
  const pct = max > 0 ? (value / max) * 100 : 0;
  const isOver = pct > 100;
  const barColor = color ?? (isOver ? "#dc2626" : pct > 80 ? "#f59e0b" : "#16a34a");

  const heights = { xs: "h-1", sm: "h-2", md: "h-3" };

  return (
    <div className={`w-full bg-stone-100 rounded-full ${heights[size]} overflow-hidden`}>
      <div
        className={`${heights[size]} rounded-full transition-all duration-500`}
        style={{
          width: `${showOverflow ? Math.min(100, pct) : Math.min(100, pct)}%`,
          backgroundColor: barColor,
        }}
      />
    </div>
  );
}
