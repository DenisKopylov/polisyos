import {
  getCapability,
  isCapabilityEnabled,
  readNumericConstraint,
} from "@/shared/lib/capabilities";
import {
  type CapabilityDiscovery,
  isIssuedCapabilityDiscovery,
} from "@/api/hooks/useCapabilities";
import type { CapabilityManifestPayload } from "@/api/validators";

const ownerManifest: CapabilityManifestPayload = {
  meta: {
    request_id: "owner-capability-manifest",
    generated_at: "2026-08-09T00:00:00Z",
    source_kinds: ["core_run"],
  },
  runtime_api_version: "2.0.0",
  shell_flavor: "atlas",
  default_execution_profile: "dev",
  default_locale: "en",
  supported_execution_profiles: ["dev"],
  supported_locales: ["en"],
  state_store_backend: "sqlite",
  worker_backend: "embedded",
  workspaces: [],
  features: [
    {
      key: "workflow_runs",
      label: "Workflow runs",
      description: "Owner-issued feature.",
      category: "runs",
      enabled: true,
      stage: "active",
    },
  ],
  constraints: {},
};

describe("capabilities helpers", () => {
  it("test_capability_discovery_accepts_only_issued_owner_manifest", () => {
    expectTypeOf(ownerManifest).not.toExtend<CapabilityDiscovery>();
    expect(isIssuedCapabilityDiscovery(ownerManifest)).toBe(false);
  });

  it("reads features from an owner manifest", () => {
    expect(isCapabilityEnabled(ownerManifest, "workflow_runs")).toBe(true);
    expect(isCapabilityEnabled(ownerManifest, "security_admin_layer")).toBe(
      false,
    );
    expect(isCapabilityEnabled(undefined, "workflow_runs")).toBe(false);

    expect(getCapability(ownerManifest, "workflow_runs")).toMatchObject({
      category: "runs",
      enabled: true,
      key: "workflow_runs",
    });
    expect(getCapability(undefined, "workflow_runs")).toBeNull();
  });

  it("reads numeric constraints with fallback behavior", () => {
    expect(
      readNumericConstraint(
        {
          ...ownerManifest,
          constraints: { max_parallel_models: 16 },
        },
        "max_parallel_models",
        2,
      ),
    ).toBe(16);
    expect(
      readNumericConstraint(
        {
          constraints: {
            max_parallel_models: Number.POSITIVE_INFINITY,
          },
          ...ownerManifest,
        },
        "max_parallel_models",
        3,
      ),
    ).toBe(3);
    expect(readNumericConstraint(undefined, "missing", 7)).toBe(7);
  });
});
