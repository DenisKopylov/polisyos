import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
  type RefObject,
} from "react";

type Orientation = "horizontal" | "vertical" | "both";

export type UseRovingTabIndexOptions = {
  loop?: boolean;
  orientation?: Orientation;
  size: number;
};

export type UseRovingTabIndexReturn = {
  activeIndex: number;
  containerRef: RefObject<HTMLElement | null>;
  getTabIndex: (index: number) => 0 | -1;
  handleKeyDown: (event: ReactKeyboardEvent<HTMLElement>) => void;
  setActiveIndex: (index: number) => void;
};

const ROVING_ITEM_SELECTOR = "[data-roving-item]";

export function useRovingTabIndex(
  options: UseRovingTabIndexOptions,
): UseRovingTabIndexReturn {
  const { size, orientation = "vertical", loop = true } = options;
  const [activeIndex, setActiveIndexState] = useState(0);
  const containerRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    setActiveIndexState((current) => {
      if (size <= 0) {
        return 0;
      }
      return Math.min(current, size - 1);
    });
  }, [size]);

  const focusItem = useCallback(
    (index: number) => {
      const container = containerRef.current;
      if (!container || size <= 0) {
        setActiveIndexState(0);
        return;
      }

      const nextIndex = Math.max(0, Math.min(index, size - 1));
      const items = Array.from(
        container.querySelectorAll<HTMLElement>(ROVING_ITEM_SELECTOR),
      );
      items[nextIndex]?.focus();
      setActiveIndexState(nextIndex);
    },
    [size],
  );

  const moveTo = useCallback(
    (delta: number) => {
      if (size <= 0) {
        return;
      }

      let nextIndex = activeIndex + delta;
      if (loop) {
        nextIndex = ((nextIndex % size) + size) % size;
      } else {
        nextIndex = Math.max(0, Math.min(nextIndex, size - 1));
      }

      focusItem(nextIndex);
    },
    [activeIndex, focusItem, loop, size],
  );

  const handleKeyDown = useCallback(
    (event: ReactKeyboardEvent<HTMLElement>) => {
      const allowsVertical =
        orientation === "vertical" || orientation === "both";
      const allowsHorizontal =
        orientation === "horizontal" || orientation === "both";

      switch (event.key) {
        case "ArrowDown":
          if (allowsVertical) {
            event.preventDefault();
            moveTo(1);
          }
          break;
        case "ArrowUp":
          if (allowsVertical) {
            event.preventDefault();
            moveTo(-1);
          }
          break;
        case "ArrowRight":
          if (allowsHorizontal) {
            event.preventDefault();
            moveTo(1);
          }
          break;
        case "ArrowLeft":
          if (allowsHorizontal) {
            event.preventDefault();
            moveTo(-1);
          }
          break;
        case "Home":
          event.preventDefault();
          focusItem(0);
          break;
        case "End":
          event.preventDefault();
          focusItem(Math.max(0, size - 1));
          break;
      }
    },
    [focusItem, moveTo, orientation, size],
  );

  const getTabIndex = useCallback(
    (index: number): 0 | -1 => (index === activeIndex ? 0 : -1),
    [activeIndex],
  );

  return {
    activeIndex,
    containerRef,
    getTabIndex,
    handleKeyDown,
    setActiveIndex: focusItem,
  };
}
