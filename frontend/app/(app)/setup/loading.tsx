import Skeleton from "@/components/ui/Skeleton";

export default function Loading() {
  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <Skeleton className="h-7 w-48" />
      <Skeleton className="h-2 w-full rounded-full" />
      <div className="bg-card rounded-xl border border-card-border shadow-sm p-6 space-y-4">
        <Skeleton className="h-5 w-40" />
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-3/4" />
        <Skeleton className="h-10 w-full rounded-lg" />
        <Skeleton className="h-10 w-full rounded-lg" />
      </div>
    </div>
  );
}
