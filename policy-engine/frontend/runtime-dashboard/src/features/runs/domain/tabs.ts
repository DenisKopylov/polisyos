import type { CapabilityManifestPayload } from "@/api/validators";
import { isCapabilityEnabled } from "@/lib/capabilities";
import type { RunDetailTab } from "@/features/runs/routes/useRunDetailSummary";

export type RunInspectorTabConfig = {
  key: RunDetailTab;
  labelKey: string;
  requiredCapabilities?: string[];
};

export const RUN_INSPECTOR_TABS: RunInspectorTabConfig[] = [
  { key: "overview", labelKey: "pages.runs.tabs.overview" },
  {
    key: "governance",
    labelKey: "pages.runs.tabs.governance",
    requiredCapabilities: ["evaluator_reports"],
  },
  {
    key: "evidence",
    labelKey: "pages.runs.tabs.evidence",
    requiredCapabilities: ["promotion_lane"],
  },
  {
    key: "workflow",
    labelKey: "pages.runs.tabs.workflow",
    requiredCapabilities: ["unified_dag"],
  },
  { key: "artifacts", labelKey: "pages.runs.tabs.artifacts" },
  {
    key: "agents",
    labelKey: "pages.runs.tabs.agents",
    requiredCapabilities: ["natural_language_runs"],
  },
  { key: "debug", labelKey: "pages.runs.tabs.debug" },
];

export function getVisibleRunInspectorTabs(
  manifest: CapabilityManifestPayload | undefined,
  options?: {
    canAccessTab?: (tab: RunDetailTab) => boolean;
  },
) {
  return RUN_INSPECTOR_TABS.filter(
    (tab) =>
      (tab.requiredCapabilities ?? []).every((capability) =>
        isCapabilityEnabled(manifest, capability),
      ) && (options?.canAccessTab ? options.canAccessTab(tab.key) : true),
  );
}
