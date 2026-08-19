import {
  WORKSPACE_ORDER,
  WORKSPACES,
  type WorkspaceKey,
} from "@/app/workspaces";
import type { GlyphName } from "@/shared/brand/glyph-vocabulary";
import type { FeatureFlagKey } from "@/shared/lib/featureFlags";

export type SurfacePlacement = "panel" | "sidebar" | "workspace-tab";
export type SurfaceKind = "panel" | "run-tab" | "workspace";
export type SurfaceCommandGroup =
  | "navigation"
  | "runSurfaces"
  | "workspaceSurfaces";
export type SurfaceContextRequirement = "runId";
export type SurfacePermissionKey = "evidence.review" | "runs.review";

export type RunDetailSurfaceKey =
  | "overview"
  | "causal"
  | "governance"
  | "evidence"
  | "workflow"
  | "artifacts"
  | "agents"
  | "debug";

export type SurfaceId =
  | `fabric.${string}`
  | `runs.${string}`
  | `workspace.${WorkspaceKey}`;

export type SurfaceHrefContext = {
  runId?: string | null;
};

export type SurfaceRegistryEntry = {
  aliases: readonly string[];
  command: {
    enabled: boolean;
    group: SurfaceCommandGroup;
    requiresContext?: SurfaceContextRequirement;
    shortcut?: string;
  };
  descriptionKey: string;
  featureFlag?: FeatureFlagKey;
  glyph: GlyphName;
  id: SurfaceId;
  kind: SurfaceKind;
  labelKey: string;
  legacyAliases?: readonly string[];
  parentId?: SurfaceId;
  permissionKey?: SurfacePermissionKey;
  placement: SurfacePlacement;
  requiredCapabilities: readonly string[];
  resolveHref: (context: SurfaceHrefContext) => string | null;
  routeId?: string;
  semanticExplanationId: string;
  visualFixtureKind?: "large-graph" | "temporal";
  workspaceKey: WorkspaceKey;
};

function searchHref(
  pathname: string,
  params: Record<string, string | null | undefined>,
) {
  const search = new URLSearchParams(
    Object.entries(params).flatMap(([key, value]) =>
      value ? [[key, value]] : [],
    ),
  );
  return `${pathname}?${search.toString()}`;
}

export const WORKSPACE_SURFACES: readonly SurfaceRegistryEntry[] =
  WORKSPACE_ORDER.map((workspaceKey) => {
    const workspace = WORKSPACES[workspaceKey];
    const glyph: Record<WorkspaceKey, GlyphName> = {
      commandCenter: "governance-pass",
      evidenceFabric: "evidence",
      lexKnowledge: "provenance",
      platformHealth: "transport",
      runsDecisions: "reproducibility",
      scenarioComposer: "intervention",
    };

    return {
      aliases: workspace.aliases,
      command: {
        enabled: true,
        group: "navigation",
      },
      descriptionKey: workspace.resolveHeader(workspace.path).subtitleKey,
      glyph: glyph[workspaceKey],
      id: `workspace.${workspaceKey}`,
      kind: "workspace",
      labelKey: `shell.nav.${workspaceKey}`,
      placement: "sidebar",
      requiredCapabilities: workspace.requiredCapabilities,
      resolveHref: () => workspace.path,
      routeId: workspace.key,
      semanticExplanationId: `surface.workspace.${workspaceKey}`,
      workspaceKey,
    } satisfies SurfaceRegistryEntry;
  });

