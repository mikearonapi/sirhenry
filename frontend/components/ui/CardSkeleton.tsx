import Skeleton, { SkeletonText } from "./Skeleton";

interface CardSkeletonProps {
  /** Number of text lines in the body (default 3) */
  lines?: number;
  /** Show a header bar */
  header?: boolean;
  className?: string;
}

/** Skeleton matching the Card component (white rounded-xl border). */
export default function CardSkeleton({
  lines = 3,
  header = true,
  className = "",
}: CardSkeletonProps) {
  return (
    <div
      className={`bg-card rounded-xl border border-card-border shadow-sm p-5 space-y-3 ${className}`}
    >
      {header && <Skeleton className="h-5 w-32" />}
      {Array.from({ length: lines }).map((_, i) => (
        <SkeletonText key={i} width={i === lines - 1 ? "w-2/3" : "w-full"} />
      ))}
    </div>
  );
}
