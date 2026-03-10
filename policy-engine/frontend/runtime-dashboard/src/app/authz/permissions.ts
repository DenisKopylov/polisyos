import type { WorkspaceKey } from "@/app/workspaces";
import type { RunDetailTab } from "@/features/runs";

export const PERMISSION_KEYS = [
  "dashboard.view",
  "evidence.promotions.approve",
  "evidence.promotions.reject",
  "evidence.review",
  "evidence.view",
  "knowledge.view",
  "platform.admin",
  "platform.view",
  "runs.launch",
  "runs.review",
  "runs.view",
] as const;

export type PermissionKey = (typeof PERMISSION_KEYS)[number];

export const WORKSPACE_PERMISSIONS: Partial<Record<WorkspaceKey, PermissionKey>> = {
  commandCenter: "dashboard.view",
  evidenceFabric: "evidence.view",
  lexKnowledge: "knowledge.view",
  platformHealth: "platform.view",
  runsDecisions: "runs.view",
  scenarioComposer: "runs.launch",
};

export const RUN_REVIEW_TAB_PERMISSIONS: Partial<
  Record<RunDetailTab, PermissionKey>
> = {
  evidence: "evidence.review",
  governance: "runs.review",
};

export function getWorkspacePermission(workspaceKey: WorkspaceKey) {
  return WORKSPACE_PERMISSIONS[workspaceKey];
}

export function getRunReviewTabPermission(tab: RunDetailTab) {
  return RUN_REVIEW_TAB_PERMISSIONS[tab];
}
