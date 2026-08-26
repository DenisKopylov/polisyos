import {
  type PermissionKey,
  WORKSPACE_PERMISSIONS,
} from "@/app/authz/AuthzProvider";
import { RUN_DETAIL_TAB_REGISTRY, type RunDetailTab } from "@/features/runs";

export {
  getWorkspacePermission,
  type PermissionKey,
  WORKSPACE_PERMISSIONS,
} from "@/app/authz/AuthzProvider";

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
] as const satisfies readonly PermissionKey[];

export const RUN_REVIEW_TAB_PERMISSIONS: Partial<
  Record<RunDetailTab, PermissionKey>
> = Object.fromEntries(
  RUN_DETAIL_TAB_REGISTRY.flatMap((tab) =>
    tab.permissionKey ? [[tab.key, tab.permissionKey]] : [],
  ),
) as Partial<Record<RunDetailTab, PermissionKey>>;

export function getRunReviewTabPermission(tab: RunDetailTab) {
  return RUN_REVIEW_TAB_PERMISSIONS[tab];
}
