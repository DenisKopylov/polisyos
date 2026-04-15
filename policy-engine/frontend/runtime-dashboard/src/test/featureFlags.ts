import {
  DEFAULT_FEATURE_FLAGS,
  type FeatureFlagOverrides,
  type FeatureFlags,
} from "@/lib/featureFlags";

export function buildFeatureFlags(
  overrides?: FeatureFlagOverrides,
): FeatureFlags {
  return {
    ...DEFAULT_FEATURE_FLAGS,
    ...overrides,
  };
}
