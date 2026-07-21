import type {
  AvailableGovernedProjectionPacket,
  LegacyProvingGroundPayload,
} from "@polisyos/runtime-api-client";

export const FIXTURE_PAYLOAD = {
  fixture_authority: "fixture_only",
  fixture_identities: [],
  fixture_records: [],
  runtime_outcomes: {
    availability: "artifact_missing",
    reason: "fixture records do not carry runtime outcomes",
  },
} satisfies LegacyProvingGroundPayload;

export const GOVERNED_PACKET = {
  as_of: "2026-07-21T00:00:00.000Z",
  authoritative_for: ["publication_review"],
  availability: "available",
  export_replay_contract: "policyos.runtime.export_replay_binding.v1",
  freshness: {
    basis: "request_observation",
    observed_at: "2026-07-21T00:00:01.000Z",
    source_as_of: "2026-07-21T00:00:00.000Z",
    state: "observed",
  },
  intended_audience: "EXPERT",
  may_not_use_for: [],
  packet_schema_version: "policyos.runtime.governed_projection_packet.v1",
  payload: FIXTURE_PAYLOAD,
  projection_hash: "sha256:projection",
  projection_id: "legacy-proving-ground",
  projection_rule_version: "policyos.runtime.governed_projection.v1",
  replay_address: "artifact://legacy-proving-ground",
  source: {
    artifact_content_hash: "sha256:fixture",
    declared_content_hash: "sha256:fixture",
    related_artifact_bindings: [],
    relative_path: "fixtures/legacy-proving-ground.json",
    validation: {
      bound_artifact_content_hash: "sha256:fixture",
      bound_dependency_aggregate_identity: "sha256:dependencies",
      bound_dependency_count: 0,
      issue_codes: [],
      semantic_projection_hash: "sha256:projection",
      semantic_projection_hash_rule_version: "fixture.semantic.v1",
      status: "passed",
      validator_id: "fixture-owner-validator",
      validator_version: "1",
    },
  },
  source_dependency_hash: "sha256:dependencies",
  source_rule_version: "fixture.source.v1",
  source_schema_version: "fixture.schema.v1",
  stable_address: "projection://legacy-proving-ground",
} satisfies AvailableGovernedProjectionPacket;
