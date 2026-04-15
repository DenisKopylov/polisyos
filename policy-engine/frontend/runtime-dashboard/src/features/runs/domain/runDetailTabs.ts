import type { CapabilityManifestPayload } from "@/api/validators";
import { isCapabilityEnabled } from "@/lib/capabilities";

export type RunDetailTabPermission = "evidence.review" | "runs.review";
export type RunDetailTab =
  | "overview"
  | "causal"
  | "governance"
  | "evidence"
  | "workflow"
  | "artifacts"
  | "agents"
  | "debug";

export type RunInspectorTabConfig = {
  key: RunDetailTab;
  labelKey: string;
  legacyAliases: readonly string[];
  permissionKey?: RunDetailTabPermission;
  public?: boolean;
  requiredCapabilities?: readonly string[];
  routeId: string;
};

export const RUN_DETAIL_TAB_REGISTRY: readonly RunInspectorTabConfig[] = [
  {
    key: "overview",
    labelKey: "pages.runs.tabs.overview",
    legacyAliases: ["decision"],
    routeId: "runs.tab.overview",
  },
  {
    key: "causal",
    labelKey: "pages.runs.tabs.causal",
    legacyAliases: ["causal", "graph"],
    routeId: "runs.tab.causal",
  },
  {
    key: "governance",
    labelKey: "pages.runs.tabs.governance",
    legacyAliases: ["governance"],
    permissionKey: "runs.review" as const,
    requiredCapabilities: ["evaluator_reports"],
    routeId: "runs.tab.governance",
  },
  {
    key: "evidence",
    labelKey: "pages.runs.tabs.evidence",
    legacyAliases: ["evidence"],
    permissionKey: "evidence.review" as const,
    requiredCapabilities: ["promotion_lane"],
    routeId: "runs.tab.evidence",
  },
  {
    key: "workflow",
    labelKey: "pages.runs.tabs.workflow",
    legacyAliases: ["lineage", "workflow"],
    requiredCapabilities: ["unified_dag"],
    routeId: "runs.tab.workflow",
  },
  {
    key: "artifacts",
    labelKey: "pages.runs.tabs.artifacts",
    legacyAliases: ["artifacts"],
    routeId: "runs.tab.artifacts",
  },
  {
    key: "agents",
    labelKey: "pages.runs.tabs.agents",
    legacyAliases: ["agents", "models"],
    requiredCapabilities: ["natural_language_runs"],
    routeId: "runs.tab.agents",
  },
  {
    key: "debug",
    labelKey: "pages.runs.tabs.debug",
    legacyAliases: ["timeline", "nodes", "debug"],
    routeId: "runs.tab.debug",
  },
] as const;

export const RUN_DETAIL_TABS: RunDetailTab[] = RUN_DETAIL_TAB_REGISTRY.map(
  (tab) => tab.key,
);

export const LEGACY_RUN_DETAIL_TAB_MAP: Record<string, RunDetailTab> =
  Object.fromEntries(
    RUN_DETAIL_TAB_REGISTRY.flatMap((tab) =>
      tab.legacyAliases.map((alias) => [alias, tab.key] as const),
    ),
  ) as Record<string, RunDetailTab>;

export function getVisibleRunInspectorTabs(
  manifest: CapabilityManifestPayload | undefined,
  options?: {
    canAccessTab?: (tab: RunDetailTab) => boolean;
  },
) {
  return RUN_DETAIL_TAB_REGISTRY.filter(
    (tab) =>
      (tab.requiredCapabilities ?? []).every((capability) =>
        isCapabilityEnabled(manifest, capability),
      ) && (options?.canAccessTab ? options.canAccessTab(tab.key) : true),
  );
}
