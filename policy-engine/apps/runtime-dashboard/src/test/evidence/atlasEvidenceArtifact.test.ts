import { describe, expect, it } from "vitest";

import {
  ATLAS_EVIDENCE_DENIED_USES,
  ATLAS_EVIDENCE_PAYLOAD_SCHEMA,
  ATLAS_EVIDENCE_RECEIPT_SCHEMA,
  ATLAS_EVIDENCE_STORAGE_CONVENTION,
  assertAtlasEvidencePayloadBinding,
  atlasEvidencePayloadSchema,
  atlasEvidenceReceiptSchema,
  parseAtlasEvidenceReceipt,
  type AtlasEvidencePayload,
  type AtlasEvidenceReceipt,
} from "./atlasEvidenceArtifact";

const PAYLOAD_ARTIFACT_ID = `sha256:${"a".repeat(64)}`;
const REPOSITORY_REVISION = "b".repeat(40);

function validReceipt(): AtlasEvidenceReceipt {
  return {
    receipt_schema: ATLAS_EVIDENCE_RECEIPT_SCHEMA,
    authority: {
      authoritative_for: ["atlas_evidence_capture"],
      may_not_use_for: [...ATLAS_EVIDENCE_DENIED_USES],
    },
    evidence_kind: "automated_browser",
    subject: {
      kind: "component_state",
      subject_id: "badge-neutral",
      state_id: "neutral",
    },
    rule: {
      rule_id: "wcag-2.2-aa-color-contrast",
      rule_version: "axe-core@4.11.0",
    },
    provenance: {
      producer: {
        producer_id: "atlas-storybook-axe-runner",
        producer_version: "1.0.0",
      },
      verifier: {
        verifier_id: "atlas-opaque-background-classifier",
        verifier_version: "1.0.0",
      },
      repository_revision: REPOSITORY_REVISION,
      command_argv: [
        "corepack",
        "pnpm",
        "exec",
        "vitest",
        "run",
        "--config",
        "vitest.storybook.config.ts",
      ],
      predicate_provenance: "recomputed",
    },
    audiences: ["REVIEWER", "EXPERT", "MACHINE"],
    times: {
      observed_at: "2026-08-11T09:00:00.000Z",
      collected_at: "2026-08-11T09:00:01.000Z",
      verified_at: "2026-08-11T09:00:02.000Z",
    },
    result: {
      outcome: "pass",
      findings: [],
    },
    evidence_payload_ref: {
      artifact_id: PAYLOAD_ARTIFACT_ID,
      kind: "atlas_evidence_verification_payload",
      media_type: "application/json",
      schema_id: "polisyos.atlas.evidence-verification-payload",
      schema_version: "1.0.0",
    },
    retention: {
      retention_class: "content_addressed_runtime_artifacts",
      retention_days: 365,
      retain_until: "2027-08-11T09:00:01.000Z",
      cleanup_policy: "manual_approval_only",
    },
  };
}

function validPayload(): AtlasEvidencePayload {
  const receipt = validReceipt();
  return {
    payload_schema: ATLAS_EVIDENCE_PAYLOAD_SCHEMA,
    evidence_kind: receipt.evidence_kind,
    subject: receipt.subject,
    rule: receipt.rule,
    provenance: receipt.provenance,
    times: receipt.times,
    result: receipt.result,
    details: {
      contrast_ratios: [7.2, 4.5],
      source_count: 7,
    },
  };
}

