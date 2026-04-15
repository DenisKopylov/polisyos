import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  type RefObject,
} from "react";

/**
 * Lightweight touch gesture detection without external dependencies.
 *
 * Detects:
 * - Swipe left/right (for tab navigation, drawer toggle)
 * - Swipe down (for pull-to-refresh)
 * - Long press (for context menus)
 *
 * For advanced gestures (pinch zoom on charts), @use-gesture/react
 * can be added as a dependency in a future iteration.
 */

type SwipeDirection = "down" | "left" | "right" | "up";

type TouchGestureHandlers = {
  onSwipe?: (direction: SwipeDirection) => void;
  onLongPress?: () => void;
};

type TouchGestureOptions = {
  /** Minimum distance (px) to trigger a swipe. */
  swipeThreshold?: number;
  /** Max time (ms) for a swipe gesture. */
  swipeTimeLimit?: number;
  /** Duration (ms) for a long press. */
  longPressDelay?: number;
};

const DEFAULT_OPTIONS: Required<TouchGestureOptions> = {
  swipeThreshold: 50,
  swipeTimeLimit: 300,
  longPressDelay: 500,
};

/**
 * Attach swipe and long-press gesture detection to a ref'd element.
 *
 * ```tsx
 * const gestureProps = useTouchGestures(containerRef, {
 *   onSwipe: (dir) => { if (dir === "left") goNext(); },
 *   onLongPress: () => openContextMenu(),
 * });
 * <div ref={containerRef} {...gestureProps} />
 * ```
 */
export function useTouchGestures(
  ref: RefObject<HTMLElement | null>,
  handlers: TouchGestureHandlers,
  options?: TouchGestureOptions,
) {
  const opts = useMemo(
    () => ({ ...DEFAULT_OPTIONS, ...options }),
    [options],
  );
  const touchStartRef = useRef<{
    startTime: number;
    startX: number;
    startY: number;
  } | null>(null);
  const longPressTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const handlersRef = useRef(handlers);

  useEffect(() => {
    handlersRef.current = handlers;
  }, [handlers]);

  const onTouchStart = useCallback(
    (e: React.TouchEvent) => {
      const touch = e.touches[0];
      if (!touch) return;

      touchStartRef.current = {
        startTime: Date.now(),
        startX: touch.clientX,
        startY: touch.clientY,
      };

      // Start long press timer
      if (handlersRef.current.onLongPress) {
        longPressTimerRef.current = setTimeout(() => {
          handlersRef.current.onLongPress?.();
          touchStartRef.current = null; // Cancel swipe
        }, opts.longPressDelay);
      }
    },
    [opts.longPressDelay],
  );

  const onTouchMove = useCallback(() => {
    // Cancel long press on move
    if (longPressTimerRef.current) {
      clearTimeout(longPressTimerRef.current);
      longPressTimerRef.current = null;
    }
  }, []);

  const onTouchEnd = useCallback(
    (e: React.TouchEvent) => {
      // Cancel long press timer
      if (longPressTimerRef.current) {
        clearTimeout(longPressTimerRef.current);
        longPressTimerRef.current = null;
      }

      const start = touchStartRef.current;
      if (!start) return;
      touchStartRef.current = null;

      const touch = e.changedTouches[0];
      if (!touch) return;

      const elapsed = Date.now() - start.startTime;
      if (elapsed > opts.swipeTimeLimit) return;

      const dx = touch.clientX - start.startX;
      const dy = touch.clientY - start.startY;
      const absDx = Math.abs(dx);
      const absDy = Math.abs(dy);

      if (absDx < opts.swipeThreshold && absDy < opts.swipeThreshold) return;

      let direction: SwipeDirection;
      if (absDx > absDy) {
        direction = dx > 0 ? "right" : "left";
      } else {
        direction = dy > 0 ? "down" : "up";
      }

      handlersRef.current.onSwipe?.(direction);
    },
    [opts.swipeThreshold, opts.swipeTimeLimit],
  );

  return { onTouchEnd, onTouchMove, onTouchStart };
}
