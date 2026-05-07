import { useEffect, useState, type RefObject } from "react";

import { READING_VIEW_MARGIN_BREAKPOINT } from "@/features/artifacts/reading-view/reading-view-tokens";
import { useBreakpoint } from "@/shared/ui/responsive";

export function useMarginNoteAnchors(rootRef: RefObject<HTMLElement | null>) {
  const breakpoint = useBreakpoint();
  const [positions, setPositions] = useState<Record<string, number>>({});
  const [isInline, setIsInline] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    const root = rootRef.current;
    const inline =
      breakpoint !== "expanded" ||
      window.innerWidth < READING_VIEW_MARGIN_BREAKPOINT;
    setIsInline(inline);

    if (!root || inline) {
      setPositions({});
      return;
    }

    const measure = () => {
      const rootRect = root.getBoundingClientRect();
      const next: Record<string, number> = {};

      for (const anchor of root.querySelectorAll<HTMLElement>(
        "[data-margin-anchor]",
      )) {
        const id = anchor.dataset.marginAnchor;
        if (!id) {
          continue;
        }
        next[id] = Math.max(
          0,
          anchor.getBoundingClientRect().top - rootRect.top,
        );
      }

      setPositions(next);
    };

    measure();
    const resizeObserver =
      typeof ResizeObserver !== "undefined"
        ? new ResizeObserver(measure)
        : null;
    resizeObserver?.observe(root);
    window.addEventListener("resize", measure);

    return () => {
      resizeObserver?.disconnect();
      window.removeEventListener("resize", measure);
    };
  }, [breakpoint, rootRef]);

  return { positions, isInline };
}