export const RUN_DETAIL_SURFACES: readonly SurfaceRegistryEntry[] = [
  {
    aliases: ["decision"],
    command: { enabled: true, group: "runSurfaces", requiresContext: "runId" },
    descriptionKey: "surfaceRegistry.run.overview.description",
    glyph: "governance-pass",
    id: "runs.overview",
    kind: "run-tab",
    labelKey: "pages.runs.tabs.overview",
    legacyAliases: ["decision"],
    placement: "workspace-tab",
    requiredCapabilities: [],
    resolveHref: ({ runId }) => (runId ? `/runs/${runId}/overview` : null),
    routeId: "runs.tab.overview",
    semanticExplanationId: "surface.runs.overview",
    workspaceKey: "runsDecisions",
  },
  {
    aliases: ["causal", "graph"],
    command: { enabled: true, group: "runSurfaces", requiresContext: "runId" },
    descriptionKey: "surfaceRegistry.run.causal.description",
    featureFlag: "enableCausalGraph",
    glyph: "identifiability",
    id: "runs.causal",
    kind: "run-tab",
    labelKey: "pages.runs.tabs.causal",
    legacyAliases: ["causal", "graph"],
    placement: "workspace-tab",
    requiredCapabilities: [],
    resolveHref: ({ runId }) => (runId ? `/runs/${runId}/causal` : null),
    routeId: "runs.tab.causal",
    semanticExplanationId: "surface.runs.causal",
    visualFixtureKind: "large-graph",
    workspaceKey: "runsDecisions",
  },
  {
    aliases: ["governance"],
    command: { enabled: true, group: "runSurfaces", requiresContext: "runId" },
    descriptionKey: "surfaceRegistry.run.governance.description",
    glyph: "governance-pass",
    id: "runs.governance",
    kind: "run-tab",
    labelKey: "pages.runs.tabs.governance",
    legacyAliases: ["governance"],
    permissionKey: "runs.review",
    placement: "workspace-tab",
    requiredCapabilities: ["evaluator_reports"],
    resolveHref: ({ runId }) => (runId ? `/runs/${runId}/governance` : null),
    routeId: "runs.tab.governance",
    semanticExplanationId: "surface.runs.governance",
    workspaceKey: "runsDecisions",
  },
  {
    aliases: ["evidence"],
    command: { enabled: true, group: "runSurfaces", requiresContext: "runId" },
    descriptionKey: "surfaceRegistry.run.evidence.description",
    glyph: "evidence",
    id: "runs.evidence",
    kind: "run-tab",
    labelKey: "pages.runs.tabs.evidence",
    legacyAliases: ["evidence"],
    permissionKey: "evidence.review",
    placement: "workspace-tab",
    requiredCapabilities: ["promotion_lane"],
    resolveHref: ({ runId }) => (runId ? `/runs/${runId}/evidence` : null),
    routeId: "runs.tab.evidence",
    semanticExplanationId: "surface.runs.evidence",
    workspaceKey: "runsDecisions",
  },
  {
    aliases: ["lineage", "workflow"],
    command: { enabled: true, group: "runSurfaces", requiresContext: "runId" },
    descriptionKey: "surfaceRegistry.run.workflow.description",
    glyph: "reproducibility",
    id: "runs.workflow",
    kind: "run-tab",
    labelKey: "pages.runs.tabs.workflow",
    legacyAliases: ["lineage", "workflow"],
    placement: "workspace-tab",
    requiredCapabilities: ["unified_dag"],
    resolveHref: ({ runId }) => (runId ? `/runs/${runId}/workflow` : null),
    routeId: "runs.tab.workflow",
    semanticExplanationId: "surface.runs.workflow",
    visualFixtureKind: "large-graph",
    workspaceKey: "runsDecisions",
  },
  {
    aliases: ["artifacts"],
    command: { enabled: true, group: "runSurfaces", requiresContext: "runId" },
    descriptionKey: "surfaceRegistry.run.artifacts.description",
    glyph: "provenance",
    id: "runs.artifacts",
    kind: "run-tab",
    labelKey: "pages.runs.tabs.artifacts",
    legacyAliases: ["artifacts"],
    placement: "workspace-tab",
    requiredCapabilities: [],
    resolveHref: ({ runId }) => (runId ? `/runs/${runId}/artifacts` : null),
    routeId: "runs.tab.artifacts",
    semanticExplanationId: "surface.runs.artifacts",
    workspaceKey: "runsDecisions",
  },
  {
    aliases: ["agents", "models"],
    command: { enabled: true, group: "runSurfaces", requiresContext: "runId" },
    descriptionKey: "surfaceRegistry.run.agents.description",
    glyph: "transport",
    id: "runs.agents",
    kind: "run-tab",
    labelKey: "pages.runs.tabs.agents",
    legacyAliases: ["agents", "models"],
    placement: "workspace-tab",
    requiredCapabilities: ["natural_language_runs"],
    resolveHref: ({ runId }) => (runId ? `/runs/${runId}/agents` : null),
    routeId: "runs.tab.agents",
    semanticExplanationId: "surface.runs.agents",
    workspaceKey: "runsDecisions",
  },
  {
    aliases: ["timeline", "nodes", "debug"],
    command: { enabled: true, group: "runSurfaces", requiresContext: "runId" },
    descriptionKey: "surfaceRegistry.run.debug.description",
    glyph: "freshness",
    id: "runs.debug",
    kind: "run-tab",
    labelKey: "pages.runs.tabs.debug",
    legacyAliases: ["timeline", "nodes", "debug"],
    placement: "workspace-tab",
    requiredCapabilities: [],
    resolveHref: ({ runId }) => (runId ? `/runs/${runId}/debug` : null),
    routeId: "runs.tab.debug",
    semanticExplanationId: "surface.runs.debug",
    visualFixtureKind: "temporal",
    workspaceKey: "runsDecisions",
  },
] as const;

