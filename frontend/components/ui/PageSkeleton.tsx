import Skeleton from "./Skeleton";
import CardSkeleton from "./CardSkeleton";

interface PageSkeletonProps {
  /** Number of card skeletons to show (default 3) */
  cards?: number;
  /** Show stat cards row above the main cards */
  stats?: number;
  className?: string;
}

/** Standard page skeleton: heading + optional stat row + card grid. */
export default function PageSkeleton({
  cards = 3,
  stats = 0,
  className = "",
}: PageSkeletonProps) {
  return (
    <div className={`space-y-6 ${className}`}>
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div className="space-y-1.5">
          <Skeleton className="h-7 w-48" />
          <Skeleton className="h-4 w-64" />
        </div>
        <Skeleton className="h-9 w-28 rounded-lg" />
      </div>

      {/* Stat cards row */}
      {stats > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {Array.from({ length: stats }).map((_, i) => (
            <div
              key={i}
              className="bg-card rounded-xl border border-card-border shadow-sm p-4 space-y-2"
            >
              <Skeleton className="h-3 w-16" />
              <Skeleton className="h-6 w-24" />
            </div>
          ))}
        </div>
      )}

      {/* Content cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {Array.from({ length: cards }).map((_, i) => (
          <CardSkeleton key={i} lines={i === 0 ? 4 : 3} />
        ))}
      </div>
    </div>
  );
}
