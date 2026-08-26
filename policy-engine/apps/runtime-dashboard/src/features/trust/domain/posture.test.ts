import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { resolve } from "node:path";

import { describe, expect, it, vi } from "vitest";

const artifactBytes = readFileSync(
  resolve(process.cwd(), "public/atlas/trust-claim-posture.v1.json"),
);
const artifactValue = JSON.parse(artifactBytes.toString("utf8")) as Record<
  string,
  unknown
>;

type MutableArtifact = Record<string, unknown> & {
  admitted_sources: Array<{ path: string; content_digest: string }>;
  source_set_digest: string;
  identity_boundary: { last_reviewed: string };
  claims: Array<{
    claim_id: string;
    subject: string | null;
    family: string;
    effective_state: "supported" | "planned" | "blocked";
    source_bindings: Array<{
      content_digest: string;
      coordinate: { path: string };
      evidence_bindings: Array<{
        verifier_ref: string;
        verifier_provenance_ref: string;
      }>;
    }>;
  }>;
  projection_groups: Array<{ group_id: string; claim_ids: string[] }>;
  payload_digest: string;
};

function canonicalJson(value: unknown): string {
  if (
    value === null ||
    typeof value === "boolean" ||
    typeof value === "number"
  ) {
    return JSON.stringify(value);
  }
  if (typeof value === "string") return JSON.stringify(value);
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(",")}]`;
  if (typeof value === "object") {
    const record = value as Record<string, unknown>;
    return `{${Object.keys(record)
      .sort()
      .map((key) => `${JSON.stringify(key)}:${canonicalJson(record[key])}`)
      .join(",")}}`;
  }
  throw new TypeError("unsupported canonical JSON value");
}

function sha256(value: string): string {
  return `sha256:${createHash("sha256").update(value, "utf8").digest("hex")}`;
}

function recomputeDigests(value: MutableArtifact): MutableArtifact {
  value.source_set_digest = sha256(
    canonicalJson(
      value.admitted_sources.map((member) => [
        member.path,
        member.content_digest,
      ]),
    ),
  );
  const { payload_digest: _payloadDigest, ...payload } = value;
  value.payload_digest = sha256(canonicalJson(payload));
  return value;
}

async function loadCandidate(value: MutableArtifact) {
  const { loadPosture } = await import("./loadPosture");
  return loadPosture(
    vi.fn(async () =>
      Promise.resolve(
        new Response(JSON.stringify(value), {
          headers: { "content-type": "application/json" },
          status: 200,
        }),
      ),
    ),
  );
}

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

    expect(fetcher).toHaveBeenCalledWith("/atlas/trust-claim-posture.v1.json", {
      cache: "no-store",
      headers: { Accept: "application/json" },
    });
    expect(result.status).toBe("available");
    if (result.status === "available") {
      expect(result.rawBytes).toEqual(new Uint8Array(artifactBytes));
      expect(result.register.schema_version).toBe(
        "policyos.trust.claim_posture_register.v1",
      );
    }
  });

  it("rejects a valid-enum effective-state relabel before and after payload rebinding", async () => {
    const staleDigest = structuredClone(artifactValue) as MutableArtifact;
    const row = staleDigest.claims.find(
      (claim) => claim.effective_state === "supported",
    );
    expect(row).toBeDefined();
    row!.effective_state = "blocked";

    expect((await loadCandidate(staleDigest)).status).toBe("unavailable");

    const reboundDigest = recomputeDigests(
      structuredClone(staleDigest) as MutableArtifact,
    );
    expect((await loadCandidate(reboundDigest)).status).toBe("unavailable");
  });

  it.each([
    [
      "authored extra",
      (value: MutableArtifact) => {
        value.projection_groups[0]!.claim_ids.push(value.claims[0]!.claim_id);
      },
    ],
    [
      "orphan",
      (value: MutableArtifact) => {
        value.projection_groups[0]!.claim_ids[0] = "claim-posture:orphan";
      },
    ],
    [
      "empty",
      (value: MutableArtifact) => {
        value.projection_groups[0]!.claim_ids = [];
      },
    ],
    [
      "wrong group",
      (value: MutableArtifact) => {
        const accessibility = value.projection_groups.find(
          (group) => group.group_id === "accessibility",
        )!;
        const custody = value.projection_groups.find(
          (group) => group.group_id === "custody",
        )!;
        custody.claim_ids.push(accessibility.claim_ids.shift()!);
      },
    ],
  ])(
    "rejects %s projection membership with a recomputed digest",
    async (_name, mutate) => {
      const candidate = structuredClone(artifactValue) as MutableArtifact;
      mutate(candidate);
      expect((await loadCandidate(recomputeDigests(candidate))).status).toBe(
        "unavailable",
      );
    },
  );

  it("rejects source membership and evidence/verifier binding drift with recomputed digests", async () => {
    const sourceBinding = structuredClone(artifactValue) as MutableArtifact;
    const bound = sourceBinding.claims.find(
      (claim) => claim.source_bindings.length > 0,
    )!.source_bindings[0]!;
    bound.content_digest = `sha256:${"0".repeat(64)}`;
    expect((await loadCandidate(recomputeDigests(sourceBinding))).status).toBe(
      "unavailable",
    );

    const admittedSource = structuredClone(artifactValue) as MutableArtifact;
    const admittedPath =
      admittedSource.claims[0]!.source_bindings[0]!.coordinate.path;
    admittedSource.admitted_sources.find(
      (member) => member.path === admittedPath,
    )!.content_digest = `sha256:${"1".repeat(64)}`;
    expect((await loadCandidate(recomputeDigests(admittedSource))).status).toBe(
      "unavailable",
    );

    const evidenceVerifier = structuredClone(artifactValue) as MutableArtifact;
    const evidence = evidenceVerifier.claims
      .find((claim) => claim.effective_state === "supported")!
      .source_bindings.flatMap((binding) => binding.evidence_bindings)[0]!;
    evidence.verifier_provenance_ref = "provenance:forged";
    expect(
      (await loadCandidate(recomputeDigests(evidenceVerifier))).status,
    ).toBe("unavailable");
  });

  it("recomputes both canonical root digests and fails unavailable without browser crypto", async () => {
    const sourceDigestDrift = structuredClone(artifactValue) as MutableArtifact;
    sourceDigestDrift.source_set_digest = `sha256:${"2".repeat(64)}`;
    const { payload_digest: _oldPayloadDigest, ...payload } = sourceDigestDrift;
    sourceDigestDrift.payload_digest = sha256(canonicalJson(payload));
    expect((await loadCandidate(sourceDigestDrift)).status).toBe("unavailable");

    const payloadDigestDrift = structuredClone(
      artifactValue,
    ) as MutableArtifact;
    payloadDigestDrift.payload_digest = `sha256:${"3".repeat(64)}`;
    expect((await loadCandidate(payloadDigestDrift)).status).toBe(
      "unavailable",
    );

    vi.stubGlobal("crypto", undefined);
    expect(
      (await loadCandidate(structuredClone(artifactValue) as MutableArtifact))
        .status,
    ).toBe("unavailable");
    vi.unstubAllGlobals();
  });

  it.each([
    ["non-leap February 29", "2026-02-29"],
    ["February 30", "2028-02-30"],
    ["month 13", "2026-13-01"],
  ])(
    "rejects rebound-digest impossible Gregorian date %s",
    async (_name, date) => {
      const candidate = structuredClone(artifactValue) as MutableArtifact;
      candidate.identity_boundary.last_reviewed = date;
      expect((await loadCandidate(recomputeDigests(candidate))).status).toBe(
        "unavailable",
      );
    },
  );

  it.each([
    ["empty", new Uint8Array(), 200],
    ["malformed", new TextEncoder().encode("{not-json"), 200],
    ["http", artifactBytes, 503],
  ])(
    "fails unavailable for %s response bytes",
    async (_name, bytes, status) => {
      const [, { loadPosture }] = await loadDomain();
      const result = await loadPosture(
        vi.fn(async () => Promise.resolve(new Response(bytes, { status }))),
      );
      expect(result.status).toBe("unavailable");
    },
  );
});
