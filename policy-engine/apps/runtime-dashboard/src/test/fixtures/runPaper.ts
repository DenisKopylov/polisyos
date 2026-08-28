import type { components } from "@/api/types";

export type RunPaperPacket = components["schemas"]["RunPaperPacket"];
type AvailableRunPaperCase = Extract<
  RunPaperPacket["case_record"],
  { availability: "available" }
>;
type AuthorityAbstainingRunPaperCase = Extract<
  RunPaperPacket["case_record"],
  { availability: "record_available_authority_abstaining" }
>;
type VerifiedCaseSource = components["schemas"]["RunPaperVerifiedCaseSource"];

const digest = (character: string) => `sha256:${character.repeat(64)}`;

function verifiedCaseSource(
  authorityPurpose: VerifiedCaseSource["authority_purpose"],
  digestCharacter: string,
): VerifiedCaseSource {
  const sourceDigest = digest(digestCharacter);
  return {
    as_of: "2026-08-21T10:00:00Z",
    authority_purpose: authorityPurpose,
    producer: {
      component: "polisyos.fixture.run-paper",
      version: "1.0.0",
    },
    source_digest: sourceDigest,
    source_ref: {
      artifact_id: sourceDigest,
      kind: `runtime.case_${authorityPurpose}`,
      media_type: "application/json",
    },
    source_schema_name: `polisyos.runtime.case_${authorityPurpose}`,
    source_schema_version: "1.0.0",
    verification: {
      bound_artifact_content_hash: sourceDigest,
      bound_case_id: "case.fixture",
      bound_cell_id: "cell-a",
      bound_design_record_record_id: "case.design.fixture",
      bound_run_id: "run-1",
      bound_tenant_id: "tenant-a",
      status: "passed",
      validator_id: `fixture.${authorityPurpose}`,
      validator_version: "1.0.0",
    },
  };
}

export function availableRunPaperCaseFixture(): AvailableRunPaperCase {
  const issue = (
    kind: "blocker" | "limitation" | "objection" | "abstention",
    digestCharacter: string,
  ) => ({
    code: `fixture.${kind}`,
    issue_id: `${kind}.fixture`,
    kind,
    owner_route: `team-${kind}`,
    source_bindings: [verifiedCaseSource(kind, digestCharacter)],
    statement: `${kind} fixture statement`,
    status: kind === "limitation" ? "accepted_as_limit" : "open",
    status_vocabulary_ref: "polisyos.pdc.ObligationRecord.status",
  });
  const designDigest = digest("c");
  const searchLedgerDigest = digest("9");
  return {
    abstentions: [issue("abstention", "2")],
    admission_state: {
      source_binding: verifiedCaseSource("admission_state", "d"),
      state: "admitted_to_claim",
      vocabulary_ref:
        "polisyos.runtime.quality.hypothesis_ledger.HypothesisAdmissionState",
    },
    availability: "available",
    blockers: [issue("blocker", "f")],
    case_id: "case.fixture",
    design_record: {
      authority_boundary: {
        authoritative_for: ["governed_case_projection"],
        may_not_use_for: ["production_authority"],
        posture: "governed",
        rule_version_refs: ["policyos.fixture.case.v1"],
        source_authority: "deterministic_producer",
      },
      axis_positions: [],
      candidate_ref: "candidate://fixture",
      candidate_source: "deterministic_producer",
      envelope: {
        actor_scopes: ["actor.fixture"],
        certified_for: ["governed_case_projection"],
        cluster_authority_dimension_refs: [],
        domains: ["fixture"],
        envelope_id: "case.envelope.fixture",
        epistemic_regime_scopes: ["uncertainty"],
        method_scopes: ["deterministic_fixture"],
        not_certified_for: ["production_authority"],
        posture_scopes: ["governed"],
        rule_version_ref: "policyos.fixture.case.v1",
      },
      firewall_status: [],
      ledger_refs: [],
      projection_audiences: ["REVIEWER", "MACHINE"],
      projection_status: "governed",
      record_id: "case.design.fixture",
      schema_version: "policyos.policy_design_case.layer2_readiness.v1",
    },
    design_record_binding: {
      binding_id: "binding.fixture",
      case_id: "case.fixture",
      cell_id: "cell-a",
      design_record_content_digest: designDigest,
      design_record_record_id: "case.design.fixture",
      design_record_ref: {
        artifact_id: designDigest,
        kind: "policyos.layer2_s2.design_record_v0",
        media_type: "application/json",
      },
      design_record_schema_name: "policyos.layer2_s2.design_record_v0",
      design_record_schema_version:
        "policyos.policy_design_case.layer2_readiness.v1",
      producer: {
        component: "polisyos.fixture.run-paper",
        version: "1.0.0",
      },
      run_id: "run-1",
      schema_version: "policyos.pdc.run_bound_design_record_binding.v1",
      search_ledger_content_digest: searchLedgerDigest,
      search_ledger_id: "search-ledger.fixture",
      search_ledger_ref: {
        artifact_id: searchLedgerDigest,
        kind: "policyos.layer2_s2.search_ledger",
        media_type: "application/json",
      },
      tenant_id: "tenant-a",
    },
    grounding_state: {
      source_binding: verifiedCaseSource("grounding_state", "b"),
      state: "current_valid",
      vocabulary_ref:
        "polisyos.runtime.quality.generation_cycle.GroundingStatus",
    },
    limitations: [issue("limitation", "0")],
    objections: [issue("objection", "1")],
    promotion_state: {
      source_binding: verifiedCaseSource("promotion_state", "e"),
      state: "governed_promoted",
      vocabulary_ref:
        "polisyos.runtime.quality.proving_ground.governed_promotion_gate.Layer3G4PromotionRecord.promotion_state",
    },
  } as AvailableRunPaperCase;
}

