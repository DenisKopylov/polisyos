import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  LayoutDashboard,
  FlaskConical,
  ListChecks,
  Database,
  BookOpen,
  Activity,
  Sun,
  Minimize2,
  Maximize2,
  AlignJustify,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

import {
  CommandDialog,
  CommandInput,
  CommandList,
  CommandEmpty,
  CommandGroup,
  CommandItem,
  CommandSeparator,
  CommandShortcut,
} from "@/shared/ui/Command";
import { useTheme } from "@/app/providers/ThemeProvider";
import { useI18n } from "@/i18n/LocaleProvider";
import { useGlobalShortcut } from "@/lib/hooks";
import { WORKSPACE_ORDER, WORKSPACES, type WorkspaceKey } from "@/app/workspaces";
import { usePreferencesStore, type Density } from "@/app/state/usePreferencesStore";

const WORKSPACE_ICONS: Record<WorkspaceKey, LucideIcon> = {
  commandCenter: LayoutDashboard,
  scenarioComposer: FlaskConical,
  runsDecisions: ListChecks,
  evidenceFabric: Database,
  lexKnowledge: BookOpen,
  platformHealth: Activity,
};

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();
  const { t } = useI18n();
  const { toggleTheme } = useTheme();
  const setDensity = usePreferencesStore((s) => s.setDensity);
  const density = usePreferencesStore((s) => s.density);

  useGlobalShortcut(
    "command-palette",
    { key: "k", meta: true },
    "Open command palette",
    () => setOpen((o) => !o),
    { group: "Global" },
  );

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        setOpen(false);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open]);

  const runCommand = useCallback(
    (command: () => void) => {
      setOpen(false);
      command();
    },
    [],
  );

  const workspaceItems = useMemo(
    () =>
      WORKSPACE_ORDER.map((key) => {
        const ws = WORKSPACES[key];
        const Icon = WORKSPACE_ICONS[key];
        const navKey = `shell.nav.${key}` as const;
        return { key, path: ws.path, Icon, label: t(navKey) };
      }),
    [t],
  );

  const densityOptions: Array<{ value: Density; label: string; Icon: LucideIcon }> = [
    { value: "compact", label: "Compact", Icon: Minimize2 },
    { value: "comfortable", label: "Comfortable", Icon: AlignJustify },
    { value: "spacious", label: "Spacious", Icon: Maximize2 },
  ];

  return (
    <CommandDialog open={open} onOpenChange={setOpen}>
      <CommandInput placeholder={t("commandPalette.placeholder")} />
      <CommandList>
        <CommandEmpty>{t("commandPalette.noResults")}</CommandEmpty>

        <CommandGroup heading={t("commandPalette.navigation")}>
          {workspaceItems.map(({ key, path, Icon, label }) => (
            <CommandItem
              key={key}
              onSelect={() =>
                runCommand(() => {
                  void navigate(path);
                })
              }
            >
              <Icon />
              <span>{label}</span>
            </CommandItem>
          ))}
        </CommandGroup>

        <CommandSeparator />

        <CommandGroup heading={t("commandPalette.appearance")}>
          <CommandItem
            onSelect={() =>
              runCommand(() => {
                toggleTheme();
              })
            }
          >
            <Sun />
            <span>{t("commandPalette.toggleTheme")}</span>
            <CommandShortcut>Theme</CommandShortcut>
          </CommandItem>
          {densityOptions.map(({ value, label, Icon }) => (
            <CommandItem
              key={value}
              onSelect={() => runCommand(() => setDensity(value))}
            >
              <Icon />
              <span>{label}</span>
              {density === value && (
                <CommandShortcut>Active</CommandShortcut>
              )}
            </CommandItem>
          ))}
        </CommandGroup>
      </CommandList>
    </CommandDialog>
  );
}
