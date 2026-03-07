import Skeleton from "./Skeleton";
import CardSkeleton from "./CardSkeleton";

/** Dashboard-specific skeleton: greeting + stat cards + chart + transactions. */
export default function DashboardSkeleton() {
  return (
    <div className="space-y-6">
      {/* Greeting header */}
      <div className="flex items-center justify-between">
        <div className="space-y-1.5">
          <Skeleton className="h-7 w-56" />
          <Skeleton className="h-4 w-36" />
        </div>
        <div className="flex gap-2">
          <Skeleton className="h-9 w-20 rounded-lg" />
          <Skeleton className="h-9 w-20 rounded-lg" />
        </div>
      </div>

      {/* Stat cards row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div
            key={i}
            className="bg-card rounded-xl border border-card-border shadow-sm p-4 space-y-2"
          >
            <Skeleton className="h-3 w-20" />
            <Skeleton className="h-7 w-28" />
            <Skeleton className="h-3 w-16" />
          </div>
        ))}
      </div>

      {/* Chart + sidebar */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Chart area */}
        <div className="lg:col-span-2 bg-card rounded-xl border border-card-border shadow-sm p-5 space-y-3">
          <Skeleton className="h-5 w-40" />
          <Skeleton className="h-48 w-full rounded-lg" />
        </div>
        {/* Side card */}
        <CardSkeleton lines={5} />
      </div>

      {/* Transaction rows */}
      <div className="bg-card rounded-xl border border-card-border shadow-sm p-5 space-y-3">
        <Skeleton className="h-5 w-40" />
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="flex items-center justify-between py-2">
            <div className="flex items-center gap-3">
              <Skeleton className="h-8 w-8 rounded-full" />
              <div className="space-y-1.5">
                <Skeleton className="h-4 w-32" />
                <Skeleton className="h-3 w-20" />
              </div>
            </div>
            <Skeleton className="h-4 w-16" />
          </div>
        ))}
      </div>
    </div>
  );
}