export function authorityAbstainingRunPaperCaseFixture(): AuthorityAbstainingRunPaperCase {
  const available = availableRunPaperCaseFixture();
  return {
    admission_nonreceipt: {
      authority_state: "absent/unallocated",
      denied_uses: [
        "admission_state",
        "admitted_case_projection",
        "available_run_paper_case",
      ],
      kind: "run_paper_authority_nonreceipt",
      missing_authority: "hypothesis_ledger_admission_authority",
      owner_route:
        "polisyos.runtime.quality.hypothesis_ledger.HypothesisAdmissionState",
      status: "not_established",
    },
    authority_projection: "abstained",
    availability: "record_available_authority_abstaining",
    case_id: available.case_id,
    design_record: available.design_record,
    design_record_binding: available.design_record_binding,
    grounding_nonreceipt: {
      authority_state: "absent/unallocated",
      denied_uses: [
        "grounding_state",
        "grounded_case_projection",
        "available_run_paper_case",
      ],
      kind: "run_paper_authority_nonreceipt",
      missing_authority: "generation_cycle_grounding_authority",
      owner_route: "polisyos.runtime.quality.generation_cycle.GroundingStatus",
      status: "not_established",
    },
    promotion_nonreceipt: {
      authority_state: "absent/unallocated",
      denied_uses: [
        "promotion_state",
        "governed_case_projection",
        "available_run_paper_case",
      ],
      kind: "run_paper_authority_nonreceipt",
      missing_authority: "layer3_g4_promotion_authority",
      owner_route:
        "polisyos.runtime.quality.proving_ground.governed_promotion_gate.Layer3G4PromotionRecord.promotion_state",
      status: "not_established",
    },
  };
}

export function runPaperPacketFixture(
  overrides: Partial<RunPaperPacket> = {},
): RunPaperPacket {
  const manifestArtifactId = digest("a");
  const projectionHash = digest("b");
  const replayQuery =
    `manifest_artifact_id=${encodeURIComponent(manifestArtifactId)}` +
    "&manifest_schema_version=0.1.0" +
    "&paper_projection_rule_version=policyos.runtime.run_paper.v1" +
    `&paper_projection_hash=${encodeURIComponent(projectionHash)}`;
  return {
    artifact_links: [
      {
        artifact_ref: {
          artifact_id: digest("c"),
          kind: "scientist.decision_packet",
          media_type: "application/json",
        },
        href: `/api/v1/artifacts/${digest("c")}`,
        relation: "run_output",
      },
    ],
    case_record: {
      availability: "artifact_missing",
      capability_state: "producer_missing",
      closure_signal: "case-record-not-run-bound",
      may_not_use_for: [
        "case_identity",
        "design_record",
        "grounding_state",
        "admission_state",
        "promotion_state",
        "blockers",
        "limitations",
        "objections",
        "abstentions",
      ],
      owner_route: "team-runtime",
      reason_code: "case-record-not-run-bound",
    },
    intended_audiences: ["reviewer", "expert"],
    packet_schema_version: "policyos.runtime.run_paper_packet.v1",
    projection_hash: projectionHash,
    projection_rule_version: "policyos.runtime.run_paper.v1",
    replay_address: `/api/v1/runs/run-1/paper?${replayQuery}`,
    replay_pins: {
      manifest_artifact_id: manifestArtifactId,
      manifest_schema_version: "0.1.0",
      paper_projection_hash: projectionHash,
      paper_projection_rule_version: "policyos.runtime.run_paper.v1",
    },
    report_href: `/runs/run-1/report?${replayQuery}#stage-trace`,
    run: {
      cell_id: "cell-a",
      duration_ms: 45_000,
      finished_at: "2026-08-21T10:00:45Z",
      run_id: "run-1",
      run_terminality: "terminal",
      source_kind: "core_run",
      started_at: "2026-08-21T10:00:00Z",
      status: "success",
      tenant_id: "tenant-a",
    },
    source: {
      environment: null,
      manifest_ref: {
        artifact_id: manifestArtifactId,
        kind: "core.run_manifest",
        media_type: "application/json",
      },
      manifest_schema_name: "polisyos.core.RunManifest",
      manifest_schema_version: "0.1.0",
      producer: {
        component: "polisyos.fixture.run-paper",
        version: "1.0.0",
      },
      registry_bundle: {
        artifact_id: digest("d"),
        kind: "core.registry_bundle",
        media_type: "application/json",
      },
    },
    stable_address: "/api/v1/runs/run-1/paper",
    stage_trace: {
      availability: "available",
      owner_route: "core RunManifest.trace_ref",
      section_id: "stage-trace",
      trace_ref: {
        artifact_id: digest("e"),
        kind: "scientist.trace",
        media_type: "application/json",
      },
    },
    ...overrides,
  } as RunPaperPacket;
}

export function authorityAbstainingRunPaperPacketFixture(): RunPaperPacket {
  const caseRecord = authorityAbstainingRunPaperCaseFixture();
  const requiredRefs = [
    caseRecord.design_record_binding.design_record_ref,
    caseRecord.design_record_binding.search_ledger_ref,
  ];
  return runPaperPacketFixture({
    artifact_links: requiredRefs.map((artifactRef) => ({
      artifact_ref: artifactRef,
      href: `/api/v1/artifacts/${artifactRef.artifact_id}`,
      relation: "run_output",
    })),
    case_record: caseRecord,
  });
}
