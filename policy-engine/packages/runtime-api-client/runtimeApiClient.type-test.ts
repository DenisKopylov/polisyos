import type {
  ArtifactID,
  ArtifactMissingGovernedProjectionPacket,
  AvailableGovernedProjectionPacket,
  ChannelRegistryEntry,
  ChannelRegistryResponse,
  CycleBoardProjectionPacket,
  DataSnapshotRef,
  DecisionGrade,
  InvalidGovernedProjectionPacket,
  ProjectionSourceValidation,
  RunBoundDesignRecordBinding,
  RunPaperDesignRecordBinding,
  RuntimeApiClient,
} from "./canonicalRuntimeApiClient.js";
import type { components as RawRuntimeApiComponents } from "./types.js";

type Equal<Left, Right> =
  (<Value>() => Value extends Left ? 1 : 2) extends <
    Value,
  >() => Value extends Right ? 1 : 2
    ? true
    : false;
type Assert<Condition extends true> = Condition;

type GovernedProjectionPacket =
  | AvailableGovernedProjectionPacket
  | ArtifactMissingGovernedProjectionPacket
  | InvalidGovernedProjectionPacket;

type CycleBoardExportPacket = Awaited<
  ReturnType<RuntimeApiClient["getDepthNCycleBoardProjection"]>
>;

type CanonicalLiteralWitnesses = [
  Assert<Equal<AvailableGovernedProjectionPacket["availability"], "available">>,
  Assert<
    Equal<
      ArtifactMissingGovernedProjectionPacket["availability"],
      "artifact_missing"
    >
  >,
  Assert<
    Equal<InvalidGovernedProjectionPacket["availability"], "invalid_source">
  >,
  Assert<
    Equal<
      AvailableGovernedProjectionPacket["packet_schema_version"],
      "policyos.runtime.governed_projection_packet.v1"
    >
  >,
  Assert<
    Equal<AvailableGovernedProjectionPacket["source_dependency_hash"], string>
  >,
  Assert<
    Equal<ProjectionSourceValidation["status"], "passed" | "failed" | "not_run">
  >,
  Assert<
    Equal<
      ProjectionSourceValidation["semantic_projection_hash"],
      string | null | undefined
    >
  >,
  Assert<
    Equal<ChannelRegistryEntry["capability_state"], "verification_missing">
  >,
  Assert<
    Equal<
      Extract<
        CycleBoardExportPacket,
        { packet_schema_version: "policyos.runtime.cycle_board_packet.v1" }
      >["projection_rule_version"],
      "policyos.runtime.depth_n_cycle_board.v2"
    >
  >,
  Assert<
    Equal<
      Extract<
        CycleBoardExportPacket,
        {
          packet_schema_version: "policyos.runtime.governed_projection_packet.v1";
        }
      >["projection_rule_version"],
      "policyos.runtime.governed_projection.v1"
    >
  >,
  Assert<
    Equal<CycleBoardProjectionPacket["projection_id"], "depth-n-cycle-board">
  >,
  Assert<Equal<ChannelRegistryEntry["include_in_schema"], false>>,
  Assert<Equal<ChannelRegistryEntry["status"], "active">>,
  Assert<Equal<RunPaperDesignRecordBinding, RunBoundDesignRecordBinding>>,
  Assert<Equal<ArtifactID, RawRuntimeApiComponents["schemas"]["ArtifactID"]>>,
  Assert<
    Equal<
      DataSnapshotRef,
      RawRuntimeApiComponents["schemas"]["DataSnapshotRef-Input"]
    >
  >,
  Assert<
    Equal<DecisionGrade, RawRuntimeApiComponents["schemas"]["DecisionGrade"]>
  >,
  Assert<
    Equal<
      ChannelRegistryResponse["schema_version"],
      "policyos.runtime.channel_registry.v1"
    >
  >,
];

export function narrowGovernedProjectionPacket(
  packet: GovernedProjectionPacket,
): string {
  if (packet.availability === "available") {
    return packet.projection_hash;
  }
  if (packet.availability === "artifact_missing") {
    return packet.absence_reason;
  }
  const invalidAvailability: "invalid_source" = packet.availability;
  return invalidAvailability;
}

export type { CanonicalLiteralWitnesses };

const legacyDataSnapshotRequest: DataSnapshotRef = {
  artifact_id: "sha256:" + "a".repeat(64),
};
const selectedDataSnapshotRequest: RawRuntimeApiComponents["schemas"]["DataSnapshotRef-Input"] =
  legacyDataSnapshotRequest;
const invalidDataSnapshotRequest: DataSnapshotRef = {
  // @ts-expect-error the established package-root alias retains the string ID contract
  artifact_id: 42,
};
void selectedDataSnapshotRequest;
void invalidDataSnapshotRequest;

