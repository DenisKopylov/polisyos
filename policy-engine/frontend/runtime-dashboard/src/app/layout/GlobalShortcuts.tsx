import { useCallback, useState } from "react";
import { useNavigate } from "react-router-dom";

import { useOptionalI18n } from "@/shared/i18n/LocaleProvider";
import { useDensity } from "@/app/providers/DensityProvider";
import { useTheme } from "@/app/providers/ThemeProvider";
import {
  useKeyboardShortcuts,
  type ShortcutEntry,
} from "@/shared/lib/hooks/useKeyboardShortcuts";
import { usePreferencesStore } from "@/app/state/usePreferencesStore";

// ---------------------------------------------------------------------------
// Shortcuts help overlay
// ---------------------------------------------------------------------------

function ShortcutsHelp({
  closeLabel,
  dialogLabel,
  open,
  onClose,
  shortcuts,
  title,
}: {
  closeLabel: string;
  dialogLabel: string;
  open: boolean;
  onClose: () => void;
  shortcuts: ShortcutEntry[];
  title: string;
}) {
  if (!open) return null;

  const grouped = new Map<string, ShortcutEntry[]>();
  for (const s of shortcuts) {
    const group = s.group ?? "Other";
    if (!grouped.has(group)) grouped.set(group, []);
    grouped.get(group)!.push(s);
  }

  return (
    <>
      <div
        className="fixed inset-0 z-[var(--z-overlay)] bg-black/40"
        onClick={onClose}
        aria-hidden
      />
      <div
        role="dialog"
        aria-label={dialogLabel}
        className="bg-paper border-line fixed top-1/2 left-1/2 z-[var(--z-modal)] w-full max-w-md -translate-x-1/2 -translate-y-1/2 rounded-2xl border p-6 shadow-xl"
      >
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold">{title}</h2>
          <button
            type="button"
            onClick={onClose}
            className="text-muted hover:text-foreground focus-visible:outline-accent/45 rounded-md focus-visible:outline-2 focus-visible:outline-offset-2"
            aria-label={closeLabel}
          >
            ×
          </button>
        </div>

        <div className="space-y-5">
          {[...grouped.entries()].map(([group, entries]) => (
            <div key={group}>
              <p className="text-muted mb-2 text-xs font-semibold tracking-wider uppercase">
                {group}
              </p>
              <div className="space-y-1.5">
                {entries.map((s) => (
                  <div
                    key={s.id}
                    className="flex items-center justify-between text-sm"
                  >
                    <span>{s.label}</span>
                    <kbd className="bg-surface border-line rounded-md border px-2 py-0.5 font-mono text-xs">
                      {formatCombo(s.combo)}
                    </kbd>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </>
  );
}

function formatCombo(combo: ShortcutEntry["combo"]) {
  const parts: string[] = [];
  const isMac =
    typeof navigator !== "undefined" &&
    /Mac|iPod|iPhone|iPad/.test(navigator.userAgent);
  if (combo.meta) parts.push(isMac ? "⌘" : "Ctrl");
  if (combo.ctrl) parts.push("Ctrl");
  if (combo.shift) parts.push("⇧");
  if (combo.alt) parts.push(isMac ? "⌥" : "Alt");
  parts.push(combo.key.length === 1 ? combo.key.toUpperCase() : combo.key);
  return parts.join(isMac ? "" : "+");
}

// ---------------------------------------------------------------------------
// Global shortcuts provider
// ---------------------------------------------------------------------------

export function GlobalShortcuts() {
  const navigate = useNavigate();
  const toggleSidebar = usePreferencesStore((s) => s.toggleSidebar);
  const { cycleDensity } = useDensity();
  const { t } = useOptionalI18n();
  const { toggleTheme } = useTheme();
  const [helpOpen, setHelpOpen] = useState(false);

  const shortcuts: ShortcutEntry[] = [
    // Navigation: Cmd+1 through Cmd+6
    {
      id: "nav.commandCenter",
      combo: { key: "1", meta: true },
      label: "Command Center",
      group: "Navigation",
      handler: useCallback(() => {
        void navigate("/");
      }, [navigate]),
    },
    {
      id: "nav.composer",
      combo: { key: "2", meta: true },
      label: "Scenario Composer",
      group: "Navigation",
      handler: useCallback(() => {
        void navigate("/compose");
      }, [navigate]),
    },
    {
      id: "nav.runs",
      combo: { key: "3", meta: true },
      label: "Runs & Decisions",
      group: "Navigation",
      handler: useCallback(() => {
        void navigate("/runs");
      }, [navigate]),
    },
    {
      id: "nav.evidence",
      combo: { key: "4", meta: true },
      label: "Evidence Fabric",
      group: "Navigation",
      handler: useCallback(() => {
        void navigate("/evidence");
      }, [navigate]),
    },
    {
      id: "nav.lex",
      combo: { key: "5", meta: true },
      label: "Lex & Knowledge",
      group: "Navigation",
      handler: useCallback(() => {
        void navigate("/knowledge");
      }, [navigate]),
    },
    {
      id: "nav.platform",
      combo: { key: "6", meta: true },
      label: "Platform Health",
      group: "Navigation",
      handler: useCallback(() => {
        void navigate("/platform");
      }, [navigate]),
    },
    // General
    {
      id: "general.toggleSidebar",
      combo: { key: "b", meta: true },
      label: "Toggle sidebar",
      group: "General",
      handler: useCallback(() => toggleSidebar(), [toggleSidebar]),
    },
    {
      id: "general.newRun",
      combo: { key: "n", meta: true },
      label: "New scenario",
      group: "General",
      handler: useCallback(() => {
        void navigate("/compose");
      }, [navigate]),
    },
    {
      id: "general.help",
      combo: { key: "?" },
      label: "Show keyboard shortcuts",
      group: "General",
      handler: useCallback(() => setHelpOpen(true), []),
    },
    {
      id: "appearance.toggleTheme",
      combo: { key: "l", meta: true, shift: true },
      label: "Theme: toggle light/dark",
      group: "Appearance",
      handler: useCallback(() => toggleTheme(), [toggleTheme]),
    },
    {
      id: "appearance.cycleDensity",
      combo: { key: "d", meta: true, shift: true },
      label: "Density: cycle comfortable/compact/condensed",
      group: "Appearance",
      handler: useCallback(() => cycleDensity(), [cycleDensity]),
    },
    // Vim-style list navigation
    {
      id: "vim.next",
      combo: { key: "j" },
      label: "Next item",
      group: "Vim Navigation",
      handler: useCallback(() => {
        const focused = document.activeElement;
        const container =
          focused?.closest("[data-vim-list]") ??
          document.querySelector("[data-vim-list]");
        if (!container) return;

        const items = Array.from(
          container.querySelectorAll<HTMLElement>("[data-vim-item]"),
        );
        if (items.length === 0) return;

        const idx =
          focused instanceof HTMLElement ? items.indexOf(focused) : -1;
        const next = items[Math.min(idx + 1, items.length - 1)];
        next?.focus();
      }, []),
    },
    {
      id: "vim.prev",
      combo: { key: "k" },
      label: "Previous item",
      group: "Vim Navigation",
      handler: useCallback(() => {
        const focused = document.activeElement;
        const container =
          focused?.closest("[data-vim-list]") ??
          document.querySelector("[data-vim-list]");
        if (!container) return;

        const items = Array.from(
          container.querySelectorAll<HTMLElement>("[data-vim-item]"),
        );
        if (items.length === 0) return;

        const idx =
          focused instanceof HTMLElement ? items.indexOf(focused) : -1;
        const prev = items[Math.max(idx - 1, 0)];
        prev?.focus();
      }, []),
    },
  ];

  useKeyboardShortcuts(shortcuts);

  return (
    <ShortcutsHelp
      closeLabel={t("common.close")}
      dialogLabel={t("shell.shortcuts.dialogLabel")}
      open={helpOpen}
      onClose={() => setHelpOpen(false)}
      shortcuts={shortcuts}
      title={t("shell.shortcuts.title")}
    />
  );
}
