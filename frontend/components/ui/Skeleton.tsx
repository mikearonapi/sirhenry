/** Base skeleton shimmer block — pulse animation on stone-100/200. */
export default function Skeleton({
  className = "",
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={`animate-pulse rounded-lg bg-border/60 ${className}`}
      {...props}
    />
  );
}

/** Skeleton shaped like a line of text. */
export function SkeletonText({
  width = "w-full",
  className = "",
}: {
  width?: string;
  className?: string;
}) {
  return <Skeleton className={`h-4 ${width} ${className}`} />;
}

/** Skeleton shaped like a heading. */
export function SkeletonHeading({ className = "" }: { className?: string }) {
  return <Skeleton className={`h-7 w-48 ${className}`} />;
}
