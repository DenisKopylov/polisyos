import type { CapabilityManifestPayload } from "@/api/validators";
import {
  RUN_DETAIL_SURFACES,
  type RunDetailSurfaceKey,
  type SurfacePermissionKey,
} from "@/app/surfaces/surfaceRegistry";
import { isCapabilityEnabled } from "@/shared/lib/capabilities";
import type { FeatureFlagKey } from "@/shared/lib/featureFlags";

export type RunDetailTabPermission = Extract<
  SurfacePermissionKey,
  "evidence.review" | "runs.review"
>;
export type RunDetailTab = RunDetailSurfaceKey;

export type RunInspectorTabConfig = {
  featureFlag?: FeatureFlagKey;
  key: RunDetailTab;
  labelKey: string;
  legacyAliases: readonly string[];
  permissionKey?: RunDetailTabPermission;
  public?: boolean;
  requiredCapabilities?: readonly string[];
  routeId: string;
};

export const RUN_DETAIL_TAB_REGISTRY: readonly RunInspectorTabConfig[] =
  RUN_DETAIL_SURFACES.map((surface) => ({
    featureFlag: surface.featureFlag,
    key: surface.id.replace("runs.", "") as RunDetailTab,
    labelKey: surface.labelKey,
    legacyAliases: surface.legacyAliases ?? surface.aliases,
    permissionKey: surface.permissionKey as RunDetailTabPermission | undefined,
    requiredCapabilities: surface.requiredCapabilities,
    routeId: surface.routeId ?? surface.id,
  }));

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
    isFeatureEnabled?: (featureFlag: FeatureFlagKey) => boolean;
  },
) {
  return RUN_DETAIL_TAB_REGISTRY.filter(
    (tab) =>
      (!tab.featureFlag ||
        options?.isFeatureEnabled?.(tab.featureFlag) !== false) &&
      (tab.requiredCapabilities ?? []).every((capability) =>
        isCapabilityEnabled(manifest, capability),
      ) &&
      (options?.canAccessTab ? options.canAccessTab(tab.key) : true),
  );
}
