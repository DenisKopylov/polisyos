import {
  isExecutionPolicyEnabled,
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
  fallback_rules: {
    execution_policy: {
      auto_materialization: false,
      multimodel_nl: true,
      producer_ref: "runtime/http/services/_control_contracts.py",
      required_preflight: true,
    },
  },
  workspaces: [],
  features: [],
  constraints: {},
};

describe("capabilities helpers", () => {
  it("test_capability_discovery_accepts_only_issued_owner_manifest", () => {
    expectTypeOf(ownerManifest).not.toExtend<CapabilityDiscovery>();
    expect(isIssuedCapabilityDiscovery(ownerManifest)).toBe(false);
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

  it("reads execution policy only from the current policy projection", () => {
    expect(isExecutionPolicyEnabled(ownerManifest, "multimodel_nl")).toBe(true);
    expect(
      isExecutionPolicyEnabled(ownerManifest, "auto_materialization"),
    ).toBe(false);
    expect(
      isExecutionPolicyEnabled(
        {
          ...ownerManifest,
          fallback_rules: {},
        },
        "multimodel_nl",
      ),
    ).toBe(false);
  });
});
