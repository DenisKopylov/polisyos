import { describe, expect, it } from "vitest";

import adoptionLedger from "../../../../../architecture/atlas_surfaces/atlas-v15-adoption-ledger.json";
import readinessSchema from "../../../../../architecture/atlas_surfaces/surface-readiness-ledger.schema.json";
import {
  ATLAS_EVIDENCE_DENIED_USES,
  ATLAS_EVIDENCE_PAYLOAD_SCHEMA,
  ATLAS_EVIDENCE_RECEIPT_SCHEMA,
  type AtlasEvidencePayload,
  type AtlasEvidenceReceipt,
} from "./atlasEvidenceArtifact";
import {
  ATLAS_MANUAL_AT_PROTOCOL,
  evaluateManualAtMaturityPrerequisite,
  type AtlasManualAtDetails,
  type ManualAtEvidenceBundle,
} from "./atlasManualAtMaturity";

const PAYLOAD_ARTIFACT_ID = `sha256:${"d".repeat(64)}`;
const RECEIPT_ARTIFACT_ID = `sha256:${"f".repeat(64)}`;
const BASIS_ARTIFACT_ID = `sha256:${"c".repeat(64)}`;
const BROWSER_ARTIFACT_ID = `sha256:${"b".repeat(64)}`;
const REPOSITORY_REVISION = "e".repeat(40);
const EVALUATED_AT = "2026-08-11T12:00:00.000Z";

function requireBadgeEntry() {
  const entry = adoptionLedger.entries.find(
    (candidate) => candidate.id === "component-badge",
  );
  if (entry === undefined) {
    throw new Error("Expected the adoption-ledger owner row component-badge.");
  }
  return entry;
}

const badgeEntry = requireBadgeEntry();

function stableOwnerEntry(includeManualRef = true): unknown {
  return {
    ...badgeEntry,
    maturity: "stable",
    evidence_refs: includeManualRef
      ? [
          ...badgeEntry.evidence_refs,
          {
            kind: "browser",
            ref: BROWSER_ARTIFACT_ID,
            as_of: "2026-08-11",
          },
          {
            kind: "at_manual",
            ref: RECEIPT_ARTIFACT_ID,
            as_of: "2026-08-11",
          },
        ]
      : [
          ...badgeEntry.evidence_refs,
          {
            kind: "browser",
            ref: BROWSER_ARTIFACT_ID,
            as_of: "2026-08-11",
          },
        ],
  };
}

function validDetails(): AtlasManualAtDetails {
  return {
    protocol_schema: ATLAS_MANUAL_AT_PROTOCOL,
    reviewer: {
      reviewer_id: "reviewer:at-17",
      reviewer_role: "assistive_technology_reviewer",
    },
    basis: {
      profile_ref: BASIS_ARTIFACT_ID,
      predicate_provenance: "independently_reconciled",
      required_task_ids: ["identify-badge-state"],
      required_at_capabilities: ["screen_reader"],
    },
    session: {
      session_id: "manual-at:component-badge:2026-08-11",
      assistive_technologies: ["voiceover@macos-15"],
      observed_at_capabilities: ["screen_reader"],
      observation_status: "observed",
      observed_task_count: 1,
      task_results: [
        {
          task_id: "identify-badge-state",
          outcome: "pass",
        },
      ],
    },
    authority: {
      authoritative_for: ["manual_at_observation"],
      may_not_use_for: [...ATLAS_EVIDENCE_DENIED_USES],
    },
    expires_at: "2026-09-11T09:00:02.000Z",
  };
}

function validBundle(): ManualAtEvidenceBundle {
  const receipt: AtlasEvidenceReceipt = {
    receipt_schema: ATLAS_EVIDENCE_RECEIPT_SCHEMA,
    authority: {
      authoritative_for: ["atlas_evidence_capture"],
      may_not_use_for: [...ATLAS_EVIDENCE_DENIED_USES],
    },
    evidence_kind: "manual_at",
    subject: {
      kind: "component_state",
      subject_id: "component-badge",
      state_id: "neutral",
    },
    rule: {
      rule_id: ATLAS_MANUAL_AT_PROTOCOL.rule_id,
      rule_version: ATLAS_MANUAL_AT_PROTOCOL.version,
    },
    provenance: {
      producer: {
        producer_id: "atlas-manual-at-reviewer",
        producer_version: "1.0.0",
      },
      verifier: {
        verifier_id: "atlas-manual-at-reconciler",
        verifier_version: "1.0.0",
      },
      repository_revision: REPOSITORY_REVISION,
      command_argv: ["manual-at-review", "--session", "component-badge"],
      predicate_provenance: "independently_reconciled",
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
      schema_id: ATLAS_EVIDENCE_PAYLOAD_SCHEMA.id,
      schema_version: ATLAS_EVIDENCE_PAYLOAD_SCHEMA.version,
    },
    retention: {
      retention_class: "content_addressed_runtime_artifacts",
      retention_days: 365,
      retain_until: "2027-08-11T09:00:01.000Z",
      cleanup_policy: "manual_approval_only",
    },
  };
  const payload: AtlasEvidencePayload = {
    payload_schema: ATLAS_EVIDENCE_PAYLOAD_SCHEMA,
    evidence_kind: receipt.evidence_kind,
    subject: receipt.subject,
    rule: receipt.rule,
    provenance: receipt.provenance,
    times: receipt.times,
    result: receipt.result,
    details: validDetails(),
  };

  return {
    receipt_artifact_id: RECEIPT_ARTIFACT_ID,
    receipt,
    resolved_payload: {
      artifact_id: PAYLOAD_ARTIFACT_ID,
      payload,
    },
  };
}

