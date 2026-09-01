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
  admitted_verifiers: Array<{
    ref: string;
    verifier_kind: string;
    provenance_ref: string;
    provenance_digest: string;
    subject_scope: string[];
    prohibited_subjects: string[];
  }>;
  source_set_digest: string;
  identity_boundary: {
    frontmatter_digest: string;
    paragraph_digest: string;
    last_reviewed: string;
    identity_statement: string;
    identity_statement_digest: string;
    anti_roles: Array<{
      role: string;
      display_label: string;
      source_path: string;
      source_digest: string;
    }>;
    derivation_receipt_digests: [string, string];
  };
  custody_appointment_sources: Array<{
    path: string;
    debt_id: string;
    status: "open" | "blocked" | "closed";
    source_content: string;
    content_digest: string;
  }>;
  claims: Array<{
    claim_id: string;
    subject: string | null;
    family: string;
    authoritative_for: string[];
    may_not_use_for: string[];
    effective_state: "supported" | "planned" | "blocked";
    limitations: string[];
    source_bindings: Array<{
      subject: string | null;
      family: string;
      authoritative_for: string[];
      may_not_use_for: string[];
      authority_purpose: string | null;
      closure_signal: string | null;
      content_digest: string;
      coordinate: { path: string };
      owner: { owner: string | null; source_ref: string | null };
      evidence_bindings: Array<{
        subject_binding: string;
        verifier_ref: string;
        verifier_provenance_ref: string;
      }>;
    }>;
  }>;
  projection_groups: Array<{ group_id: string; claim_ids: string[] }>;
  page_a11y_receipt: {
    schema_version: string;
    authority_purpose: string;
    status: string;
    execution_entry_commit: string;
    policy_source_base_commit: string;
    command: string;
  };
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
        rule_version: "policyos.trust.claim_posture_rules.v5",
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

    const unrelatedScope = structuredClone(artifactValue) as MutableArtifact;
    const identityVerifier = unrelatedScope.admitted_verifiers.find(
      (verifier) => verifier.ref.includes("identity-boundary"),
    )!;
    expect(identityVerifier.subject_scope).toEqual(["system_identity"]);
    expect(identityVerifier.prohibited_subjects).toContain(
      "universal_custody_commitment",
    );
    const identityClaim = unrelatedScope.claims.find(
      (claim) => claim.subject === "system_identity",
    )!;
    identityClaim.subject = "novel_unrelated_subject";
    identityClaim.authoritative_for = ["novel_unrelated_subject"];
    const identityBinding = identityClaim.source_bindings[0]!;
    identityBinding.subject = "novel_unrelated_subject";
    identityBinding.authoritative_for = ["novel_unrelated_subject"];
    identityBinding.authority_purpose = "novel_unrelated_subject";
    const reboundEvidence = identityBinding.evidence_bindings[0]!;
    reboundEvidence.subject_binding = "novel_unrelated_subject";
    expect((await loadCandidate(recomputeDigests(unrelatedScope))).status).toBe(
      "unavailable",
    );
  });

  it("rejects rebound identity content and anti-role derivation drift", async () => {
    const removed = structuredClone(artifactValue) as MutableArtifact;
    removed.identity_boundary.anti_roles =
      removed.identity_boundary.anti_roles.filter(
        (antiRole) => antiRole.display_label !== "CRM",
      );
    const reboundReceipt = sha256(
      canonicalJson(
        removed.identity_boundary.anti_roles.map(
          (antiRole) => antiRole.display_label,
        ),
      ),
    );
    removed.identity_boundary.derivation_receipt_digests = [
      reboundReceipt,
      reboundReceipt,
    ];
    const identityVerifier = removed.admitted_verifiers.find(
      (verifier) => verifier.verifier_kind === "identity_boundary_derivation",
    )!;
    const provenanceDigest = sha256(
      canonicalJson([
        removed.identity_boundary.frontmatter_digest,
        removed.identity_boundary.identity_statement_digest,
        removed.identity_boundary.paragraph_digest,
        ...removed.identity_boundary.derivation_receipt_digests,
      ]),
    );
    identityVerifier.provenance_digest = provenanceDigest;
    identityVerifier.provenance_ref = `provenance:identity_boundary_derivation:${provenanceDigest}`;
    for (const claim of removed.claims) {
      for (const binding of claim.source_bindings) {
        for (const evidence of binding.evidence_bindings) {
          if (evidence.verifier_ref === identityVerifier.ref) {
            evidence.verifier_provenance_ref = identityVerifier.provenance_ref;
          }
        }
      }
    }
    expect((await loadCandidate(recomputeDigests(removed))).status).toBe(
      "unavailable",
    );

    const reordered = structuredClone(artifactValue) as MutableArtifact;
    reordered.identity_boundary.anti_roles.reverse();
    expect((await loadCandidate(recomputeDigests(reordered))).status).toBe(
      "unavailable",
    );

    const receipt = structuredClone(artifactValue) as MutableArtifact;
    receipt.identity_boundary.derivation_receipt_digests[0] = `sha256:${"4".repeat(64)}`;
    expect((await loadCandidate(recomputeDigests(receipt))).status).toBe(
      "unavailable",
    );

    const statement = structuredClone(artifactValue) as MutableArtifact;
    statement.identity_boundary.identity_statement =
      "PolicyOS is a case-management system.";
    expect((await loadCandidate(recomputeDigests(statement))).status).toBe(
      "unavailable",
    );
  });

  it("binds the historical page receipt to its exact source base and command", async () => {
    const candidate = structuredClone(artifactValue) as MutableArtifact;
    expect(candidate.page_a11y_receipt.policy_source_base_commit).toBe(
      "f935e0c2e9359bc1202ce5d36ea706de58f7aaab",
    );
    expect(candidate.page_a11y_receipt.command).toBe(
      "PLAYWRIGHT_JSON_OUTPUT_FILE=<receipt-relative-output> corepack pnpm --filter @polisyos/runtime-dashboard exec playwright test e2e/a11y --project=chromium --reporter=json",
    );
    candidate.page_a11y_receipt.policy_source_base_commit = "0".repeat(40);
    expect((await loadCandidate(recomputeDigests(candidate))).status).toBe(
      "unavailable",
    );
  });

  it.each([
    "page receipt",
    "accessibility selector",
    "denied receipt counts",
    "coordinated source omission",
  ])(
    "replays carried content and complete source receipts for %s",
    async (caseName) => {
      const candidate = structuredClone(artifactValue) as MutableArtifact & {
        accessibility_document: {
          bindings: Array<{ key: string; value: string }>;
        };
        page_a11y_receipt: MutableArtifact["page_a11y_receipt"] & {
          passed: number;
          failed: number;
          failures: unknown[];
        };
        source_inventory: Array<{ path: string }>;
        ast_derivation: { may_not_use_for_raw_file_count: number };
        token_derivation: { may_not_use_for_raw_file_count: number };
      };
      if (caseName === "page receipt") {
        candidate.page_a11y_receipt.passed = 24;
        candidate.page_a11y_receipt.failed = 0;
        candidate.page_a11y_receipt.failures = [];
      } else if (caseName === "accessibility selector") {
        candidate.accessibility_document.bindings.find(
          (binding) => binding.key === "audit_type",
        )!.value = "external audit";
      } else if (caseName === "denied receipt counts") {
        candidate.ast_derivation.may_not_use_for_raw_file_count += 1;
        candidate.token_derivation.may_not_use_for_raw_file_count += 1;
      } else {
        const omittedPath = "src/polisyos/core/contracts/rule_evolution.py";
        const omittedIds = new Set(
          candidate.claims
            .filter((row) =>
              row.source_bindings.some(
                (binding) => binding.coordinate.path === omittedPath,
              ),
            )
            .map((row) => row.claim_id),
        );
        expect(omittedIds.size).toBeGreaterThan(0);
        candidate.source_inventory = candidate.source_inventory.filter(
          (row) => row.path !== omittedPath,
        );
        candidate.admitted_sources = candidate.admitted_sources.filter(
          (member) => member.path !== omittedPath,
        );
        candidate.claims = candidate.claims.filter(
          (row) => !omittedIds.has(row.claim_id),
        );
        for (const group of candidate.projection_groups) {
          group.claim_ids = group.claim_ids.filter(
            (claimId) => !omittedIds.has(claimId),
          );
        }
      }
      expect((await loadCandidate(recomputeDigests(candidate))).status).toBe(
        "unavailable",
      );
    },
  );

  it.each([
    "symbol",
    "column",
    "use_kind",
    "field_name",
    "values",
    "order",
    "denied_only",
  ])(
    "binds full denied-site coordinates and values for %s",
    async (caseName) => {
      type MutableDeniedSite = {
        coordinate: {
          path: string;
          symbol: string | null;
          column: number;
          field_name: string;
          use_kind: string;
        };
        values: string[];
      };
      const candidate = structuredClone(artifactValue) as MutableArtifact & {
        ast_derivation: { may_not_use_for_sites: MutableDeniedSite[] };
        token_derivation: { may_not_use_for_sites: MutableDeniedSite[] };
      };
      for (const receipt of [
        candidate.ast_derivation,
        candidate.token_derivation,
      ]) {
        const sites = receipt.may_not_use_for_sites;
        if (caseName === "symbol")
          sites[0]!.coordinate.symbol = "fabricated_symbol";
        else if (caseName === "column") sites[0]!.coordinate.column += 17;
        else if (caseName === "use_kind")
          sites[0]!.coordinate.use_kind = "consumer";
        else if (caseName === "field_name")
          sites[0]!.coordinate.field_name = "authoritative_for";
        else if (caseName === "values") sites[0]!.values = ["claim_authority"];
        else if (caseName === "order")
          [sites[0], sites[1]] = [sites[1], sites[0]];
        else
          sites.find(
            (site) =>
              site.coordinate.path === "src/polisyos/core/contracts/search.py",
          )!.coordinate.symbol = "fabricated_denied_only_symbol";
      }
      expect((await loadCandidate(recomputeDigests(candidate))).status).toBe(
        "unavailable",
      );
    },
  );

  it.each(["omitted", "duplicated"])(
    "requires exactly one MACHINE freshness limitation when %s",
    async (caseName) => {
      const candidate = structuredClone(artifactValue) as MutableArtifact & {
        machine_admission_boundary: { limitation_refs: string[] };
      };
      const limitation =
        candidate.machine_admission_boundary.limitation_refs[0]!;
      candidate.machine_admission_boundary.limitation_refs =
        caseName === "omitted" ? [] : [limitation, limitation];
      expect((await loadCandidate(recomputeDigests(candidate))).status).toBe(
        "unavailable",
      );
    },
  );

  it("rejects a rebound planned row when one producer arm loses its closure signal", async () => {
    const candidate = structuredClone(artifactValue) as MutableArtifact;
    const custody = candidate.claims.find(
      (claim) => claim.subject === "universal_custody_commitment",
    )!;
    expect(custody.source_bindings).toHaveLength(3);
    custody.source_bindings.find(
      (binding) => binding.owner.owner === "team-scientist",
    )!.closure_signal = null;
    expect((await loadCandidate(recomputeDigests(candidate))).status).toBe(
      "unavailable",
    );

    const fabricated = structuredClone(artifactValue) as MutableArtifact;
    const fabricatedCustody = fabricated.claims.find(
      (claim) => claim.subject === "universal_custody_commitment",
    )!;
    const fabricatedArm = fabricatedCustody.source_bindings.find(
      (binding) => binding.owner.owner === "team-runtime",
    )!;
    fabricatedArm.owner.owner = "team-fabricated";
    fabricatedArm.closure_signal = "python -c fabricated_owner_and_closure";
    expect((await loadCandidate(recomputeDigests(fabricated))).status).toBe(
      "unavailable",
    );
  });

  it("rejects an invented planned claim absent from the producer inventory", async () => {
    const candidate = structuredClone(artifactValue) as MutableArtifact;
    const custody = candidate.claims.find(
      (claim) => claim.subject === "universal_custody_commitment",
    )!;
    const fabricated = structuredClone(custody);
    const subject = "fabricated_posture_claim";
    fabricated.claim_id = `claim-posture:${sha256(subject).slice("sha256:".length)}`;
    fabricated.subject = subject;
    fabricated.family = "methodology";
    fabricated.authoritative_for = [subject];
    for (const binding of fabricated.source_bindings) {
      binding.subject = subject;
      binding.family = "methodology";
      binding.authoritative_for = [subject];
      binding.authority_purpose = subject;
    }
    candidate.claims.push(fabricated);
    candidate.claims.sort((left, right) =>
      left.claim_id.localeCompare(right.claim_id, "en"),
    );
    for (const groupId of ["limitations", "methodology"]) {
      const group = candidate.projection_groups.find(
        (item) => item.group_id === groupId,
      )!;
      group.claim_ids.push(fabricated.claim_id);
      group.claim_ids.sort((left, right) => left.localeCompare(right, "en"));
    }

    expect((await loadCandidate(recomputeDigests(candidate))).status).toBe(
      "unavailable",
    );
  });

  it("rejects a rebound fixed identity arm that differs from its ratified basis", async () => {
    const candidate = structuredClone(artifactValue) as MutableArtifact;
    const identity = candidate.claims.find(
      (claim) => claim.subject === "system_identity",
    )!;
    const binding = identity.source_bindings[0]!;
    const fabricatedPurpose = "fabricated_identity_purpose";
    identity.family = "fabricated_methodology";
    identity.authoritative_for = [fabricatedPurpose];
    identity.may_not_use_for = ["fabricated_identity_denial"];
    binding.family = identity.family;
    binding.authoritative_for = [...identity.authoritative_for];
    binding.may_not_use_for = [...identity.may_not_use_for];
    binding.authority_purpose = fabricatedPurpose;

    expect((await loadCandidate(recomputeDigests(candidate))).status).toBe(
      "unavailable",
    );
  });

  it("rejects custody content drift while its marker strings remain unchanged", async () => {
    const candidate = structuredClone(artifactValue) as MutableArtifact;
    const custody = candidate.claims.find(
      (claim) => claim.subject === "universal_custody_commitment",
    )!;
    const markerSnapshot = custody.source_bindings.map((binding) => ({
      closure_signal: binding.closure_signal,
      owner: binding.owner.owner,
    }));
    const source = candidate.custody_appointment_sources[0]!;
    source.source_content += " ";
    expect(
      custody.source_bindings.map((binding) => ({
        closure_signal: binding.closure_signal,
        owner: binding.owner.owner,
      })),
    ).toEqual(markerSnapshot);

    expect((await loadCandidate(recomputeDigests(candidate))).status).toBe(
      "unavailable",
    );
  });

  it("rejects a MACHINE limitation omission after digest rebinding", async () => {
    const candidate = structuredClone(artifactValue) as MutableArtifact;
    const limited = candidate.claims.find(
      (claim) => claim.limitations.length > 0,
    )!;
    limited.limitations.shift();
    expect((await loadCandidate(recomputeDigests(candidate))).status).toBe(
      "unavailable",
    );
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
