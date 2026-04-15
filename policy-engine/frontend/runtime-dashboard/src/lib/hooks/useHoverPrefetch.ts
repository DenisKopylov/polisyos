import { useCallback, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { queryKeys } from "@/api/queryKeys";

type UseHoverPrefetchOptions = {
  /** Debounce delay before prefetching (ms). */
  delay?: number;
  /** Stale time for the prefetched data (ms). */
  staleTime?: number;
};

/**
 * Returns an onMouseEnter handler that prefetches run detail data
 * when the user hovers a run row in a list.
 *
 * ```tsx
 * const prefetchProps = useHoverPrefetch(run.id);
 * <tr {...prefetchProps}>...</tr>
 * ```
 */
export function useHoverPrefetch(
  runId: string | undefined,
  options?: UseHoverPrefetchOptions,
) {
  const queryClient = useQueryClient();
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const prefetchedRef = useRef<string | null>(null);
  const delay = options?.delay ?? 100;
  const staleTime = options?.staleTime ?? 30_000;

  const onMouseEnter = useCallback(() => {
    if (!runId || prefetchedRef.current === runId) return;

    timerRef.current = setTimeout(() => {
      prefetchedRef.current = runId;
      void queryClient.prefetchQuery({
        queryKey: queryKeys.run(runId),
        staleTime,
      });
      void queryClient.prefetchQuery({
        queryKey: queryKeys.runTimeline(runId),
        staleTime,
      });
    }, delay);
  }, [runId, queryClient, delay, staleTime]);

  const onMouseLeave = useCallback(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  return { onMouseEnter, onMouseLeave };
}
