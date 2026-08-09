import { useCallback, useEffect, useMemo, useState } from "react";
import { matchPath, useLocation, useNavigate } from "react-router-dom";
import {
  Activity,
  AlignJustify,
  Archive,
  Bot,
  Bug,
  Database,
  FileText,
  FlaskConical,
  GitBranch,
  LayoutDashboard,
  ListChecks,
  Network,
  PanelTop,
  Scale,
  ShieldCheck,
  Sun,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

import {
  isDiscoveryCapabilityEnabled,
  useCapabilityDiscovery,
} from "@/api/hooks/useCapabilities";
import { useMaybeAuthz } from "@/app/authz/AuthzProvider";
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
  CommandShortcut,
} from "@polisyos/atlas-ui";
import { useDensity } from "@/app/providers/DensityProvider";
import { useFeatureFlags } from "@/app/providers/FeatureFlagProvider";
import { useTheme } from "@/app/providers/ThemeProvider";
import {
  getCommandPaletteSurfaceEntries,
  type CommandPaletteSurfaceEntry,
  type SurfaceId,
} from "@/app/surfaces/surfaceRegistry";
import { useI18n } from "@/shared/i18n/LocaleProvider";
import { useGlobalShortcut } from "@/shared/lib/hooks";
import { WORKSPACES, type WorkspaceKey } from "@/app/workspaces";

const SURFACE_ICONS: Partial<Record<SurfaceId, LucideIcon>> = {
  "fabric.connectorCards": Database,
  "fabric.freshnessBraid": Activity,
  "runs.agents": Bot,
  "runs.ambientTelemetry": Activity,
  "runs.artifacts": Archive,
  "runs.causal": Network,
  "runs.causalAtlas": Network,
  "runs.debug": Bug,
  "runs.disputeRegistry": Scale,
  "runs.evidence": FileText,
  "runs.governance": ShieldCheck,
  "runs.overview": PanelTop,
  "runs.runChoreography": GitBranch,
  "runs.workflow": GitBranch,
  "workspace.commandCenter": LayoutDashboard,
  "workspace.evidenceFabric": Database,
  "workspace.lexKnowledge": Network,
  "workspace.platformHealth": Activity,
  "workspace.runsDecisions": ListChecks,
  "workspace.scenarioComposer": FlaskConical,
};

function SurfaceCommandItem({
  label,
  onSelect,
  surface,
}: {
  label: string;
  onSelect: () => void;
  surface: CommandPaletteSurfaceEntry;
}) {
  const Icon = SURFACE_ICONS[surface.id] ?? PanelTop;
  const searchValue = [
    label,
    surface.id,
    surface.routeId,
    surface.labelKey,
    surface.descriptionKey,
    ...surface.aliases,
    ...(surface.legacyAliases ?? []),
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <CommandItem value={searchValue} onSelect={onSelect}>
      <Icon />
      <span>{label}</span>
      {surface.command.shortcut ? (
        <CommandShortcut>{surface.command.shortcut}</CommandShortcut>
      ) : null}
    </CommandItem>
  );
}

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();
  const authz = useMaybeAuthz();
  const capabilityDiscovery = useCapabilityDiscovery();
  const { flags } = useFeatureFlags();
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

  const currentRunId =
    matchPath("/runs/:runId/*", location.pathname)?.params.runId ??
    matchPath("/runs/:runId", location.pathname)?.params.runId ??
    null;
  const surfaceEntries = useMemo(
    () =>
      getCommandPaletteSurfaceEntries({
        canAccessPermission: (permission) =>
          authz ? authz.can(permission) : true,
        hasCapability: (capability) =>
          isDiscoveryCapabilityEnabled(capabilityDiscovery, capability),
        isWorkspaceAllowed: (workspaceKey) =>
          authz ? authz.isWorkspaceAllowed(workspaceKey) : true,
        isWorkspaceEnabled: (workspaceKey: WorkspaceKey) => {
          const workspace = WORKSPACES[workspaceKey];
          return workspace.featureFlag ? flags[workspace.featureFlag] : true;
        },
        runId: currentRunId,
      }),
    [authz, capabilityDiscovery, currentRunId, flags],
  );
  const navigationItems = surfaceEntries.filter(
    (surface) => surface.command.group === "navigation",
  );
  const runSurfaceItems = surfaceEntries.filter(
    (surface) => surface.command.group === "runSurfaces",
  );
  const workspaceSurfaceItems = surfaceEntries.filter(
    (surface) => surface.command.group === "workspaceSurfaces",
  );

  return (
    <CommandDialog
      open={open}
      onOpenChange={setOpen}
      title={t("shared.ui.command.paletteTitle")}
      closeLabel={t("common.close")}
    >
      <CommandInput placeholder={t("commandPalette.placeholder")} />
      <CommandList>
        <CommandEmpty>{t("commandPalette.noResults")}</CommandEmpty>

        <CommandGroup heading={t("commandPalette.navigation")}>
          {navigationItems.map((surface) => (
            <SurfaceCommandItem
              key={surface.id}
              surface={surface}
              label={t(surface.labelKey)}
              onSelect={() =>
                runCommand(() => {
                  void navigate(surface.href);
                })
              }
            />
          ))}
        </CommandGroup>

        {runSurfaceItems.length > 0 ? (
          <>
            <CommandSeparator />
            <CommandGroup heading={t("commandPalette.runSurfaces")}>
              {runSurfaceItems.map((surface) => (
                <SurfaceCommandItem
                  key={surface.id}
                  surface={surface}
                  label={t(surface.labelKey)}
                  onSelect={() =>
                    runCommand(() => {
                      void navigate(surface.href);
                    })
                  }
                />
              ))}
            </CommandGroup>
          </>
        ) : null}

        {workspaceSurfaceItems.length > 0 ? (
          <>
            <CommandSeparator />
            <CommandGroup heading={t("commandPalette.workspaceSurfaces")}>
              {workspaceSurfaceItems.map((surface) => (
                <SurfaceCommandItem
                  key={surface.id}
                  surface={surface}
                  label={t(surface.labelKey)}
                  onSelect={() =>
                    runCommand(() => {
                      void navigate(surface.href);
                    })
                  }
                />
              ))}
            </CommandGroup>
          </>
        ) : null}

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
