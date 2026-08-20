import {
  RuntimeApiClient,
  type CycleBoardProjectionPacket,
  type DepthNCycleBoardPayload,
  type DepthNCycleBoardPayloadV2,
  type DepthNDomainRunProjection,
} from "@polisyos/runtime-api-client";

import { queryKeys } from "@/api/queryKeys";
import { observeCachePosture } from "@/api/cacheDiscipline";
import { governedQueryOptions, useGovernedQuery } from "@/api/governedQueryPolicy";
import { authAwareRuntimeFetch } from "@/app/auth/authSession";
import { API_BASE_URL } from "@/shared/lib/constants";

type GovernedProjectionPacket = Awaited<
  ReturnType<RuntimeApiClient["getGovernedProjection"]>
>;

type GovernedProjectionClient = Pick<RuntimeApiClient, "getGovernedProjection">;

type CycleBoardExportPacket = Awaited<
  ReturnType<RuntimeApiClient["getDepthNCycleBoardProjection"]>
>;

type CycleBoardHeroClient = Pick<
  RuntimeApiClient,
  "getDepthNCycleBoardProjection"
>;

export type DepthNCycleBoardHeroProjection = Readonly<{
  packet: CycleBoardProjectionPacket;
  payload: DepthNCycleBoardPayloadV2;
}>;

export type DepthNCycleBoardProjection = Readonly<{
  packet: GovernedProjectionPacket;
  payload: DepthNCycleBoardPayload | null;
}>;

function runtimeApiBaseUrl(): string {
  const applicationOrigin =
    typeof window === "undefined" ? "http://localhost" : window.location.origin;
  return API_BASE_URL
    ? new URL(API_BASE_URL, applicationOrigin).toString()
    : applicationOrigin;
}

const governedProjectionClient = new RuntimeApiClient({
  baseUrl: runtimeApiBaseUrl(),
  fetchImpl: (input, init) => authAwareRuntimeFetch(new Request(input, init)),
});

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isStringArray(value: unknown): value is string[] {
  return (
    Array.isArray(value) && value.every((item) => typeof item === "string")
  );
}

function isDepthNDomainRunProjection(
  value: unknown,
): value is DepthNDomainRunProjection {
  if (!isRecord(value)) {
    return false;
  }
  return (
    (value.acquisition_route == null || isRecord(value.acquisition_route)) &&
    (value.acquisition_economics == null ||
      isRecord(value.acquisition_economics)) &&
    typeof value.design_problem_ref === "string" &&
    typeof value.domain_role === "string" &&
    typeof value.evidence_class === "string" &&
    isRecord(value.evidence_witness) &&
    typeof value.generation_cycle_run_id === "string" &&
    isRecord(value.terminal_distribution) &&
    isStringArray(value.weakest_links)
  );
}

function isDepthNCycleBoardPayload(
  value: unknown,
): value is DepthNCycleBoardPayload {
  if (
    !isRecord(value) ||
    !isRecord(value.depth_evidence) ||
    !isRecord(value.domain_runs) ||
    !isRecord(value.terminal_distributions)
  ) {
    return false;
  }
  return Object.values(value.domain_runs).every(isDepthNDomainRunProjection);
}

/** Narrow only the generated composed-v2 packet intended for the hero surface. */
export function narrowDepthNCycleBoardHeroProjection(
  packet: CycleBoardExportPacket,
): DepthNCycleBoardHeroProjection {
  if (
    packet.packet_schema_version !== "policyos.runtime.cycle_board_packet.v1" ||
    packet.projection_rule_version !== "policyos.runtime.depth_n_cycle_board.v2" ||
    packet.projection_id !== "depth-n-cycle-board"
  ) {
    throw new TypeError(
      "contract_error: Cycle Board hero requires the composed-v2 packet version",
    );
  }
  return Object.freeze({ packet, payload: packet.payload });
}

/** Prepare the future hero query against the distinct static operation. */
export function depthNCycleBoardHeroProjectionQueryOptions(
  client: CycleBoardHeroClient,
) {
  return {
    queryKey: queryKeys.cycleBoardProjection(),
    queryFn: async () =>
      narrowDepthNCycleBoardHeroProjection(
        await client.getDepthNCycleBoardProjection({}),
      ),
  };
}

/** Composed authority has no aggregate owner as-of and is never retained. */
export function depthNCycleBoardHeroProjectionQueryPolicy() {
  return { kind: "never_cache_authority" } as const;
}

/**
 * Narrow one generated governed packet at the feature boundary.
 *
 * The packet is retained byte-for-byte. Contract mismatches become query
 * errors; they are never relabelled as an owner-issued invalid-source state.
 */
export function narrowDepthNCycleBoardProjection(
  packet: GovernedProjectionPacket,
): DepthNCycleBoardProjection {
  if (packet.projection_id !== "depth-n-cycle-board") {
    throw new TypeError(
      "contract_error: governed projection id is not depth-n-cycle-board",
    );
  }
  if (packet.availability !== "available") {
    return Object.freeze({ packet, payload: null });
  }
  if (!isDepthNCycleBoardPayload(packet.payload)) {
    throw new TypeError(
      "contract_error: depth-n-cycle-board payload does not match the generated shape",
    );
  }
  return Object.freeze({ packet, payload: packet.payload });
}

export function depthNCycleBoardProjectionQueryOptions(
  client: GovernedProjectionClient = governedProjectionClient,
) {
  return {
    queryKey: queryKeys.governedProjection("depth-n-cycle-board"),
    queryFn: async () =>
      narrowDepthNCycleBoardProjection(
        await client.getGovernedProjection({
          projection_id: "depth-n-cycle-board",
        }),
      ),
  };
}

/** Bind the feature producer to the wrapper's direct packet `as_of` rule. */
export function depthNCycleBoardProjectionQueryPolicy() {
  return { kind: "owner_as_of" } as const;
}

/** Read the global Cycle Board projection without correlating it to a route. */
export function useDepthNCycleBoardProjection(
  client: GovernedProjectionClient = governedProjectionClient,
) {
  const query = useGovernedQuery(
    governedQueryOptions(
      depthNCycleBoardProjectionQueryOptions(client),
      depthNCycleBoardProjectionQueryPolicy(),
    ),
  );

  return {
    ...query,
    cacheObservation: observeCachePosture(query, query.data?.packet.as_of),
  };
}
