import { useCallback, useRef, useState } from "react";

import { useI18n } from "@/i18n/LocaleProvider";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type PullToRefreshProps = {
  onRefresh: () => Promise<void>;
  threshold?: number;
  children: React.ReactNode;
  className?: string;
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function PullToRefresh({
  onRefresh,
  threshold = 80,
  children,
  className,
}: PullToRefreshProps) {
  const { t } = useI18n();
  const [pullDistance, setPullDistance] = useState(0);
  const [refreshing, setRefreshing] = useState(false);
  const startY = useRef<number | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const handleTouchStart = useCallback(
    (e: React.TouchEvent) => {
      if (refreshing) return;
      const el = containerRef.current;
      if (el && el.scrollTop === 0) {
        startY.current = e.touches[0].clientY;
      }
    },
    [refreshing],
  );

  const handleTouchMove = useCallback(
    (e: React.TouchEvent) => {
      if (startY.current == null || refreshing) return;
      const dy = e.touches[0].clientY - startY.current;
      if (dy > 0) {
        // Damped pull
        setPullDistance(Math.min(dy * 0.4, threshold * 1.5));
      }
    },
    [refreshing, threshold],
  );

  const handleTouchEnd = useCallback(async () => {
    if (startY.current == null) return;
    startY.current = null;

    if (pullDistance >= threshold && !refreshing) {
      setRefreshing(true);
      setPullDistance(threshold * 0.5);
      try {
        await onRefresh();
      } finally {
        setRefreshing(false);
        setPullDistance(0);
      }
    } else {
      setPullDistance(0);
    }
  }, [pullDistance, threshold, refreshing, onRefresh]);

  const isTriggered = pullDistance >= threshold;

  return (
    <div
      ref={containerRef}
      className={cn("relative overflow-y-auto", className)}
      onTouchStart={handleTouchStart}
      onTouchMove={handleTouchMove}
      onTouchEnd={handleTouchEnd}
    >
      {/* Pull indicator */}
      <div
        className="flex items-center justify-center overflow-hidden transition-[height] duration-200"
        style={{ height: pullDistance > 0 ? pullDistance : 0 }}
      >
        {refreshing ? (
          <div className="border-accent size-5 animate-spin rounded-full border-2 border-t-transparent" />
        ) : (
          <div
            className={cn(
              "text-muted text-xs transition-opacity",
              isTriggered ? "opacity-100" : "opacity-50",
            )}
          >
            {isTriggered
              ? t("common.releaseToRefresh")
              : t("common.pullToRefresh")}
          </div>
        )}
      </div>

      {children}
    </div>
  );
}