export const PANEL_SURFACES: readonly SurfaceRegistryEntry[] = [
  {
    aliases: ["freshness", "braid", "source lag"],
    command: { enabled: true, group: "workspaceSurfaces" },
    descriptionKey: "surfaceRegistry.panels.freshnessBraid.description",
    glyph: "freshness",
    id: "fabric.freshnessBraid",
    kind: "panel",
    labelKey: "surfaceRegistry.panels.freshnessBraid.label",
    parentId: "workspace.evidenceFabric",
    placement: "panel",
    requiredCapabilities: ["source_profiles"],
    resolveHref: ({ runId }) =>
      searchHref("/evidence", { runId, surface: "freshness-braid" }),
    routeId: "surface.fabric.freshnessBraid",
    semanticExplanationId: "surface.fabric.freshnessBraid",
    visualFixtureKind: "temporal",
    workspaceKey: "evidenceFabric",
  },
  {
    aliases: ["connectors", "source cards", "connector health"],
    command: { enabled: true, group: "workspaceSurfaces" },
    descriptionKey: "surfaceRegistry.panels.connectorCards.description",
    glyph: "transport",
    id: "fabric.connectorCards",
    kind: "panel",
    labelKey: "surfaceRegistry.panels.connectorCards.label",
    parentId: "workspace.evidenceFabric",
    placement: "panel",
    requiredCapabilities: ["source_profiles"],
    resolveHref: ({ runId }) =>
      searchHref("/evidence", { runId, surface: "connector-cards" }),
    routeId: "surface.fabric.connectorCards",
    semanticExplanationId: "surface.fabric.connectorCards",
    workspaceKey: "evidenceFabric",
  },
  {
    aliases: ["choreography", "run score", "event score"],
    command: { enabled: true, group: "runSurfaces", requiresContext: "runId" },
    descriptionKey: "surfaceRegistry.panels.runChoreography.description",
    glyph: "reproducibility",
    id: "runs.runChoreography",
    kind: "panel",
    labelKey: "surfaceRegistry.panels.runChoreography.label",
    parentId: "runs.workflow",
    placement: "panel",
    requiredCapabilities: ["unified_dag"],
    resolveHref: ({ runId }) =>
      runId
        ? searchHref(`/runs/${runId}/workflow`, { surface: "choreography" })
        : null,
    routeId: "surface.runs.runChoreography",
    semanticExplanationId: "surface.runs.runChoreography",
    visualFixtureKind: "temporal",
    workspaceKey: "runsDecisions",
  },
  {
    aliases: ["telemetry", "transport health", "sse"],
    command: { enabled: true, group: "workspaceSurfaces" },
    descriptionKey: "surfaceRegistry.panels.ambientTelemetry.description",
    glyph: "transport",
    id: "runs.ambientTelemetry",
    kind: "panel",
    labelKey: "surfaceRegistry.panels.ambientTelemetry.label",
    parentId: "workspace.runsDecisions",
    placement: "panel",
    requiredCapabilities: [],
    resolveHref: ({ runId }) =>
      runId
        ? searchHref(`/runs/${runId}/overview`, {
            surface: "ambient-telemetry",
          })
        : searchHref("/runs", { surface: "ambient-telemetry" }),
    routeId: "surface.runs.ambientTelemetry",
    semanticExplanationId: "surface.runs.ambientTelemetry",
    workspaceKey: "runsDecisions",
  },
  {
    aliases: ["causal atlas", "dag", "identification"],
    command: { enabled: true, group: "runSurfaces", requiresContext: "runId" },
    descriptionKey: "surfaceRegistry.panels.causalAtlas.description",
    featureFlag: "enableCausalGraph",
    glyph: "identifiability",
    id: "runs.causalAtlas",
    kind: "panel",
    labelKey: "surfaceRegistry.panels.causalAtlas.label",
    parentId: "runs.causal",
    placement: "panel",
    requiredCapabilities: [],
    resolveHref: ({ runId }) =>
      runId
        ? searchHref(`/runs/${runId}/causal`, { surface: "causal-atlas" })
        : null,
    routeId: "surface.runs.causalAtlas",
    semanticExplanationId: "surface.runs.causalAtlas",
    visualFixtureKind: "large-graph",
    workspaceKey: "runsDecisions",
  },
  {
    aliases: ["identifiability", "identified set", "bounds", "manski"],
    command: { enabled: true, group: "runSurfaces", requiresContext: "runId" },
    descriptionKey: "surfaceRegistry.panels.identifiabilitySurface.description",
    featureFlag: "enableCausalGraph",
    glyph: "identifiability",
    id: "runs.identifiabilitySurface",
    kind: "panel",
    labelKey: "surfaceRegistry.panels.identifiabilitySurface.label",
    parentId: "runs.causal",
    placement: "panel",
    requiredCapabilities: [],
    resolveHref: ({ runId }) =>
      runId
        ? searchHref(`/runs/${runId}/overview`, {
            surface: "identifiability-surface",
          })
        : null,
    routeId: "surface.runs.identifiabilitySurface",
    semanticExplanationId: "surface.runs.identifiabilitySurface",
    visualFixtureKind: "large-graph",
    workspaceKey: "runsDecisions",
  },
  {
    aliases: ["sensitivity", "e-value", "rotor", "trust threshold"],
    command: { enabled: true, group: "runSurfaces", requiresContext: "runId" },
    descriptionKey: "surfaceRegistry.panels.sensitivityRotor.description",
    glyph: "counterfactual",
    id: "runs.sensitivityRotor",
    kind: "panel",
    labelKey: "surfaceRegistry.panels.sensitivityRotor.label",
    parentId: "runs.overview",
    placement: "panel",
    requiredCapabilities: [],
    resolveHref: ({ runId }) =>
      runId
        ? searchHref(`/runs/${runId}/overview`, {
            surface: "sensitivity-rotor",
          })
        : null,
    routeId: "surface.runs.sensitivityRotor",
    semanticExplanationId: "surface.runs.sensitivityRotor",
    visualFixtureKind: "temporal",
    workspaceKey: "runsDecisions",
  },
  {
    aliases: ["cohort", "time traveler", "valid time", "policy overlay"],
    command: { enabled: true, group: "runSurfaces", requiresContext: "runId" },
    descriptionKey: "surfaceRegistry.panels.cohortTimeTraveler.description",
    glyph: "counterfactual",
    id: "runs.cohortTimeTraveler",
    kind: "panel",
    labelKey: "surfaceRegistry.panels.cohortTimeTraveler.label",
    parentId: "runs.overview",
    placement: "panel",
    requiredCapabilities: [],
    resolveHref: ({ runId }) =>
      runId
        ? searchHref(`/runs/${runId}/overview`, {
            surface: "cohort-time-traveler",
          })
        : null,
    routeId: "surface.runs.cohortTimeTraveler",
    semanticExplanationId: "surface.runs.cohortTimeTraveler",
    visualFixtureKind: "temporal",
    workspaceKey: "runsDecisions",
  },
  {
    aliases: ["stress", "stress scenes", "stress theatre", "block warning"],
    command: { enabled: true, group: "runSurfaces", requiresContext: "runId" },
    descriptionKey: "surfaceRegistry.panels.stressTestTheatre.description",
    glyph: "blocker",
    id: "runs.stressTestTheatre",
    kind: "panel",
    labelKey: "surfaceRegistry.panels.stressTestTheatre.label",
    parentId: "runs.governance",
    placement: "panel",
    requiredCapabilities: ["evaluator_reports"],
    resolveHref: ({ runId }) =>
      runId
        ? searchHref(`/runs/${runId}/overview`, {
            surface: "stress-test-theatre",
          })
        : null,
    routeId: "surface.runs.stressTestTheatre",
    semanticExplanationId: "surface.runs.stressTestTheatre",
    visualFixtureKind: "temporal",
    workspaceKey: "runsDecisions",
  },
  {
    aliases: ["objections", "disputes", "appeals"],
    command: { enabled: true, group: "runSurfaces", requiresContext: "runId" },
    descriptionKey: "surfaceRegistry.panels.disputeRegistry.description",
    glyph: "blocker",
    id: "runs.disputeRegistry",
    kind: "panel",
    labelKey: "surfaceRegistry.panels.disputeRegistry.label",
    parentId: "runs.governance",
    permissionKey: "runs.review",
    placement: "panel",
    requiredCapabilities: ["evaluator_reports"],
    resolveHref: ({ runId }) =>
      runId
        ? searchHref(`/runs/${runId}/governance`, { surface: "disputes" })
        : null,
    routeId: "surface.runs.disputeRegistry",
    semanticExplanationId: "surface.runs.disputeRegistry",
    workspaceKey: "runsDecisions",
  },
  {
    aliases: ["stakeholder lens", "lens", "regulator", "appellant"],
    command: { enabled: true, group: "runSurfaces", requiresContext: "runId" },
    descriptionKey: "surfaceRegistry.panels.stakeholderLens.description",
    glyph: "governance-pass",
    id: "runs.stakeholderLens",
    kind: "panel",
    labelKey: "surfaceRegistry.panels.stakeholderLens.label",
    parentId: "runs.overview",
    placement: "panel",
    requiredCapabilities: [],
    resolveHref: ({ runId }) =>
      runId
        ? searchHref(`/runs/${runId}/overview`, {
            surface: "stakeholder-lens",
          })
        : null,
    routeId: "surface.runs.stakeholderLens",
    semanticExplanationId: "surface.runs.stakeholderLens",
    workspaceKey: "runsDecisions",
  },
  {
    aliases: ["fairness audit", "bias", "sentinel", "disparate impact"],
    command: { enabled: true, group: "runSurfaces", requiresContext: "runId" },
    descriptionKey: "surfaceRegistry.panels.fairnessAudit.description",
    glyph: "blocker",
    id: "runs.fairnessAudit",
    kind: "panel",
    labelKey: "surfaceRegistry.panels.fairnessAudit.label",
    parentId: "runs.governance",
    permissionKey: "runs.review",
    placement: "panel",
    requiredCapabilities: ["evaluator_reports"],
    resolveHref: ({ runId }) =>
      runId
        ? searchHref(`/runs/${runId}/governance`, {
            surface: "fairness-audit",
          })
        : null,
    routeId: "surface.runs.fairnessAudit",
    semanticExplanationId: "surface.runs.fairnessAudit",
    workspaceKey: "runsDecisions",
  },
  {
    aliases: ["harm", "ethics", "eu ai act", "human oversight"],
    command: { enabled: true, group: "runSurfaces", requiresContext: "runId" },
    descriptionKey: "surfaceRegistry.panels.harmSurface.description",
    glyph: "governance-pass",
    id: "runs.harmSurface",
    kind: "panel",
    labelKey: "surfaceRegistry.panels.harmSurface.label",
    parentId: "runs.governance",
    permissionKey: "runs.review",
    placement: "panel",
    requiredCapabilities: ["evaluator_reports"],
    resolveHref: ({ runId }) =>
      runId
        ? searchHref(`/runs/${runId}/governance`, { surface: "harm-surface" })
        : null,
    routeId: "surface.runs.harmSurface",
    semanticExplanationId: "surface.runs.harmSurface",
    workspaceKey: "runsDecisions",
  },
  {
    aliases: ["embargo", "blackout", "masking", "restricted data"],
    command: { enabled: true, group: "runSurfaces", requiresContext: "runId" },
    descriptionKey: "surfaceRegistry.panels.embargoOverlay.description",
    glyph: "freshness",
    id: "runs.embargoOverlay",
    kind: "panel",
    labelKey: "surfaceRegistry.panels.embargoOverlay.label",
    parentId: "runs.evidence",
    permissionKey: "evidence.review",
    placement: "panel",
    requiredCapabilities: ["promotion_lane"],
    resolveHref: ({ runId }) =>
      runId
        ? searchHref(`/runs/${runId}/overview`, {
            surface: "embargo-overlay",
          })
        : null,
    routeId: "surface.runs.embargoOverlay",
    semanticExplanationId: "surface.runs.embargoOverlay",
    workspaceKey: "runsDecisions",
  },
  {
    aliases: ["slow review", "attention", "dwell", "approval friction"],
    command: { enabled: true, group: "runSurfaces", requiresContext: "runId" },
    descriptionKey: "surfaceRegistry.panels.slowReviewMode.description",
    glyph: "reproducibility",
    id: "runs.slowReviewMode",
    kind: "panel",
    labelKey: "surfaceRegistry.panels.slowReviewMode.label",
    parentId: "runs.governance",
    permissionKey: "runs.review",
    placement: "panel",
    requiredCapabilities: ["evaluator_reports"],
    resolveHref: ({ runId }) =>
      runId
        ? searchHref(`/runs/${runId}/governance`, {
            surface: "slow-review",
          })
        : null,
    routeId: "surface.runs.slowReviewMode",
    semanticExplanationId: "surface.runs.slowReviewMode",
    visualFixtureKind: "temporal",
    workspaceKey: "runsDecisions",
  },
  {
    aliases: ["revocation", "superseded", "policy chain", "replacement"],
    command: { enabled: true, group: "runSurfaces", requiresContext: "runId" },
    descriptionKey: "surfaceRegistry.panels.revocationLedger.description",
    glyph: "provenance",
    id: "runs.revocationLedger",
    kind: "panel",
    labelKey: "surfaceRegistry.panels.revocationLedger.label",
    parentId: "runs.governance",
    permissionKey: "runs.review",
    placement: "panel",
    requiredCapabilities: ["evaluator_reports"],
    resolveHref: ({ runId }) =>
      runId
        ? searchHref(`/runs/${runId}/governance`, {
            surface: "revocation-ledger",
          })
        : null,
    routeId: "surface.runs.revocationLedger",
    semanticExplanationId: "surface.runs.revocationLedger",
    visualFixtureKind: "temporal",
    workspaceKey: "runsDecisions",
  },
  {
    aliases: ["argument map", "toulmin", "claim graph", "reasoning"],
    command: { enabled: true, group: "runSurfaces", requiresContext: "runId" },
    descriptionKey: "surfaceRegistry.panels.argumentMap.description",
    glyph: "governance-pass",
    id: "runs.argumentMap",
    kind: "panel",
    labelKey: "surfaceRegistry.panels.argumentMap.label",
    parentId: "runs.overview",
    placement: "panel",
    requiredCapabilities: [],
    resolveHref: ({ runId }) =>
      runId
        ? searchHref(`/runs/${runId}/overview`, { surface: "argument-map" })
        : null,
    routeId: "surface.runs.argumentMap",
    semanticExplanationId: "surface.runs.argumentMap",
    visualFixtureKind: "large-graph",
    workspaceKey: "runsDecisions",
  },
  {
    aliases: ["comprehension", "semantic explanation", "help overlay"],
    command: { enabled: true, group: "runSurfaces", requiresContext: "runId" },
    descriptionKey: "surfaceRegistry.panels.comprehensionLayer.description",
    glyph: "provenance",
    id: "runs.comprehensionLayer",
    kind: "panel",
    labelKey: "surfaceRegistry.panels.comprehensionLayer.label",
    parentId: "runs.overview",
    placement: "panel",
    requiredCapabilities: [],
    resolveHref: ({ runId }) =>
      runId
        ? searchHref(`/runs/${runId}/overview`, {
            surface: "comprehension-layer",
          })
        : null,
    routeId: "surface.runs.comprehensionLayer",
    semanticExplanationId: "surface.runs.comprehensionLayer",
    workspaceKey: "runsDecisions",
  },
  {
    aliases: ["glossary", "lexicon", "definitions", "terms"],
    command: { enabled: true, group: "runSurfaces", requiresContext: "runId" },
    descriptionKey: "surfaceRegistry.panels.glossaryLens.description",
    glyph: "provenance",
    id: "runs.glossaryLens",
    kind: "panel",
    labelKey: "surfaceRegistry.panels.glossaryLens.label",
    parentId: "runs.overview",
    placement: "panel",
    requiredCapabilities: [],
    resolveHref: ({ runId }) =>
      runId
        ? searchHref(`/runs/${runId}/overview`, { surface: "glossary-lens" })
        : null,
    routeId: "surface.runs.glossaryLens",
    semanticExplanationId: "surface.runs.glossaryLens",
    workspaceKey: "runsDecisions",
  },
  {
    aliases: ["confidence ladder", "weakest link", "strongest claim"],
    command: { enabled: true, group: "runSurfaces", requiresContext: "runId" },
    descriptionKey: "surfaceRegistry.panels.confidenceLadder.description",
    glyph: "identifiability",
    id: "runs.confidenceLadder",
    kind: "panel",
    labelKey: "surfaceRegistry.panels.confidenceLadder.label",
    parentId: "runs.overview",
    placement: "panel",
    requiredCapabilities: [],
    resolveHref: ({ runId }) =>
      runId
        ? searchHref(`/runs/${runId}/overview`, {
            surface: "confidence-ladder",
          })
        : null,
    routeId: "surface.runs.confidenceLadder",
    semanticExplanationId: "surface.runs.confidenceLadder",
    workspaceKey: "runsDecisions",
  },
  {
    aliases: ["model card", "citation card", "references", "bibliography"],
    command: { enabled: true, group: "runSurfaces", requiresContext: "runId" },
    descriptionKey: "surfaceRegistry.panels.modelCard.description",
    glyph: "provenance",
    id: "runs.modelCard",
    kind: "panel",
    labelKey: "surfaceRegistry.panels.modelCard.label",
    parentId: "runs.artifacts",
    placement: "panel",
    requiredCapabilities: [],
    resolveHref: ({ runId }) =>
      runId
        ? searchHref(`/runs/${runId}/overview`, { surface: "model-card" })
        : null,
    routeId: "surface.runs.modelCard",
    semanticExplanationId: "surface.runs.modelCard",
    workspaceKey: "runsDecisions",
  },
  {
    aliases: ["public viewer", "signed decision", "provenance theatre"],
    command: { enabled: true, group: "runSurfaces", requiresContext: "runId" },
    descriptionKey: "surfaceRegistry.panels.publicViewer.description",
    glyph: "governance-pass",
    id: "runs.publicViewer",
    kind: "panel",
    labelKey: "surfaceRegistry.panels.publicViewer.label",
    parentId: "runs.artifacts",
    placement: "panel",
    requiredCapabilities: [],
    resolveHref: ({ runId }) =>
      runId
        ? searchHref(`/runs/${runId}/overview`, { surface: "public-viewer" })
        : null,
    routeId: "surface.runs.publicViewer",
    semanticExplanationId: "surface.runs.publicViewer",
    workspaceKey: "runsDecisions",
  },
  {
    aliases: ["coverage map", "coverage caveat", "geography evidence"],
    command: { enabled: true, group: "runSurfaces", requiresContext: "runId" },
    descriptionKey: "surfaceRegistry.panels.coverageMap.description",
    glyph: "evidence",
    id: "runs.coverageMap",
    kind: "panel",
    labelKey: "surfaceRegistry.panels.coverageMap.label",
    parentId: "runs.evidence",
    placement: "panel",
    requiredCapabilities: ["promotion_lane"],
    resolveHref: ({ runId }) =>
      runId
        ? searchHref(`/runs/${runId}/overview`, { surface: "coverage-map" })
        : null,
    routeId: "surface.runs.coverageMap",
    semanticExplanationId: "surface.runs.coverageMap",
    visualFixtureKind: "large-graph",
    workspaceKey: "runsDecisions",
  },
  {
    aliases: ["threshold contract", "microcontract", "cutoff", "edge cases"],
    command: { enabled: true, group: "runSurfaces", requiresContext: "runId" },
    descriptionKey: "surfaceRegistry.panels.thresholdContract.description",
    glyph: "intervention",
    id: "runs.thresholdContract",
    kind: "panel",
    labelKey: "surfaceRegistry.panels.thresholdContract.label",
    parentId: "runs.overview",
    placement: "panel",
    requiredCapabilities: [],
    resolveHref: ({ runId }) =>
      runId
        ? searchHref(`/runs/${runId}/overview`, {
            surface: "threshold-contract",
          })
        : null,
    routeId: "surface.runs.thresholdContract",
    semanticExplanationId: "surface.runs.thresholdContract",
    workspaceKey: "runsDecisions",
  },
  {
    aliases: ["trust dial", "trust threshold", "confidence threshold"],
    command: { enabled: true, group: "runSurfaces", requiresContext: "runId" },
    descriptionKey: "surfaceRegistry.panels.globalTrustDial.description",
    glyph: "counterfactual",
    id: "runs.globalTrustDial",
    kind: "panel",
    labelKey: "surfaceRegistry.panels.globalTrustDial.label",
    parentId: "runs.overview",
    placement: "panel",
    requiredCapabilities: [],
    resolveHref: ({ runId }) =>
      runId
        ? searchHref(`/runs/${runId}/overview`, {
            surface: "global-trust-dial",
          })
        : null,
    routeId: "surface.runs.globalTrustDial",
    semanticExplanationId: "surface.runs.globalTrustDial",
    workspaceKey: "runsDecisions",
  },
  {
    aliases: ["annotations", "snapshot notes", "review notes"],
    command: { enabled: true, group: "runSurfaces", requiresContext: "runId" },
    descriptionKey: "surfaceRegistry.panels.annotationSurface.description",
    glyph: "provenance",
    id: "runs.annotationSurface",
    kind: "panel",
    labelKey: "surfaceRegistry.panels.annotationSurface.label",
    parentId: "runs.overview",
    permissionKey: "runs.review",
    placement: "panel",
    requiredCapabilities: [],
    resolveHref: ({ runId }) =>
      runId
        ? searchHref(`/runs/${runId}/overview`, {
            surface: "annotation-surface",
          })
        : null,
    routeId: "surface.runs.annotationSurface",
    semanticExplanationId: "surface.runs.annotationSurface",
    workspaceKey: "runsDecisions",
  },
  {
    aliases: ["evidence wallet", "saved evidence", "review wallet"],
    command: { enabled: true, group: "runSurfaces", requiresContext: "runId" },
    descriptionKey: "surfaceRegistry.panels.evidenceWallet.description",
    glyph: "evidence",
    id: "runs.evidenceWallet",
    kind: "panel",
    labelKey: "surfaceRegistry.panels.evidenceWallet.label",
    parentId: "runs.artifacts",
    permissionKey: "runs.review",
    placement: "panel",
    requiredCapabilities: [],
    resolveHref: ({ runId }) =>
      runId
        ? searchHref(`/runs/${runId}/overview`, {
            surface: "evidence-wallet",
          })
        : null,
    routeId: "surface.runs.evidenceWallet",
    semanticExplanationId: "surface.runs.evidenceWallet",
    workspaceKey: "runsDecisions",
  },
  {
    aliases: ["reading onboarding", "first run", "reviewer onboarding"],
    command: { enabled: true, group: "runSurfaces", requiresContext: "runId" },
    descriptionKey: "surfaceRegistry.panels.readingOnboarding.description",
    glyph: "governance-pass",
    id: "runs.readingOnboarding",
    kind: "panel",
    labelKey: "surfaceRegistry.panels.readingOnboarding.label",
    parentId: "runs.overview",
    permissionKey: "runs.review",
    placement: "panel",
    requiredCapabilities: [],
    resolveHref: ({ runId }) =>
      runId
        ? searchHref(`/runs/${runId}/overview`, {
            surface: "reading-onboarding",
          })
        : null,
    routeId: "surface.runs.readingOnboarding",
    semanticExplanationId: "surface.runs.readingOnboarding",
    visualFixtureKind: "temporal",
    workspaceKey: "runsDecisions",
  },
  {
    aliases: ["bureaucratic forms", "nakaz", "postanova", "vysnovok"],
    command: { enabled: true, group: "runSurfaces", requiresContext: "runId" },
    descriptionKey: "surfaceRegistry.panels.bureaucraticForms.description",
    glyph: "provenance",
    id: "runs.bureaucraticForms",
    kind: "panel",
    labelKey: "surfaceRegistry.panels.bureaucraticForms.label",
    parentId: "runs.artifacts",
    placement: "panel",
    requiredCapabilities: [],
    resolveHref: ({ runId }) =>
      runId
        ? searchHref(`/runs/${runId}/overview`, {
            surface: "bureaucratic-forms",
          })
        : null,
    routeId: "surface.runs.bureaucraticForms",
    semanticExplanationId: "surface.runs.bureaucraticForms",
    workspaceKey: "runsDecisions",
  },
] as const;