type SourceWriteTransportWitnesses = [
  Assert<
    Equal<Parameters<RuntimeApiClient["cancelControlJob"]>[0]["job_id"], string>
  >,
  Assert<
    Equal<
      Parameters<RuntimeApiClient["cancelControlJob"]>[0]["body"],
      RawRuntimeApiComponents["schemas"]["ControlJobCancellationRequest"]
    >
  >,
  Assert<
    Equal<
      Awaited<ReturnType<RuntimeApiClient["cancelControlJob"]>>,
      RawRuntimeApiComponents["schemas"]["ControlJobResponse"]
    >
  >,
  Assert<
    Equal<
      Parameters<RuntimeApiClient["registerSqlSource"]>[0]["body"],
      RawRuntimeApiComponents["schemas"]["RegisteredSQLRegistrationRequest"]
    >
  >,
  Assert<
    Equal<
      Awaited<ReturnType<RuntimeApiClient["registerSqlSource"]>>,
      RawRuntimeApiComponents["schemas"]["RegisteredSQLRegistrationResponse"]
    >
  >,
  Assert<
    Equal<
      Parameters<
        RuntimeApiClient["admitRegisteredSqlMaterialization"]
      >[0]["body"],
      RawRuntimeApiComponents["schemas"]["RegisteredSQLMaterializationRequest"]
    >
  >,
  Assert<
    Equal<
      Awaited<
        ReturnType<RuntimeApiClient["admitRegisteredSqlMaterialization"]>
      >,
      RawRuntimeApiComponents["schemas"]["RegisteredSQLMaterializationResponse"]
    >
  >,
  Assert<
    Equal<
      Parameters<
        RuntimeApiClient["withdrawRegisteredSqlMaterialization"]
      >[0]["body"],
      RawRuntimeApiComponents["schemas"]["RegisteredSQLWithdrawalRequest"]
    >
  >,
  Assert<
    Equal<
      Awaited<
        ReturnType<RuntimeApiClient["withdrawRegisteredSqlMaterialization"]>
      >,
      RawRuntimeApiComponents["schemas"]["RegisteredSQLWithdrawalResponse"]
    >
  >,
];

export type { SourceWriteTransportWitnesses };

type ComparisonResult =
  RawRuntimeApiComponents["schemas"]["CompletedExAnteCandidateComparisonResponse"];
type ComparisonRanking = NonNullable<ComparisonResult["candidate_comparison"]>;
type ComparisonTransportWitnesses = [
  Assert<
    Equal<
      Parameters<RuntimeApiClient["getRunMethodMetricComparison"]>[0]["run_id"],
      string
    >
  >,
  Assert<
    Equal<
      Awaited<ReturnType<RuntimeApiClient["getRunMethodMetricComparison"]>>,
      ComparisonResult
    >
  >,
  Assert<
    Equal<
      ComparisonRanking["status"],
      "complete" | "verification_missing" | "invalid"
    >
  >,
  Assert<
    Equal<NonNullable<ComparisonRanking["authority_status"]>, "candidate_only">
  >,
  Assert<Equal<NonNullable<ComparisonRanking["revalidation_required"]>, true>>,
];

export type { ComparisonTransportWitnesses };

type CandidateExperimentResponse = Awaited<
  ReturnType<RuntimeApiClient["getRunCandidateAcquisitionExperiment"]>
>;
type CandidateExperimentAction = NonNullable<
  CandidateExperimentResponse["current_action"]
>;
type CandidateExperimentResult = NonNullable<
  CandidateExperimentAction["candidate_n5_result"]
>;
type CandidateExperimentPriorResult = NonNullable<
  CandidateExperimentAction["prior_candidate_n5_result"]
>;
type CandidateExperimentResultWitnesses = [
  Assert<
    Equal<
      undefined extends CandidateExperimentAction["prior_candidate_n5_result"]
        ? true
        : false,
      true
    >
  >,
  Assert<
    Equal<CandidateExperimentPriorResult["n5_result"], CandidateExperimentResult>
  >,
  Assert<Equal<CandidateExperimentPriorResult["prior_action_generation"], number>>,
  Assert<
    Equal<
      undefined extends CandidateExperimentAction["candidate_n5_result"]
        ? true
        : false,
      true
    >
  >,
  Assert<
    Equal<
      CandidateExperimentResult["result_body"],
      RawRuntimeApiComponents["schemas"]["RunCandidateSimulationN5ResultBody"]
    >
  >,
  Assert<
    Equal<
      NonNullable<CandidateExperimentResult["configuration_use"]>,
      "not_established"
    >
  >,
  Assert<
    Equal<
      NonNullable<CandidateExperimentResult["implementation_currentness"]>,
      "not_established"
    >
  >,
  Assert<
    Equal<
      NonNullable<CandidateExperimentResult["publication_authority"]>,
      false
    >
  >,
];

export type { CandidateExperimentResultWitnesses };
