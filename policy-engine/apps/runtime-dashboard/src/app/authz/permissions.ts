import type { RuntimePermission } from "@polisyos/runtime-api-client";

import type { WorkspaceKey } from "@/app/workspaces";
import { RUN_DETAIL_TAB_REGISTRY, type RunDetailTab } from "@/features/runs";

export const PERMISSION_KEYS = [
  "dashboard.view",
  "evidence.promotions.approve",
  "evidence.promotions.reject",
  "evidence.review",
  "evidence.view",
  "knowledge.view",
  "mode.analyst",
  "platform.admin",
  "platform.view",
  "runs.launch",
  "runs.review",
  "runs.view",
] as const satisfies readonly RuntimePermission[];

export type PermissionKey = RuntimePermission;

export const WORKSPACE_PERMISSIONS: Partial<
  Record<WorkspaceKey, PermissionKey>
> = {
  commandCenter: "dashboard.view",
  evidenceFabric: "evidence.view",
  lexKnowledge: "knowledge.view",
  platformHealth: "platform.view",
  runsDecisions: "runs.view",
  scenarioComposer: "runs.launch",
};

export const RUN_REVIEW_TAB_PERMISSIONS: Partial<
  Record<RunDetailTab, PermissionKey>
> = Object.fromEntries(
  RUN_DETAIL_TAB_REGISTRY.flatMap((tab) =>
    tab.permissionKey ? [[tab.key, tab.permissionKey]] : [],
  ),
) as Partial<Record<RunDetailTab, PermissionKey>>;

export function getWorkspacePermission(workspaceKey: WorkspaceKey) {
  return WORKSPACE_PERMISSIONS[workspaceKey];
}

export function getRunReviewTabPermission(tab: RunDetailTab) {
  return RUN_REVIEW_TAB_PERMISSIONS[tab];
}