export const SURFACE_REGISTRY: readonly SurfaceRegistryEntry[] = [
  ...WORKSPACE_SURFACES,
  ...RUN_DETAIL_SURFACES,
  ...PANEL_SURFACES,
] as const;

export type CommandPaletteSurfaceEntry = SurfaceRegistryEntry & {
  href: string;
};

function hasRequiredContext(
  surface: SurfaceRegistryEntry,
  context: SurfaceHrefContext,
) {
  return surface.command.requiresContext === "runId"
    ? Boolean(context.runId)
    : true;
}

export function getSurfaceById(surfaceId: SurfaceId) {
  return SURFACE_REGISTRY.find((surface) => surface.id === surfaceId) ?? null;
}

export function getSurfacesForWorkspace(workspaceKey: WorkspaceKey) {
  return SURFACE_REGISTRY.filter(
    (surface) => surface.workspaceKey === workspaceKey,
  );
}

export function getNestedSurfacesForWorkspace(workspaceKey: WorkspaceKey) {
  return getSurfacesForWorkspace(workspaceKey).filter(
    (surface) => surface.placement !== "sidebar",
  );
}

export function getChildSurfaces(parentId: SurfaceId) {
  return SURFACE_REGISTRY.filter((surface) => surface.parentId === parentId);
}

