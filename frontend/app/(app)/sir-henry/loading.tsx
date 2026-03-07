import Skeleton from "@/components/ui/Skeleton";

export default function Loading() {
  return (
    <div className="flex flex-col h-[calc(100vh-2rem)] max-w-3xl mx-auto px-4 pt-6">
      {/* Chat header */}
      <div className="flex items-center gap-3 pb-4 border-b border-card-border">
        <Skeleton className="h-10 w-10 rounded-full" />
        <div className="space-y-1.5">
          <Skeleton className="h-5 w-32" />
          <Skeleton className="h-3 w-48" />
        </div>
      </div>
      {/* Empty message area */}
      <div className="flex-1" />
      {/* Input bar */}
      <div className="pb-4 pt-3">
        <Skeleton className="h-12 w-full rounded-xl" />
      </div>
    </div>
  );
}
