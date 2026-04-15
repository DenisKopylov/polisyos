import { useCallback, useEffect, useRef } from "react";

export type KeyCombo = {
  key: string;
  meta?: boolean;
  ctrl?: boolean;
  shift?: boolean;
  alt?: boolean;
};

export type ShortcutEntry = {
  id: string;
  combo: KeyCombo;
  label: string;
  group?: string;
  handler: () => void;
  enabled?: boolean;
};

function isInputElement(target: EventTarget | null): boolean {
  if (!target || !(target instanceof HTMLElement)) return false;
  const tag = target.tagName;
  return (
    tag === "INPUT" ||
    tag === "TEXTAREA" ||
    tag === "SELECT" ||
    target.isContentEditable
  );
}

function matchesCombo(e: KeyboardEvent, combo: KeyCombo): boolean {
  const wantsMeta = combo.meta ?? false;
  const wantsCtrl = combo.ctrl ?? false;
  const wantsShift = combo.shift ?? false;
  const wantsAlt = combo.alt ?? false;

  // For non-alphanumeric single characters (e.g. "?", "!", "@") the Shift key
  // is needed just to produce the character on most layouts. Ignore the
  // shiftKey modifier check so these combos fire regardless of layout.
  const isCharacterKey =
    combo.key.length === 1 && !/^[a-z0-9]$/i.test(combo.key);
  const shiftMatches = isCharacterKey || e.shiftKey === wantsShift;

  return (
    e.key.toLowerCase() === combo.key.toLowerCase() &&
    e.metaKey === wantsMeta &&
    e.ctrlKey === wantsCtrl &&
    shiftMatches &&
    e.altKey === wantsAlt
  );
}

export function formatShortcut(combo: KeyCombo): string {
  const parts: string[] = [];
  const isMac = typeof navigator !== "undefined" && /mac/i.test(navigator.userAgent);

  if (combo.ctrl) parts.push(isMac ? "^" : "Ctrl");
  if (combo.alt) parts.push(isMac ? "\u2325" : "Alt");
  if (combo.shift) parts.push(isMac ? "\u21E7" : "Shift");
  if (combo.meta) parts.push(isMac ? "\u2318" : "Ctrl");

  const keyLabel = combo.key.length === 1 ? combo.key.toUpperCase() : combo.key;
  parts.push(keyLabel);

  return parts.join(isMac ? "" : "+");
}

type ShortcutRegistryEntry = Omit<ShortcutEntry, "handler"> & {
  handler: { current: () => void };
};

const globalRegistry = new Map<string, ShortcutRegistryEntry>();
const listeners = new Set<() => void>();

function notifyListeners() {
  for (const fn of listeners) fn();
}

export function getRegisteredShortcuts(): ShortcutEntry[] {
  return Array.from(globalRegistry.values()).map((entry) => ({
    ...entry,
    handler: entry.handler.current,
  }));
}

export function subscribeShortcuts(fn: () => void): () => void {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

export function useKeyboardShortcuts(shortcuts: ShortcutEntry[]) {
  const shortcutsRef = useRef(shortcuts);
  const handlersByIdRef = useRef(new Map<string, () => void>());
  const registrationsSignature = shortcuts
    .map(
      (shortcut) =>
        [
          shortcut.id,
          shortcut.label,
          shortcut.group ?? "",
          shortcut.enabled === false ? "disabled" : "enabled",
          shortcut.combo.key,
          shortcut.combo.meta ? "meta" : "",
          shortcut.combo.ctrl ? "ctrl" : "",
          shortcut.combo.shift ? "shift" : "",
          shortcut.combo.alt ? "alt" : "",
        ].join(":"),
    )
    .join("|");

  useEffect(() => {
    shortcutsRef.current = shortcuts;
    handlersByIdRef.current = new Map(
      shortcuts.map((shortcut) => [shortcut.id, shortcut.handler]),
    );
  }, [shortcuts]);

  const invokeShortcutById = useCallback((shortcutId: string) => {
    handlersByIdRef.current.get(shortcutId)?.();
  }, []);

  useEffect(() => {
    const registrations: string[] = [];

    shortcuts.forEach((s) => {
      const entry: ShortcutRegistryEntry = {
        id: s.id,
        combo: s.combo,
        label: s.label,
        group: s.group,
        enabled: s.enabled !== false,
        handler: { current: () => invokeShortcutById(s.id) },
      };
      globalRegistry.set(s.id, entry);
      registrations.push(s.id);
    });

    notifyListeners();

    return () => {
      for (const id of registrations) globalRegistry.delete(id);
      notifyListeners();
    };
  }, [invokeShortcutById, registrationsSignature, shortcuts]);

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      for (const shortcut of shortcutsRef.current) {
        if (shortcut.enabled === false) {
          continue;
        }

        if (!matchesCombo(e, shortcut.combo)) {
          continue;
        }

        if (
          shortcut.combo.meta ||
          shortcut.combo.ctrl ||
          !isInputElement(e.target)
        ) {
          e.preventDefault();
          e.stopPropagation();
          invokeShortcutById(shortcut.id);
          return;
        }
      }
    };

    window.addEventListener("keydown", onKeyDown, true);
    return () => window.removeEventListener("keydown", onKeyDown, true);
  }, [invokeShortcutById]);
}

export function useGlobalShortcut(
  id: string,
  combo: KeyCombo,
  label: string,
  handler: () => void,
  options?: { group?: string; enabled?: boolean },
) {
  const handlerRef = useRef(handler);

  useEffect(() => {
    handlerRef.current = handler;
  }, [handler]);

  const stableHandler = useCallback(() => {
    handlerRef.current();
  }, []);

  const shortcut: ShortcutEntry = {
    id,
    combo,
    label,
    group: options?.group,
    handler: stableHandler,
    enabled: options?.enabled !== false,
  };

  useKeyboardShortcuts([shortcut]);
}
