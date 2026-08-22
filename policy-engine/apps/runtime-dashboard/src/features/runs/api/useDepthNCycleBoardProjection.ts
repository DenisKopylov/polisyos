import {
  RuntimeApiClient,
  type CycleBoardProjectionPacket,
  type DepthNCycleBoardPayloadV2,
} from "@polisyos/runtime-api-client";

import { queryKeys } from "@/api/queryKeys";
import {
  governedQueryOptions,
  useGovernedQuery,
} from "@/api/governedQueryPolicy";
import { authAwareRuntimeFetch } from "@/app/auth/authSession";
import { API_BASE_URL } from "@/shared/lib/constants";

type CycleBoardExportPacket = Awaited<
  ReturnType<RuntimeApiClient["getDepthNCycleBoardProjection"]>
>;

type CapturedCycleBoardExport = Readonly<{
  packet: CycleBoardExportPacket;
  rawPacketBytes: Uint8Array;
}>;

type CycleBoardHeroClient = Readonly<{
  getDepthNCycleBoardProjection: (
    params: Record<string, never>,
  ) => Promise<CapturedCycleBoardExport>;
}>;

export type DepthNCycleBoardProjection = Readonly<{
  packet: CycleBoardProjectionPacket;
  payload: DepthNCycleBoardPayloadV2;
  rawPacketBytes: Uint8Array;
}>;

export type DepthNCycleBoardHeroProjection = DepthNCycleBoardProjection;

function runtimeApiBaseUrl(): string {
  const applicationOrigin =
    typeof window === "undefined" ? "http://localhost" : window.location.origin;
  return API_BASE_URL
    ? new URL(API_BASE_URL, applicationOrigin).toString()
    : applicationOrigin;
}

const cycleBoardProjectionClient: CycleBoardHeroClient = {
  async getDepthNCycleBoardProjection(params) {
    let rawPacketBytes: Uint8Array | null = null;
    const client = new RuntimeApiClient({
      baseUrl: runtimeApiBaseUrl(),
      fetchImpl: async (input, init) => {
        const response = await authAwareRuntimeFetch(new Request(input, init));
        rawPacketBytes = new Uint8Array(await response.clone().arrayBuffer());
        return response;
      },
    });
    const packet = await client.getDepthNCycleBoardProjection(params);
    if (rawPacketBytes === null) {
      throw new TypeError(
        "contract_error: Cycle Board response bytes were not captured",
      );
    }
    return Object.freeze({ packet, rawPacketBytes });
  },
};

/** Narrow only the generated composed-v2 packet intended for the hero surface. */
export function narrowDepthNCycleBoardHeroProjection(
  packet: CycleBoardExportPacket,
  rawPacketBytes: Uint8Array,
): DepthNCycleBoardProjection {
  if (
    packet.packet_schema_version !== "policyos.runtime.cycle_board_packet.v1" ||
    packet.projection_rule_version !==
      "policyos.runtime.depth_n_cycle_board.v2" ||
    packet.projection_id !== "depth-n-cycle-board"
  ) {
    throw new TypeError(
      "contract_error: Cycle Board hero requires the composed-v2 packet version",
    );
  }
  return Object.freeze({
    packet,
    payload: packet.payload,
    rawPacketBytes,
  });
}

/** Prepare the hero query against the distinct static composed-v2 operation. */
export function depthNCycleBoardHeroProjectionQueryOptions(
  client: CycleBoardHeroClient,
) {
  return {
    queryKey: queryKeys.cycleBoardProjection(),
    queryFn: async () => {
      const response = await client.getDepthNCycleBoardProjection({});
      return narrowDepthNCycleBoardHeroProjection(
        response.packet,
        response.rawPacketBytes,
      );
    },
  };
}

/** Composed authority has no aggregate owner as-of and is never retained. */
export function depthNCycleBoardHeroProjectionQueryPolicy() {
  return { kind: "never_cache_authority" } as const;
}

/** Read the global Cycle Board projection without correlating it to a route. */
export function useDepthNCycleBoardProjection(
  client: CycleBoardHeroClient = cycleBoardProjectionClient,
) {
  return useGovernedQuery(
    governedQueryOptions(
      depthNCycleBoardHeroProjectionQueryOptions(client),
      depthNCycleBoardHeroProjectionQueryPolicy(),
    ),
  );
}
