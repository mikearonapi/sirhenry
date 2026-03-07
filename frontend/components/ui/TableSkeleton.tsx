import Skeleton from "./Skeleton";

interface TableSkeletonProps {
  /** Number of body rows (default 6) */
  rows?: number;
  /** Number of columns (default 4) */
  cols?: number;
  className?: string;
}

/** Skeleton matching a data table with header row + body rows. */
export default function TableSkeleton({
  rows = 6,
  cols = 4,
  className = "",
}: TableSkeletonProps) {
  return (
    <div
      className={`bg-card rounded-xl border border-card-border shadow-sm overflow-hidden ${className}`}
    >
      {/* Header */}
      <div className="flex gap-4 px-5 py-3 border-b border-card-border">
        {Array.from({ length: cols }).map((_, i) => (
          <Skeleton
            key={i}
            className={`h-4 ${i === 0 ? "w-40" : "w-20"}`}
          />
        ))}
      </div>
      {/* Rows */}
      {Array.from({ length: rows }).map((_, r) => (
        <div
          key={r}
          className="flex gap-4 px-5 py-3 border-b border-border-light last:border-0"
        >
          {Array.from({ length: cols }).map((_, c) => (
            <Skeleton
              key={c}
              className={`h-4 ${c === 0 ? "w-40" : "w-20"}`}
            />
          ))}
        </div>
      ))}
    </div>
  );
}
