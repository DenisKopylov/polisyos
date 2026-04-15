import { useCallback, useRef, useState, type RefObject } from "react";

type Orientation = "horizontal" | "vertical" | "both";

type UseRovingTabIndexOptions = {
  /** Number of items in the group. */
  size: number;
  /** Navigation orientation (default: "vertical"). */
  orientation?: Orientation;
  /** Whether the navigation wraps around (default: true). */
  loop?: boolean;
};

type UseRovingTabIndexReturn = {
  /** Ref to attach to the container element. */
  containerRef: RefObject<HTMLElement | null>;
  /** Currently active (roving) index. */
  activeIndex: number;
  /** Set active index programmatically. */
  setActiveIndex: (index: number) => void;
  /** Returns the tabIndex value for a given item index. */
  getTabIndex: (index: number) => 0 | -1;
  /** onKeyDown handler to attach to each item (or the container). */
  handleKeyDown: (e: React.KeyboardEvent) => void;
};

/**
 * Implements the WAI-ARIA roving tabindex pattern for keyboard-navigable groups
 * (tabs, toolbars, listboxes, etc.).
 *
 * Only the currently active item has `tabIndex={0}`; all others get `tabIndex={-1}`.
 * Arrow keys move focus between items; Home/End jump to first/last.
 */
export function useRovingTabIndex(
  options: UseRovingTabIndexOptions,
): UseRovingTabIndexReturn {
  const { size, orientation = "vertical", loop = true } = options;
  const [activeIndex, setActiveIndex] = useState(0);
  const containerRef = useRef<HTMLElement | null>(null);

  const focusItem = useCallback(
    (index: number) => {
      const container = containerRef.current;
      if (!container) return;

      const items = Array.from(
        container.querySelectorAll<HTMLElement>("[data-roving-item]"),
      );
      items[index]?.focus();
      setActiveIndex(index);
    },
    [],
  );

  const moveTo = useCallback(
    (delta: number) => {
      if (size === 0) return;
      let next = activeIndex + delta;
      if (loop) {
        next = ((next % size) + size) % size;
      } else {
        next = Math.max(0, Math.min(next, size - 1));
      }
      focusItem(next);
    },
    [activeIndex, size, loop, focusItem],
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      const isVertical = orientation === "vertical" || orientation === "both";
      const isHorizontal = orientation === "horizontal" || orientation === "both";

      switch (e.key) {
        case "ArrowDown":
          if (isVertical) {
            e.preventDefault();
            moveTo(1);
          }
          break;
        case "ArrowUp":
          if (isVertical) {
            e.preventDefault();
            moveTo(-1);
          }
          break;
        case "ArrowRight":
          if (isHorizontal) {
            e.preventDefault();
            moveTo(1);
          }
          break;
        case "ArrowLeft":
          if (isHorizontal) {
            e.preventDefault();
            moveTo(-1);
          }
          break;
        case "Home":
          e.preventDefault();
          focusItem(0);
          break;
        case "End":
          e.preventDefault();
          focusItem(size - 1);
          break;
      }
    },
    [orientation, moveTo, focusItem, size],
  );

  const getTabIndex = useCallback(
    (index: number): 0 | -1 => (index === activeIndex ? 0 : -1),
    [activeIndex],
  );

  return {
    containerRef,
    activeIndex,
    setActiveIndex: focusItem,
    getTabIndex,
    handleKeyDown,
  };
}
