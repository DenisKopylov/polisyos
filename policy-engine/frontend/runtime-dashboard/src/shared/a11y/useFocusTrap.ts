import { useEffect, useRef, type RefObject } from "react";

const FOCUSABLE_SELECTOR = [
  'a[href]:not([tabindex="-1"])',
  'button:not([disabled]):not([tabindex="-1"])',
  'input:not([disabled]):not([type="hidden"]):not([tabindex="-1"])',
  'select:not([disabled]):not([tabindex="-1"])',
  'textarea:not([disabled]):not([tabindex="-1"])',
  '[contenteditable="true"]:not([tabindex="-1"])',
  '[tabindex]:not([tabindex="-1"])',
].join(", ");

export type UseFocusTrapOptions = {
  fallbackToContainer?: boolean;
  initialFocus?: RefObject<HTMLElement | null>;
  restoreFocus?: boolean;
};

function getFocusableElements(container: HTMLElement) {
  return Array.from(
    container.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR),
  ).filter((element) => {
    if (element.closest("[inert]")) {
      return false;
    }
    if (
      element.hasAttribute("hidden") ||
      element.getAttribute("aria-hidden") === "true"
    ) {
      return false;
    }
    return element.getClientRects().length > 0;
  });
}

export function useFocusTrap<T extends HTMLElement = HTMLElement>(
  active: boolean,
  options: UseFocusTrapOptions = {},
): RefObject<T | null> {
  const containerRef = useRef<T | null>(null);
  const previousFocusRef = useRef<HTMLElement | null>(null);
  const shouldFallbackToContainer = options.fallbackToContainer ?? true;
  const shouldRestoreFocus = options.restoreFocus ?? true;

  useEffect(() => {
    if (!active) {
      return;
    }

    const host = containerRef.current;
    if (!host) {
      return;
    }
    const focusHost: HTMLElement = host;

    previousFocusRef.current = document.activeElement as HTMLElement | null;

    const focusable = getFocusableElements(focusHost);
    const initialTarget = options.initialFocus?.current ?? focusable[0] ?? null;

    if (initialTarget) {
      initialTarget.focus();
    } else if (shouldFallbackToContainer) {
      if (!focusHost.hasAttribute("tabindex")) {
        focusHost.setAttribute("tabindex", "-1");
      }
      focusHost.focus();
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key !== "Tab") {
        return;
      }

      const available = getFocusableElements(focusHost);
      if (available.length === 0) {
        event.preventDefault();
        if (shouldFallbackToContainer) {
          focusHost.focus();
        }
        return;
      }

      const first = available[0];
      const last = available[available.length - 1];
      const activeElement = document.activeElement as HTMLElement | null;
      const focusOutsideTrap =
        !activeElement || !focusHost.contains(activeElement);

      if (event.shiftKey) {
        if (focusOutsideTrap || activeElement === first) {
          event.preventDefault();
          last.focus();
        }
        return;
      }

      if (focusOutsideTrap || activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }

    document.addEventListener("keydown", handleKeyDown, true);

    return () => {
      document.removeEventListener("keydown", handleKeyDown, true);

      if (!shouldRestoreFocus) {
        return;
      }

      const previousFocus = previousFocusRef.current;
      if (previousFocus && previousFocus.isConnected) {
        previousFocus.focus();
      }
    };
  }, [
    active,
    options.initialFocus,
    shouldFallbackToContainer,
    shouldRestoreFocus,
  ]);

  return containerRef;
}
