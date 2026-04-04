import {
  FALLBACK_CAPABILITY_MANIFEST,
  getCapability,
  isCapabilityEnabled,
  readNumericConstraint,
} from "@/lib/capabilities";

describe("capabilities helpers", () => {
  it("reads features from the fallback manifest", () => {
    expect(
      isCapabilityEnabled(FALLBACK_CAPABILITY_MANIFEST, "workflow_runs"),
    ).toBe(true);
    expect(
      isCapabilityEnabled(FALLBACK_CAPABILITY_MANIFEST, "security_admin_layer"),
    ).toBe(false);
    expect(isCapabilityEnabled(undefined, "workflow_runs")).toBe(false);

    expect(
      getCapability(FALLBACK_CAPABILITY_MANIFEST, "transport_summary"),
    ).toMatchObject({
      category: "governance",
      enabled: true,
      key: "transport_summary",
    });
    expect(getCapability(undefined, "transport_summary")).toBeNull();
  });

  it("reads numeric constraints with fallback behavior", () => {
    expect(
      readNumericConstraint(
        FALLBACK_CAPABILITY_MANIFEST,
        "max_parallel_models",
        2,
      ),
    ).toBe(16);
    expect(
      readNumericConstraint(
        {
          ...FALLBACK_CAPABILITY_MANIFEST,
          constraints: {
            ...FALLBACK_CAPABILITY_MANIFEST.constraints,
            max_parallel_models: Number.POSITIVE_INFINITY,
          },
        },
        "max_parallel_models",
        3,
      ),
    ).toBe(3);
    expect(readNumericConstraint(undefined, "missing", 7)).toBe(7);
  });
});
