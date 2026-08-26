import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it, vi } from "vitest";

const artifactBytes = readFileSync(
  resolve(process.cwd(), "public/atlas/trust-claim-posture.v1.json"),
);
const artifactValue = JSON.parse(artifactBytes.toString("utf8")) as Record<
  string,
  unknown
>;

async function loadDomain() {
  return Promise.all([import("./posture"), import("./loadPosture")]);
}

describe("trust posture artifact admission", () => {
  it("accepts the complete committed artifact and rejects nested or version novelty", async () => {
    const [{ claimPostureRegisterSchema }] = await loadDomain();

    expect(claimPostureRegisterSchema.safeParse(artifactValue).success).toBe(
      true,
    );

    const unknownNested = structuredClone(artifactValue) as {
      claims: Array<{
        source_bindings: Array<{ coordinate: Record<string, unknown> }>;
      }>;
    };
    unknownNested.claims[0]!.source_bindings[0]!.coordinate.unearned = true;
    expect(claimPostureRegisterSchema.safeParse(unknownNested).success).toBe(
      false,
    );

    const missingNested = structuredClone(artifactValue) as {
      claims: Array<{
        source_bindings: Array<{ coordinate: Record<string, unknown> }>;
      }>;
    };
    delete missingNested.claims[0]!.source_bindings[0]!.coordinate.path;
    expect(claimPostureRegisterSchema.safeParse(missingNested).success).toBe(
      false,
    );

    expect(
      claimPostureRegisterSchema.safeParse({
        ...artifactValue,
        schema_version: "policyos.trust.claim_posture_register.v2",
      }).success,
    ).toBe(false);
    expect(
      claimPostureRegisterSchema.safeParse({
        ...artifactValue,
        rule_version: "policyos.trust.claim_posture_rules.v4",
      }).success,
    ).toBe(false);

    const malformedState = structuredClone(artifactValue) as {
      claims: Array<{ effective_state: string }>;
    };
    malformedState.claims[0]!.effective_state = "review_required";
    expect(claimPostureRegisterSchema.safeParse(malformedState).success).toBe(
      false,
    );

    const malformedEstablishment = structuredClone(artifactValue) as {
      claims: Array<{
        source_bindings: Array<{
          predicates: Array<{ establishment_class: string }>;
        }>;
      }>;
    };
    malformedEstablishment.claims[0]!.source_bindings[0]!.predicates[0]!.establishment_class =
      "declared";
    expect(
      claimPostureRegisterSchema.safeParse(malformedEstablishment).success,
    ).toBe(false);
  });

  it("captures response bytes before strict validation with no cache or fallback", async () => {
    const [, { loadPosture }] = await loadDomain();
    const fetcher = vi.fn(async () =>
      Promise.resolve(
        new Response(artifactBytes, {
          headers: { "content-type": "application/json" },
          status: 200,
        }),
      ),
    );

    const result = await loadPosture(fetcher);

    expect(fetcher).toHaveBeenCalledWith(
      "/atlas/trust-claim-posture.v1.json",
      {
        cache: "no-store",
        headers: { Accept: "application/json" },
      },
    );
    expect(result.status).toBe("available");
    if (result.status === "available") {
      expect(result.rawBytes).toEqual(new Uint8Array(artifactBytes));
      expect(result.register.schema_version).toBe(
        "policyos.trust.claim_posture_register.v1",
      );
    }
  });

  it.each([
    ["empty", new Uint8Array(), 200],
    ["malformed", new TextEncoder().encode("{not-json"), 200],
    ["http", artifactBytes, 503],
  ])("fails unavailable for %s response bytes", async (_name, bytes, status) => {
    const [, { loadPosture }] = await loadDomain();
    const result = await loadPosture(
      vi.fn(async () => Promise.resolve(new Response(bytes, { status }))),
    );
    expect(result.status).toBe("unavailable");
  });
});
