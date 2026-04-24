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
import { useDensity } from "@/app/providers/DensityProvider";
import { useTheme } from "@/app/providers/ThemeProvider";
import { useI18n } from "@/i18n/LocaleProvider";
import { useGlobalShortcut } from "@/lib/hooks";
import {
  WORKSPACE_ORDER,
  WORKSPACES,
  type WorkspaceKey,
} from "@/app/workspaces";

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
  const { resolvedTheme, toggleTheme } = useTheme();
  const { cycleDensity, density } = useDensity();

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

  const runCommand = useCallback((command: () => void) => {
    setOpen(false);
    command();
  }, []);

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
            <CommandShortcut>
              {t("pages.platform.appearance.themeShortcut")}
            </CommandShortcut>
          </CommandItem>
          <CommandItem
            onSelect={() =>
              runCommand(() => {
                cycleDensity();
              })
            }
          >
            <AlignJustify />
            <span>{t("commandPalette.cycleDensity")}</span>
            <CommandShortcut>
              {t("pages.platform.appearance.densityShortcut")}
            </CommandShortcut>
          </CommandItem>
          <CommandSeparator />
          <CommandItem disabled>
            <Sun />
            <span>
              {t(`pages.platform.appearance.themeOptions.${resolvedTheme}`)}
            </span>
            <CommandShortcut>
              {t(`pages.platform.appearance.densityOptions.${density}`)}
            </CommandShortcut>
          </CommandItem>
        </CommandGroup>
      </CommandList>
    </CommandDialog>
  );
}
