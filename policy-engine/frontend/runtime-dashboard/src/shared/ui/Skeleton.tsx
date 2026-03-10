import { cn } from "@/lib/utils";

export function SkeletonBlock({ className }: { className?: string }) {
  return (
    <div
      className={cn("bg-line/80 animate-pulse rounded-2xl", className)}
      aria-hidden="true"
    />
  );
}

export function PageSkeleton() {
  return (
    <div className="space-y-5" data-testid="page-skeleton">
      <SkeletonBlock className="h-36 w-full rounded-[28px]" />
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
        <SkeletonBlock className="h-72 w-full" />
        <div className="space-y-4">
          <SkeletonBlock className="h-32 w-full" />
          <SkeletonBlock className="h-32 w-full" />
        </div>
      </div>
    </div>
  );
}

export function PanelSkeleton({
  rows = 4,
  className,
}: {
  rows?: number;
  className?: string;
}) {
  return (
    <div
      className={cn("rounded-3xl border border-line bg-panel p-5", className)}
    >
      <SkeletonBlock className="h-5 w-40" />
      <SkeletonBlock className="mt-3 h-4 w-72" />
      <div className="mt-5 space-y-3">
        {Array.from({ length: rows }, (_, index) => (
          <SkeletonBlock key={index} className="h-12 w-full" />
        ))}
      </div>
    </div>
  );
}

export function MetricsSkeleton({ count = 4 }: { count?: number }) {
  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
      {Array.from({ length: count }, (_, index) => (
        <div
          key={index}
          className="rounded-2xl border border-line bg-panel p-4"
        >
          <SkeletonBlock className="h-4 w-24" />
          <SkeletonBlock className="mt-3 h-8 w-20" />
          <SkeletonBlock className="mt-3 h-4 w-32" />
        </div>
      ))}
    </div>
  );
}
