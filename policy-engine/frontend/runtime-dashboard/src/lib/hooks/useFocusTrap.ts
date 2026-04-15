import { useEffect, useRef, type RefObject } from "react";

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

/**
 * Traps keyboard focus within a container element while `active` is true.
 * Returns a ref to attach to the container.
 *
 * - On activation the first focusable child receives focus (or `initialFocus` if provided).
 * - Tab / Shift+Tab cycle within the container.
 * - On deactivation focus returns to the element that was focused before the trap activated.
 */
export function useFocusTrap<T extends HTMLElement = HTMLElement>(
  active: boolean,
  options?: { initialFocus?: RefObject<HTMLElement | null> },
): RefObject<T | null> {
  const containerRef = useRef<T | null>(null);
  const previousFocusRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!active) return;

    const container = containerRef.current;
    if (!container) return;

    previousFocusRef.current = document.activeElement as HTMLElement | null;

    // Focus initial element or first focusable child
    const initialTarget =
      options?.initialFocus?.current ??
      container.querySelector<HTMLElement>(FOCUSABLE);
    initialTarget?.focus();

    function handleKeyDown(e: KeyboardEvent) {
      if (e.key !== "Tab") return;

      const focusable = Array.from(
        container!.querySelectorAll<HTMLElement>(FOCUSABLE),
      );
      if (focusable.length === 0) {
        e.preventDefault();
        return;
      }

      const first = focusable[0];
      const last = focusable[focusable.length - 1];

      if (e.shiftKey) {
        if (document.activeElement === first) {
          e.preventDefault();
          last.focus();
        }
      } else {
        if (document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    }

    document.addEventListener("keydown", handleKeyDown, true);

    return () => {
      document.removeEventListener("keydown", handleKeyDown, true);
      previousFocusRef.current?.focus();
    };
  }, [active, options?.initialFocus]);

  return containerRef;
}
