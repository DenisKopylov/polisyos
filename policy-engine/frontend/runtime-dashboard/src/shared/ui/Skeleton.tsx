import type React from "react";

import { cn } from "@/lib/utils";

/* ── Base block ── */

export function SkeletonBlock({
  className,
  style,
}: {
  className?: string;
  style?: React.CSSProperties;
}) {
  return (
    <div
      className={cn("bg-muted/60 animate-pulse rounded-2xl", className)}
      aria-hidden="true"
      data-testid="skeleton-block"
      style={style}
    />
  );
}

/* ── Semantic variants ── */

export function SkeletonText({
  lines = 3,
  className,
}: {
  lines?: number;
  className?: string;
}) {
  return (
    <div
      className={cn("space-y-2", className)}
      aria-hidden="true"
      data-testid="skeleton-text"
    >
      {Array.from({ length: lines }, (_, i) => (
        <SkeletonBlock
          key={i}
          className={cn("h-4", i === lines - 1 ? "w-3/5" : "w-full")}
        />
      ))}
    </div>
  );
}

export function SkeletonChart({ className }: { className?: string }) {
  return (
    <div
      className={cn("border-border bg-card rounded-xl border p-4", className)}
      aria-hidden="true"
      data-testid="skeleton-chart"
    >
      <SkeletonBlock className="mb-3 h-4 w-32" />
      <div className="flex items-end gap-1.5 pt-2" style={{ height: 120 }}>
        {[40, 65, 55, 80, 70, 90, 50, 75, 85, 60].map((h, i) => (
          <SkeletonBlock
            key={i}
            className="flex-1 rounded-sm"
            style={{ height: `${h}%` }}
          />
        ))}
      </div>
    </div>
  );
}

export function SkeletonCard({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        "border-border bg-card rounded-[var(--radius-panel)] border p-5",
        className,
      )}
      aria-hidden="true"
      data-testid="skeleton-card"
    >
      <SkeletonBlock className="h-5 w-40" />
      <SkeletonBlock className="mt-3 h-4 w-72" />
      <div className="mt-5 space-y-3">
        <SkeletonBlock className="h-12 w-full" />
        <SkeletonBlock className="h-12 w-full" />
      </div>
    </div>
  );
}

export function SkeletonTable({
  rows = 5,
  cols = 4,
  className,
}: {
  rows?: number;
  cols?: number;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "border-border bg-card overflow-hidden rounded-xl border",
        className,
      )}
      aria-hidden="true"
      data-testid="skeleton-table"
    >
      <div className="border-border flex gap-3 border-b p-3">
        {Array.from({ length: cols }, (_, i) => (
          <SkeletonBlock key={i} className="h-4 flex-1" />
        ))}
      </div>
      {Array.from({ length: rows }, (_, r) => (
        <div
          key={r}
          className="border-border flex gap-3 border-b p-3 last:border-0"
        >
          {Array.from({ length: cols }, (_, c) => (
            <SkeletonBlock
              key={c}
              className={cn("h-4 flex-1", c === 0 && "w-2/3 flex-none")}
            />
          ))}
        </div>
      ))}
    </div>
  );
}

/* ── Legacy composites (backward-compatible) ── */

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
      className={cn("border-border bg-card rounded-3xl border p-5", className)}
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
          className="border-border bg-card rounded-2xl border p-4"
        >
          <SkeletonBlock className="h-4 w-24" />
          <SkeletonBlock className="mt-3 h-8 w-20" />
          <SkeletonBlock className="mt-3 h-4 w-32" />
        </div>
      ))}
    </div>
  );
}
