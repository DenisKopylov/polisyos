import { dataIndexStatsQueryOptions } from "@/api/hooks/useDataIndexStats";
import { dataPromotionCandidatesQueryOptions } from "@/api/hooks/useDataPromotionCandidates";
import { capabilitiesQueryOptions } from "@/api/hooks/useCapabilities";
import { connectorsQueryOptions } from "@/api/hooks/useConnectors";
import { healthQueryOptions } from "@/api/hooks/useHealth";
import { llmProfilesQueryOptions } from "@/api/hooks/useLlmProfiles";
import { runsQueryOptions } from "@/api/hooks/useRuns";
import { sourceProfilesQueryOptions } from "@/api/hooks/useSourceProfiles";
import { runsSampleQueryOptions } from "@/features/runs/workspaces.public";
import {
  readStoredThemePreference,
  type ThemePreference,
} from "@/app/providers/ThemeProvider";
import {
  readPreferencesFromStorage,
  type Density,
} from "@/app/state/usePreferencesStore";
import type { InterfaceMode } from "@/app/providers/InterfaceModeProvider";
import type { FeatureFlagKey, FeatureFlags } from "@/shared/lib/featureFlags";

export type WorkspaceKey =
  | "commandCenter"
  | "scenarioComposer"
  | "runsDecisions"
  | "evidenceFabric"
  | "lexKnowledge"
  | "platformHealth";

export type WorkspaceLayout =
  | "overview"
  | "form"
  | "master-detail"
  | "full-width"
  | "chat";

export type WorkspacePrefetchKey =
  | "capabilities"
  | "connectors"
  | "dataIndexStats"
  | "dataPromotionCandidates"
  | "health"
  | "llmProfiles"
  | "runs"
  | "runsSample"
  | "sourceProfiles";

export type WorkspaceAppearancePreferences = {
  density: Density;
  theme: ThemePreference;
};

type WorkspaceBootstrapQueryOptions =
  | ReturnType<typeof capabilitiesQueryOptions>
  | ReturnType<typeof connectorsQueryOptions>
  | ReturnType<typeof dataIndexStatsQueryOptions>
  | ReturnType<typeof dataPromotionCandidatesQueryOptions>
  | ReturnType<typeof healthQueryOptions>
  | ReturnType<typeof llmProfilesQueryOptions>
  | ReturnType<typeof runsQueryOptions>
  | ReturnType<typeof sourceProfilesQueryOptions>;

type WorkspaceHeader = {
  eyebrowKey: string;
  titleKey: string;
  subtitleKey: string;
};

export type WorkspaceConfig = {
  key: WorkspaceKey;
  path: string;
  aliases: string[];
  featureFlag?: FeatureFlagKey;
  layout: WorkspaceLayout;
  modeVisibility?: InterfaceMode[];
  requiredCapabilities: string[];
  resolveHeader: (pathname: string) => WorkspaceHeader;
};

export const WORKSPACE_ORDER: WorkspaceKey[] = [
  "commandCenter",
  "scenarioComposer",
  "runsDecisions",
  "evidenceFabric",
  "lexKnowledge",
  "platformHealth",
];

