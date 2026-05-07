import type { FocusEvent, MouseEvent, TouchEvent } from "react";
import { forwardRef, useCallback, useEffect, useMemo, useRef } from "react";
import { createPath, Link, type LinkProps, type To } from "react-router-dom";

import {
  isConstrainedNetwork,
  readNetworkStatusSnapshot,
  shouldSkipViewportPrefetch,
  useMaybeNetworkStatus,
} from "@/shared/network";
import { prefetchRouteHref } from "@/app/routes/prefetch";

export type PrefetchMode = "none" | "intent" | "viewport";

const PREFETCH_TTL_MS = 60_000;
const MAX_PREFETCH_HISTORY = 500;
const prefetchHistory = new Map<string, number>();

function prunePrefetchHistory(now: number) {
  for (const [key, timestamp] of prefetchHistory.entries()) {
    if (now - timestamp >= PREFETCH_TTL_MS) {
      prefetchHistory.delete(key);
    }
  }

  if (prefetchHistory.size <= MAX_PREFETCH_HISTORY) {
    return;
  }

  const overflow = prefetchHistory.size - MAX_PREFETCH_HISTORY;
  const oldestEntries = [...prefetchHistory.entries()]
    .sort((left, right) => left[1] - right[1])
    .slice(0, overflow);

  oldestEntries.forEach(([key]) => {
    prefetchHistory.delete(key);
  });
}

function shouldSkipPrefetch(
  href: string,
  mode: PrefetchMode,
  networkStatus: ReturnType<typeof readNetworkStatusSnapshot> & {
    constrained: boolean;
  },
) {
  if (mode === "none" || href.startsWith("http")) {
    return true;
  }

  if (!networkStatus.online) {
    return true;
  }

  if (mode === "viewport" && shouldSkipViewportPrefetch(networkStatus)) {
    return true;
  }

  const now = Date.now();
  prunePrefetchHistory(now);
  const previousPrefetchAt = prefetchHistory.get(`${mode}:${href}`);
  return (
    typeof previousPrefetchAt === "number" &&
    now - previousPrefetchAt < PREFETCH_TTL_MS
  );
}

function schedulePrefetch(load: () => void) {
  if (typeof window !== "undefined" && "requestIdleCallback" in window) {
    window.requestIdleCallback(load, { timeout: 500 });
    return;
  }

  globalThis.setTimeout(load, 0);
}

export function useRoutePrefetch(to: To, prefetch: PrefetchMode = "none") {
  const networkStatusContext = useMaybeNetworkStatus();
  const networkStatus =
    networkStatusContext ??
    (() => {
      const snapshot = readNetworkStatusSnapshot();
      return {
        ...snapshot,
        constrained: isConstrainedNetwork(snapshot),
      };
    })();
  const linkRef = useRef<HTMLAnchorElement | null>(null);
  const resolvedHref = useMemo(
    () => (typeof to === "string" ? to : createPath(to)),
    [to],
  );

  const triggerPrefetch = useCallback(() => {
    if (shouldSkipPrefetch(resolvedHref, prefetch, networkStatus)) {
      return;
    }

    const now = Date.now();
    prunePrefetchHistory(now);
    prefetchHistory.set(`${prefetch}:${resolvedHref}`, now);
    schedulePrefetch(() => {
      void prefetchRouteHref(resolvedHref).catch(() => undefined);
    });
  }, [networkStatus, prefetch, resolvedHref]);

  useEffect(() => {
    if (prefetch !== "viewport" || !linkRef.current) {
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        if (!entries.some((entry) => entry.isIntersecting)) {
          return;
        }
        triggerPrefetch();
        observer.disconnect();
      },
      { rootMargin: "180px" },
    );

    observer.observe(linkRef.current);
    return () => observer.disconnect();
  }, [prefetch, resolvedHref, triggerPrefetch]);

  return {
    linkRef,
    onFocus: (event: FocusEvent<HTMLAnchorElement>) => {
      if (prefetch === "intent") {
        triggerPrefetch();
      }
      return event;
    },
    onMouseEnter: (event: MouseEvent<HTMLAnchorElement>) => {
      if (prefetch === "intent") {
        triggerPrefetch();
      }
      return event;
    },
    onTouchStart: (event: TouchEvent<HTMLAnchorElement>) => {
      if (prefetch === "intent") {
        triggerPrefetch();
      }
      return event;
    },
    prefetchNow: triggerPrefetch,
  };
}

type PrefetchLinkProps = Omit<LinkProps, "prefetch"> & {
  prefetch?: PrefetchMode;
};

export const PrefetchLink = forwardRef<HTMLAnchorElement, PrefetchLinkProps>(
  function PrefetchLink(
    {
      onFocus,
      onMouseEnter,
      onTouchStart,
      prefetch = "none",
      to,
      ...linkProps
    },
    forwardedRef,
  ) {
    const {
      linkRef,
      onFocus: handleFocus,
      onMouseEnter: handleMouseEnter,
      onTouchStart: handleTouchStart,
    } = useRoutePrefetch(to, prefetch);

    return (
      <Link
        {...linkProps}
        to={to}
        ref={(node) => {
          linkRef.current = node;
          if (typeof forwardedRef === "function") {
            forwardedRef(node);
            return;
          }
          if (forwardedRef) {
            forwardedRef.current = node;
          }
        }}
        onFocus={(event) => {
          handleFocus(event);
          onFocus?.(event);
        }}
        onMouseEnter={(event) => {
          handleMouseEnter(event);
          onMouseEnter?.(event);
        }}
        onTouchStart={(event) => {
          handleTouchStart(event);
          onTouchStart?.(event);
        }}
      />
    );
  },
);