function evaluate(
  bundle: ManualAtEvidenceBundle | undefined,
  evaluatedAt = EVALUATED_AT,
  entry: unknown = stableOwnerEntry(),
) {
  return evaluateManualAtMaturityPrerequisite(
    entry,
    "neutral",
    bundle,
    evaluatedAt,
  );
}

describe("Atlas manual AT maturity prerequisite", () => {
  it("consumes the architecture owner row and keeps shaped evidence non-satisfied", () => {
    expect(readinessSchema.$defs.componentMaturity.enum).toEqual([
      "experimental",
      "beta",
      "stable",
      "deprecated",
    ]);
    expect(badgeEntry.maturity).toBe("experimental");
    expect(
      evaluateManualAtMaturityPrerequisite(
        badgeEntry,
        "neutral",
        undefined,
        EVALUATED_AT,
      ),
    ).toMatchObject({
      decision: "not_required",
      code: "manual_at_not_required",
    });

    expect(evaluate(validBundle())).toEqual({
      decision: "blocked",
      code: "manual_at_integrity_not_established",
      evidence_status: "unverified",
      grants_stable: false,
    });
  });

  it("keeps valid owner rows and unknown owner/ref keys admitted", () => {
    const ownerEntry = stableOwnerEntry() as {
      evidence_refs: Array<Record<string, unknown>>;
    };
    const ownerWithUnknownKeys = {
      ...ownerEntry,
      c16_unknown_owner_key: "preserved-by-loose-owner-contract",
      evidence_refs: ownerEntry.evidence_refs.map((reference, index) =>
        index === 0
          ? {
              ...reference,
              c16_unknown_reference_key: "preserved-by-loose-reference-contract",
            }
          : reference,
      ),
    };

    expect(evaluate(validBundle(), EVALUATED_AT, ownerEntry)).toEqual({
      decision: "blocked",
      code: "manual_at_integrity_not_established",
      evidence_status: "unverified",
      grants_stable: false,
    });
    expect(evaluate(validBundle(), EVALUATED_AT, ownerWithUnknownKeys)).toEqual({
      decision: "blocked",
      code: "manual_at_integrity_not_established",
      evidence_status: "unverified",
      grants_stable: false,
    });
  });

  it("fails an owner-shaped stable row closed when evidence is absent", () => {
    expect(evaluate(undefined, EVALUATED_AT, stableOwnerEntry(false))).toEqual({
      decision: "blocked",
      code: "manual_at_evidence_absent",
      evidence_status: "missing",
      grants_stable: false,
    });
  });

  it("fails expired evidence with a code distinct from absent", () => {
    const bundle = validBundle();
    bundle.resolved_payload.payload.details = {
      ...validDetails(),
      expires_at: "2026-08-11T11:59:59.000Z",
    };

    const result = evaluate(bundle);
    expect(result).toEqual({
      decision: "blocked",
      code: "manual_at_evidence_expired",
      evidence_status: "expired",
      grants_stable: false,
    });
    expect(result.code).not.toBe("manual_at_evidence_absent");
  });

  it("rejects human evidence that exceeds the declared authority bound", () => {
    const bundle = validBundle();
    bundle.resolved_payload.payload.details = {
      ...validDetails(),
      authority: {
        authoritative_for: ["component_maturity"],
        may_not_use_for: [...ATLAS_EVIDENCE_DENIED_USES],
      },
    };

    expect(evaluate(bundle)).toMatchObject({
      decision: "blocked",
      code: "manual_at_authority_bound_exceeded",
      grants_stable: false,
    });
  });

  it("rejects a valid resolved receipt for a different surface", () => {
    const bundle = validBundle();
    const unrelatedSubject = {
      kind: "surface" as const,
      subject_id: "surface-insights",
      state_id: "neutral",
    };
    bundle.receipt.subject = unrelatedSubject;
    bundle.resolved_payload.payload.subject = unrelatedSubject;

    expect(evaluate(bundle)).toEqual({
      decision: "blocked",
      code: "manual_at_subject_mismatch",
      evidence_status: "mismatched",
      grants_stable: false,
    });
  });

  it("keeps unknown, known zero, and missing evidence distinguishable", () => {
    const unknown = validBundle();
    unknown.receipt.result = {
      outcome: "incomplete",
      findings: [{ code: "observation_unknown", detail: "Observation unavailable" }],
    };
    unknown.resolved_payload.payload.result = unknown.receipt.result;
    unknown.resolved_payload.payload.details = {
      ...validDetails(),
      session: {
        ...validDetails().session,
        observation_status: "unknown",
        observed_task_count: null,
        task_results: [],
      },
    };

    const zero = validBundle();
    zero.receipt.result = {
      outcome: "incomplete",
      findings: [{ code: "zero_observations", detail: "No task was observed" }],
    };
    zero.resolved_payload.payload.result = zero.receipt.result;
    zero.resolved_payload.payload.details = {
      ...validDetails(),
      session: {
        ...validDetails().session,
        observed_task_count: 0,
        task_results: [],
      },
    };

    expect(evaluate(unknown)).toMatchObject({
      code: "manual_at_evidence_unknown",
      evidence_status: "unknown",
    });
    expect(evaluate(zero)).toMatchObject({
      code: "manual_at_zero_observations",
      evidence_status: "zero",
    });
    expect(evaluate(undefined)).toMatchObject({
      code: "manual_at_evidence_absent",
      evidence_status: "missing",
    });
  });

  it("fails institutionally supplied predicate provenance closed", () => {
    const bundle = validBundle();
    bundle.receipt.provenance.predicate_provenance = "institutionally_supplied";
    bundle.resolved_payload.payload.provenance = bundle.receipt.provenance;

    expect(evaluate(bundle)).toEqual({
      decision: "blocked",
      code: "manual_at_predicate_not_admissible",
      evidence_status: "unreconciled",
      grants_stable: false,
    });
  });

  it("rejects marker-preserving resolved-payload drift", () => {
    const bundle = validBundle();
    bundle.resolved_payload.payload.rule = {
      ...bundle.resolved_payload.payload.rule,
      rule_version: "marker-preserving-drift",
    };

    expect(evaluate(bundle)).toMatchObject({
      decision: "blocked",
      code: "manual_at_payload_unverified",
      grants_stable: false,
    });
  });

  it("fails an unestablished or mismatched task/AT basis closed", () => {
    const unestablished = validBundle();
    unestablished.resolved_payload.payload.details = {
      ...validDetails(),
      basis: {
        profile_ref: null,
        predicate_provenance: "not_established",
        required_task_ids: [],
        required_at_capabilities: [],
      },
    };
    expect(evaluate(unestablished)).toMatchObject({
      code: "manual_at_basis_not_established",
      evidence_status: "unreconciled",
    });

    const undeclaredTask = validBundle();
    undeclaredTask.resolved_payload.payload.details = {
      ...validDetails(),
      session: {
        ...validDetails().session,
        task_results: [{ task_id: "noop", outcome: "pass" }],
      },
    };
    expect(evaluate(undeclaredTask)).toMatchObject({
      code: "manual_at_basis_mismatch",
      evidence_status: "inadequate",
    });

    const inadequateAt = validBundle();
    inadequateAt.resolved_payload.payload.details = {
      ...validDetails(),
      session: {
        ...validDetails().session,
        observed_at_capabilities: ["none"],
      },
    };
    expect(evaluate(inadequateAt)).toMatchObject({
      code: "manual_at_basis_mismatch",
      evidence_status: "inadequate",
    });
  });

  it("rejects future verification and expiry that does not follow verification", () => {
    expect(
      evaluate(validBundle(), "2026-08-11T09:00:01.500Z"),
    ).toMatchObject({
      code: "manual_at_evidence_not_yet_valid",
      evidence_status: "future",
    });

    const invalidExpiry = validBundle();
    invalidExpiry.resolved_payload.payload.details = {
      ...validDetails(),
      expires_at: invalidExpiry.receipt.times.verified_at,
    };
    expect(evaluate(invalidExpiry)).toMatchObject({
      code: "manual_at_expiry_invalid",
      evidence_status: "invalid",
    });
  });

  it("requires the owner row to bind the exact receipt artifact identity", () => {
    expect(evaluate(validBundle(), EVALUATED_AT, stableOwnerEntry(false))).toMatchObject({
      code: "manual_at_owner_reference_absent",
      evidence_status: "missing",
    });
  });
});