export const WORKSPACES: Record<WorkspaceKey, WorkspaceConfig> = {
  commandCenter: {
    key: "commandCenter",
    path: "/",
    aliases: [],
    layout: "overview",
    modeVisibility: ["clerk", "analyst"],
    requiredCapabilities: [],
    resolveHeader: () => ({
      eyebrowKey: "shell.routes.commandCenterEyebrow",
      titleKey: "shell.routes.commandCenterTitle",
      subtitleKey: "pages.dashboard.subtitle",
    }),
  },
  scenarioComposer: {
    key: "scenarioComposer",
    path: "/compose",
    aliases: ["/launch"],
    featureFlag: "enableScenarioComposer",
    layout: "form",
    modeVisibility: ["analyst"],
    requiredCapabilities: ["workflow_runs"],
    resolveHeader: () => ({
      eyebrowKey: "pages.composer.title",
      titleKey: "pages.composer.heroTitle",
      subtitleKey: "pages.composer.subtitle",
    }),
  },
  runsDecisions: {
    key: "runsDecisions",
    path: "/runs",
    aliases: [],
    featureFlag: "enableRunsWorkspace",
    layout: "master-detail",
    modeVisibility: ["clerk", "analyst"],
    requiredCapabilities: ["workflow_runs"],
    resolveHeader: (pathname) => ({
      eyebrowKey: pathname.startsWith("/runs/")
        ? "shell.routes.runAnalysisEyebrow"
        : "pages.runs.title",
      titleKey: pathname.startsWith("/runs/")
        ? "shell.routes.runAnalysisTitle"
        : "pages.runs.explorerTitle",
      subtitleKey: "pages.runs.subtitle",
    }),
  },
  evidenceFabric: {
    key: "evidenceFabric",
    path: "/evidence",
    aliases: ["/sources", "/data"],
    layout: "full-width",
    modeVisibility: ["analyst"],
    requiredCapabilities: ["source_profiles"],
    resolveHeader: () => ({
      eyebrowKey: "shell.routes.evidenceEyebrow",
      titleKey: "shell.routes.evidenceTitle",
      subtitleKey: "pages.evidence.subtitle",
    }),
  },
  lexKnowledge: {
    key: "lexKnowledge",
    path: "/knowledge",
    aliases: ["/lex"],
    featureFlag: "enableLexKnowledge",
    layout: "full-width",
    modeVisibility: ["analyst"],
    requiredCapabilities: ["lex_pipeline"],
    resolveHeader: () => ({
      eyebrowKey: "shell.nav.lexKnowledge",
      titleKey: "shell.routes.lexTitle",
      subtitleKey: "shell.subtitle",
    }),
  },
  platformHealth: {
    key: "platformHealth",
    path: "/platform",
    aliases: ["/health"],
    featureFlag: "enablePlatformHealth",
    layout: "full-width",
    modeVisibility: ["analyst"],
    requiredCapabilities: [],
    resolveHeader: () => ({
      eyebrowKey: "shell.header.runtime",
      titleKey: "shell.routes.platformTitle",
      subtitleKey: "shell.subtitle",
    }),
  },
};

export function resolveWorkspaceKey(pathname: string): WorkspaceKey {
  for (const key of WORKSPACE_ORDER) {
    const workspace = WORKSPACES[key];
    if (
      pathname === workspace.path ||
      pathname.startsWith(`${workspace.path}/`)
    ) {
      return workspace.key;
    }
    if (
      workspace.aliases.some(
        (alias) => pathname === alias || pathname.startsWith(`${alias}/`),
      )
    ) {
      return workspace.key;
    }
  }
  if (pathname.startsWith("/artifacts")) {
    return "runsDecisions";
  }
  return "commandCenter";
}

export function isWorkspaceEnabled(
  workspace: WorkspaceConfig,
  flags: FeatureFlags,
) {
  return workspace.featureFlag ? flags[workspace.featureFlag] : true;
}

export function getWorkspaceNavigation(flags: FeatureFlags) {
  return getWorkspaceNavigationWithOptions(flags);
}

export function getWorkspaceNavigationWithOptions(
  flags: FeatureFlags,
  options?: {
    isAllowed?: (workspace: WorkspaceConfig) => boolean;
    mode?: InterfaceMode;
  },
) {
  return WORKSPACE_ORDER.map((key) => WORKSPACES[key]).filter(
    (workspace) =>
      isWorkspaceEnabled(workspace, flags) &&
      (options?.isAllowed ? options.isAllowed(workspace) : true) &&
      (options?.mode && workspace.modeVisibility
        ? workspace.modeVisibility.includes(options.mode)
        : true),
  );
}

export function buildBootstrapQueryOptions(
  key: WorkspacePrefetchKey,
): WorkspaceBootstrapQueryOptions {
  switch (key) {
    case "capabilities":
      return capabilitiesQueryOptions();
    case "connectors":
      return connectorsQueryOptions();
    case "dataIndexStats":
      return dataIndexStatsQueryOptions();
    case "dataPromotionCandidates":
      return dataPromotionCandidatesQueryOptions();
    case "health":
      return healthQueryOptions();
    case "llmProfiles":
      return llmProfilesQueryOptions();
    case "runs":
      return runsQueryOptions({ limit: 12 });
    case "runsSample":
      return runsSampleQueryOptions();
    case "sourceProfiles":
      return sourceProfilesQueryOptions();
  }
}

export function readWorkspaceAppearancePreferences(): WorkspaceAppearancePreferences {
  return {
    density: readPreferencesFromStorage().density,
    theme: readStoredThemePreference() ?? "system",
  };
}
