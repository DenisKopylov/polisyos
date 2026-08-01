import { useQuery } from "@tanstack/react-query";
import {
  RuntimeApiClient,
  type DepthNCycleBoardPayload,
  type DepthNDomainRunProjection,
} from "@polisyos/runtime-api-client";

import { queryKeys } from "@/api/queryKeys";
import { authAwareRuntimeFetch } from "@/app/auth/authSession";
import { API_BASE_URL } from "@/shared/lib/constants";

type GovernedProjectionPacket = Awaited<
  ReturnType<RuntimeApiClient["getGovernedProjection"]>
>;

type GovernedProjectionClient = Pick<RuntimeApiClient, "getGovernedProjection">;

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
    isRecord(value.acquisition_route) &&
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

/** Read the global Cycle Board projection without correlating it to a route. */
export function useDepthNCycleBoardProjection() {
  return useQuery(depthNCycleBoardProjectionQueryOptions());
}