describe("Atlas evidence artifact contract", () => {
  it("freezes the Core CAS storage convention and accepts a complete receipt", () => {
    expect(ATLAS_EVIDENCE_STORAGE_CONVENTION).toEqual({
      artifact_store_contract:
        "polisyos.core.artifacts.ArtifactStore.put_json",
      artifact_kind: "atlas_evidence_receipt",
      media_type: "application/json",
      default_local_root: ".polisyos/cas",
      payload_canon_spec: {
        name: "polisyos.canon.json",
        version: "0.2.0",
        forbid_floats: false,
        forbid_nan_inf: true,
        exclude_none: true,
        max_depth: 128,
        sort_keys: true,
        separators: [",", ":"],
        ensure_ascii: false,
      },
      receipt_input_role: "verification_payload",
      retention_class: "content_addressed_runtime_artifacts",
      retention_days: 365,
      cleanup_policy: "manual_approval_only",
      delete_on_expiry: false,
    });

    expect(parseAtlasEvidenceReceipt(validReceipt())).toEqual(validReceipt());
    expect(atlasEvidencePayloadSchema.parse(validPayload())).toEqual(
      validPayload(),
    );
    for (const nonFinite of [Number.NaN, Number.POSITIVE_INFINITY]) {
      expect(
        atlasEvidencePayloadSchema.safeParse({
          ...validPayload(),
          details: { contrast_ratio: nonFinite },
        }).success,
      ).toBe(false);
    }
  });

  it("rejects unknown top-level and nested fields", () => {
    expect(
      atlasEvidenceReceiptSchema.safeParse({
        ...validReceipt(),
        unowned_status: "stable",
      }).success,
    ).toBe(false);
    expect(
      atlasEvidenceReceiptSchema.safeParse({
        ...validReceipt(),
        authority: {
          ...validReceipt().authority,
          rationale: "markers remain but the governed shape changed",
        },
      }).success,
    ).toBe(false);
  });

  it("rejects widened authority or a missing denial while markers remain", () => {
    const receipt = validReceipt();

    expect(
      atlasEvidenceReceiptSchema.safeParse({
        ...receipt,
        authority: {
          ...receipt.authority,
          authoritative_for: ["component_maturity"],
        },
      }).success,
    ).toBe(false);
    expect(
      atlasEvidenceReceiptSchema.safeParse({
        ...receipt,
        authority: {
          ...receipt.authority,
          may_not_use_for: receipt.authority.may_not_use_for.filter(
            (purpose) => purpose !== "stable",
          ),
        },
      }).success,
    ).toBe(false);
  });

  it("rejects absent or empty producer and verifier provenance", () => {
    const receipt = validReceipt();
    const { verifier: _verifier, ...withoutVerifier } = receipt.provenance;

    expect(
      atlasEvidenceReceiptSchema.safeParse({
        ...receipt,
        provenance: withoutVerifier,
      }).success,
    ).toBe(false);
    expect(
      atlasEvidenceReceiptSchema.safeParse({
        ...receipt,
        provenance: {
          ...receipt.provenance,
          producer: {
            ...receipt.provenance.producer,
            producer_id: "",
          },
        },
      }).success,
    ).toBe(false);
    expect(
      atlasEvidenceReceiptSchema.safeParse({
        ...receipt,
        provenance: {
          ...receipt.provenance,
          verifier: {
            verifier_id: receipt.provenance.producer.producer_id,
            verifier_version: receipt.provenance.producer.producer_version,
          },
        },
      }).success,
    ).toBe(false);
  });

  it("rejects malformed or wrong-contract content references", () => {
    const receipt = validReceipt();

    for (const artifactId of [
      "a".repeat(64),
      `sha256:${"A".repeat(64)}`,
      `sha256:${"a".repeat(63)}`,
      "sha512:declared-but-unresolved",
    ]) {
      expect(
        atlasEvidenceReceiptSchema.safeParse({
          ...receipt,
          evidence_payload_ref: {
            ...receipt.evidence_payload_ref,
            artifact_id: artifactId,
          },
        }).success,
      ).toBe(false);
    }
    for (const evidencePayloadRef of [
      { ...receipt.evidence_payload_ref, kind: "unrelated_evidence" },
      {
        ...receipt.evidence_payload_ref,
        schema_id: "polisyos.atlas.unrelated-evidence",
      },
      { ...receipt.evidence_payload_ref, schema_version: "2.0.0" },
    ]) {
      expect(
        atlasEvidenceReceiptSchema.safeParse({
          ...receipt,
          evidence_payload_ref: evidencePayloadRef,
        }).success,
      ).toBe(false);
    }
  });

  it("rejects a resolved but semantically unrelated payload", () => {
    const receipt = validReceipt();
    const payload = validPayload();
    const otherArtifactId = `sha256:${"c".repeat(64)}`;

    expect(() =>
      assertAtlasEvidencePayloadBinding(receipt, {
        artifact_id: otherArtifactId,
        payload,
      }),
    ).toThrow(/artifact_id/);

    const unrelatedPayloads: AtlasEvidencePayload[] = [
      {
        ...payload,
        evidence_kind: "manual_at",
      },
      {
        ...payload,
        subject: { ...payload.subject, subject_id: "unrelated-badge" },
      },
      {
        ...payload,
        rule: { ...payload.rule, rule_id: "unrelated-rule" },
      },
      {
        ...payload,
        provenance: {
          ...payload.provenance,
          producer: {
            ...payload.provenance.producer,
            producer_id: "unrelated-producer",
          },
        },
      },
      {
        ...payload,
        provenance: {
          ...payload.provenance,
          verifier: {
            ...payload.provenance.verifier,
            verifier_id: "unrelated-verifier",
          },
        },
      },
      {
        ...payload,
        times: {
          observed_at: "2026-08-11T08:59:59.000Z",
          collected_at: payload.times.collected_at,
          verified_at: payload.times.verified_at,
        },
      },
      {
        ...payload,
        result: {
          outcome: "fail",
          findings: [{ code: "unrelated_failure", detail: "Different result" }],
        },
      },
    ];

    for (const unrelatedPayload of unrelatedPayloads) {
      expect(() =>
        assertAtlasEvidencePayloadBinding(receipt, {
          artifact_id: PAYLOAD_ARTIFACT_ID,
          payload: unrelatedPayload,
        }),
      ).toThrow(/semantic binding/);
    }

    expect(
      assertAtlasEvidencePayloadBinding(receipt, {
        artifact_id: PAYLOAD_ARTIFACT_ID,
        payload,
      }),
    ).toEqual(payload);
  });

  it("rejects a missing time role or invalid semantic ordering", () => {
    const receipt = validReceipt();
    const { observed_at: _observedAt, ...withoutObservation } = receipt.times;

    expect(
      atlasEvidenceReceiptSchema.safeParse({
        ...receipt,
        times: withoutObservation,
      }).success,
    ).toBe(false);
    expect(
      atlasEvidenceReceiptSchema.safeParse({
        ...receipt,
        times: {
          ...receipt.times,
          collected_at: "2026-08-11T08:59:59.000Z",
        },
      }).success,
    ).toBe(false);
    expect(
      atlasEvidenceReceiptSchema.safeParse({
        ...receipt,
        times: {
          ...receipt.times,
          verified_at: "2026-08-11T09:00:00.500Z",
        },
      }).success,
    ).toBe(false);
  });

  it("rejects retention-class, duration, expiry, or cleanup drift", () => {
    const receipt = validReceipt();

    for (const retention of [
      { ...receipt.retention, retention_class: "review_evidence_candidate" },
      { ...receipt.retention, retention_days: 30 },
      { ...receipt.retention, retain_until: "2027-08-10T09:00:01.000Z" },
      { ...receipt.retention, cleanup_policy: "automatic" },
    ]) {
      expect(
        atlasEvidenceReceiptSchema.safeParse({ ...receipt, retention }).success,
      ).toBe(false);
    }
  });

  it("binds outcome semantics to findings instead of a status marker", () => {
    const receipt = validReceipt();

    expect(
      atlasEvidenceReceiptSchema.safeParse({
        ...receipt,
        result: {
          outcome: "pass",
          findings: [{ code: "contrast_below_minimum", detail: "3.2 < 4.5" }],
        },
      }).success,
    ).toBe(false);
    for (const outcome of ["fail", "incomplete"] as const) {
      expect(
        atlasEvidenceReceiptSchema.safeParse({
          ...receipt,
          result: { outcome, findings: [] },
        }).success,
      ).toBe(false);
      expect(
        atlasEvidenceReceiptSchema.safeParse({
          ...receipt,
          result: {
            outcome,
            findings: [{ code: `${outcome}_witness`, detail: "Observed result" }],
          },
        }).success,
      ).toBe(true);
    }
  });

  it("preserves all five P37 predicate-provenance labels without upgrading them", () => {
    for (const predicateProvenance of [
      "recomputed",
      "independently_reconciled",
      "consumer_asserted",
      "institutionally_supplied",
      "not_established",
    ] as const) {
      const receipt = validReceipt();
      const parsed = parseAtlasEvidenceReceipt({
        ...receipt,
        provenance: {
          ...receipt.provenance,
          predicate_provenance: predicateProvenance,
        },
      });

      expect(parsed.provenance.predicate_provenance).toBe(predicateProvenance);
      expect(parsed.authority.may_not_use_for).toContain("component_maturity");
    }
  });

  it("accepts the closed DS6 evidence kinds and rejects a new identity", () => {
    for (const evidenceKind of [
      "automated_browser",
      "automated_keyboard",
      "manual_at",
    ] as const) {
      const receipt = validReceipt();
      expect(
        atlasEvidenceReceiptSchema.safeParse({
          ...receipt,
          evidence_kind: evidenceKind,
        }).success,
      ).toBe(true);
    }
    expect(
      atlasEvidenceReceiptSchema.safeParse({
        ...validReceipt(),
        evidence_kind: "screen_capture",
      }).success,
    ).toBe(false);
  });

  it("rejects duplicate, unordered, empty, or unknown audience identities", () => {
    const receipt = validReceipt();

    for (const audiences of [
      [],
      ["MACHINE", "EXPERT"],
      ["REVIEWER", "REVIEWER"],
      ["internal_review"],
    ]) {
      expect(
        atlasEvidenceReceiptSchema.safeParse({ ...receipt, audiences }).success,
      ).toBe(false);
    }
  });
});
