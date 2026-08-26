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
  createCapabilitySearchRequest,
  useCapabilitySearch,
} from "@/api/hooks/useCapabilitySearch";
import { useAuthzDecision } from "@/app/authz/AuthzProvider";
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
  const [capabilityQuery, setCapabilityQuery] = useState("");
  const location = useLocation();
  const navigate = useNavigate();
  const authzDecision = useAuthzDecision();
  const { flags } = useFeatureFlags();
  const { t } = useI18n();
  const { resolvedTheme, toggleTheme } = useTheme();
  const { cycleDensity, density } = useDensity();
  const commandPaletteEnabled = flags.enableCommandPalette;
  const capabilitySearchRequest = useMemo(
    () =>
      createCapabilitySearchRequest(
        capabilityQuery,
        "command-palette-capability-discovery",
      ),
    [capabilityQuery],
  );
  const capabilitySearch = useCapabilitySearch(
    capabilitySearchRequest,
    undefined,
    open && capabilityQuery.trim().length > 0,
  );
  const capabilityCandidates = capabilitySearch.data?.response.results ?? [];

  useGlobalShortcut(
    "command-palette",
    { key: "k", meta: true },
    "Open command palette",
    () => setOpen((o) => !o),
    { enabled: commandPaletteEnabled, group: "Global" },
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

  const matchedRunId =
    matchPath("/runs/:runId/*", location.pathname)?.params.runId ??
    matchPath("/runs/:runId", location.pathname)?.params.runId ??
    null;
  const currentRunId =
    matchedRunId === "compare" || matchedRunId === "cycle-board"
      ? null
      : matchedRunId;
  const surfaceEntries = useMemo(
    () =>
      getCommandPaletteSurfaceEntries({
        canAccessPermission: (permission) =>
          authzDecision.kind === "verified" && authzDecision.can(permission),
        isWorkspaceAllowed: (workspaceKey) =>
          authzDecision.kind === "verified" &&
          authzDecision.isWorkspaceAllowed(workspaceKey),
        isFeatureEnabled: (featureFlag) => flags[featureFlag],
        isWorkspaceEnabled: (workspaceKey: WorkspaceKey) => {
          const workspace = WORKSPACES[workspaceKey];
          return workspace.featureFlag ? flags[workspace.featureFlag] : true;
        },
        runId: currentRunId,
      }),
    [authzDecision, currentRunId, flags],
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

  if (!commandPaletteEnabled) {
    return null;
  }

  return (
    <CommandDialog
      open={open}
      onOpenChange={setOpen}
      title={t("shared.ui.command.paletteTitle")}
      closeLabel={t("common.close")}
    >
      <CommandInput
        placeholder={t("commandPalette.placeholder")}
        value={capabilityQuery}
        onValueChange={setCapabilityQuery}
      />
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

        {capabilityQuery.trim().length > 0 ? (
          <>
            <CommandSeparator />
            <CommandGroup heading={t("capabilityDiscovery.title")}>
              {capabilityCandidates.map((candidate) => (
                <CommandItem
                  key={candidate.capability_ref}
                  value={[
                    candidate.label,
                    candidate.description,
                    candidate.capability_ref,
                    candidate.resource_kind,
                  ].join(" ")}
                  onSelect={() =>
                    runCommand(() => {
                      void navigate(
                        `/evidence?capability=${encodeURIComponent(candidate.capability_ref)}`,
                      );
                    })
                  }
                >
                  <Database />
                  <span>
                    {candidate.label} · Candidate · {candidate.resource_kind} ·{" "}
                    {candidate.discovery_result.state} ·{" "}
                    {candidate.execution_result.state} ·{" "}
                    {candidate.authority_result.state}
                  </span>
                </CommandItem>
              ))}
              {capabilitySearch.data && capabilityCandidates.length === 0 ? (
                <CommandItem disabled>
                  <Database />
                  <span>
                    Candidate frontier ·{" "}
                    {
                      capabilitySearch.data.response.frontier
                        .completeness_status
                    }
                    {capabilitySearch.data.response.frontier
                      .incompleteness_reasons.length > 0
                      ? ` · ${capabilitySearch.data.response.frontier.incompleteness_reasons.join(", ")}`
                      : ""}
                  </span>
                </CommandItem>
              ) : null}
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