export function getRunDetailSurfaceKey(surface: SurfaceRegistryEntry) {
  return surface.kind === "run-tab"
    ? (surface.id.replace("runs.", "") as RunDetailSurfaceKey)
    : null;
}

export function getCommandPaletteSurfaceEntries(
  context: SurfaceHrefContext & {
    canAccessPermission?: (permission: SurfacePermissionKey) => boolean;
    hasCapability?: (capability: string) => boolean;
    isFeatureEnabled?: (featureFlag: FeatureFlagKey) => boolean;
    isWorkspaceAllowed?: (workspaceKey: WorkspaceKey) => boolean;
    isWorkspaceEnabled?: (workspaceKey: WorkspaceKey) => boolean;
  } = {},
): CommandPaletteSurfaceEntry[] {
  return SURFACE_REGISTRY.flatMap((surface) => {
    if (!surface.command.enabled || !hasRequiredContext(surface, context)) {
      return [];
    }

    if (context.isWorkspaceEnabled?.(surface.workspaceKey) === false) {
      return [];
    }

    if (
      surface.featureFlag &&
      context.isFeatureEnabled?.(surface.featureFlag) === false
    ) {
      return [];
    }

    if (context.isWorkspaceAllowed?.(surface.workspaceKey) === false) {
      return [];
    }

    if (
      surface.permissionKey &&
      context.canAccessPermission?.(surface.permissionKey) === false
    ) {
      return [];
    }

    if (
      context.hasCapability &&
      !surface.requiredCapabilities.every((capability) =>
        context.hasCapability?.(capability),
      )
    ) {
      return [];
    }

    const href = surface.resolveHref(context);
    return href ? [{ ...surface, href }] : [];
  });
}
