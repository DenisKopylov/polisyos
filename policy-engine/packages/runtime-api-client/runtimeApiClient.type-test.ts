import type {
  ArtifactMissingGovernedProjectionPacket,
  AvailableGovernedProjectionPacket,
  ChannelRegistryEntry,
  ChannelRegistryResponse,
  InvalidGovernedProjectionPacket,
  ProjectionSourceValidation,
} from "./canonicalRuntimeApiClient.js";

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
  Assert<Equal<ChannelRegistryEntry["include_in_schema"], false>>,
  Assert<Equal<ChannelRegistryEntry["status"], "active">>,
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
