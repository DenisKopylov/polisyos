import {
  RuntimeApiClient,
  type AcquisitionDecisionRequestResponse,
  type AcquisitionExecutionResponse,
  type AcquisitionRouteListResponse,
  type AcquisitionRouteMutationRequest,
  type AcquisitionRouteProjection,
} from "@polisyos/runtime-api-client";

import {
  acquisitionDecisionRequestResponseSchema,
  acquisitionExecutionResponseSchema,
  acquisitionGrowthPacketSchema,
  acquisitionRouteListResponseSchema,
  acquisitionRouteProjectionSchema,
} from "@/features/runs/api/acquisitionRouteValidators";
import {
  governedQueryOptions,
  useGovernedQuery,
} from "@/api/governedQueryPolicy";
import { queryKeys } from "@/api/queryKeys";
import { authAwareRuntimeFetch } from "@/app/auth/authSession";
import type { AcquisitionGrowthPacket } from "@/features/runs/domain/acquisitionRoutePresentation";
import { API_BASE_URL } from "@/shared/lib/constants";

type CapturedResponse<T> = Readonly<{
  packet: T;
  rawPacketBytes: Uint8Array;
}>;

export type AcquisitionGrowthProjection = Readonly<{
  packet: AcquisitionGrowthPacket;
  payload: AcquisitionGrowthPacket["payload"];
  rawPacketBytes: Uint8Array;
}>;

export type AcquisitionRouteCollection =
  CapturedResponse<AcquisitionRouteListResponse>;
export type AcquisitionRouteDetail =
  CapturedResponse<AcquisitionRouteProjection>;

export type AcquisitionRoutesClient = Readonly<{
  getAcquisitionGrowth: () => Promise<CapturedResponse<unknown>>;
  getAcquisitionRoute: (
    runId: string,
    routeId: string,
  ) => Promise<CapturedResponse<unknown>>;
  listAcquisitionRoutes: (runId: string) => Promise<CapturedResponse<unknown>>;
}>;

function runtimeApiBaseUrl(): string {
  const applicationOrigin =
    typeof window === "undefined" ? "http://localhost" : window.location.origin;
  return API_BASE_URL
    ? new URL(API_BASE_URL, applicationOrigin).toString()
    : applicationOrigin;
}

async function captureRuntimeResponse<T>(
  invoke: (client: RuntimeApiClient) => Promise<T>,
): Promise<CapturedResponse<T>> {
  let rawPacketBytes: Uint8Array | null = null;
  const client = new RuntimeApiClient({
    baseUrl: runtimeApiBaseUrl(),
    fetchImpl: async (input, init) => {
      const response = await authAwareRuntimeFetch(new Request(input, init));
      rawPacketBytes = new Uint8Array(await response.clone().arrayBuffer());
      return response;
    },
  });
  const packet = await invoke(client);
  if (rawPacketBytes === null) {
    throw new TypeError(
      "contract_error: acquisition response bytes were not captured",
    );
  }
  return Object.freeze({
    packet,
    rawPacketBytes: new Uint8Array(rawPacketBytes),
  });
}

const runtimeAcquisitionRoutesClient: AcquisitionRoutesClient = Object.freeze({
  getAcquisitionGrowth: () =>
    captureRuntimeResponse((client) =>
      client.getGovernedProjection({ projection_id: "acquisition-growth" }),
    ),
  getAcquisitionRoute: (runId, routeId) =>
    captureRuntimeResponse((client) =>
      client.getRunAcquisitionRoute({ route_id: routeId, run_id: runId }),
    ),
  listAcquisitionRoutes: (runId) =>
    captureRuntimeResponse((client) =>
      client.listRunAcquisitionRoutes({ run_id: runId }),
    ),
});

function requireCapturedBytes(rawPacketBytes: Uint8Array) {
  if (rawPacketBytes.byteLength === 0) {
    throw new TypeError("contract_error: acquisition response bytes are empty");
  }
  return new Uint8Array(rawPacketBytes);
}

export function narrowAcquisitionGrowthProjection(
  response: CapturedResponse<unknown>,
): AcquisitionGrowthProjection {
  const packet = acquisitionGrowthPacketSchema.parse(
    response.packet,
  ) as AcquisitionGrowthPacket;
  return Object.freeze({
    packet,
    payload: packet.payload,
    rawPacketBytes: requireCapturedBytes(response.rawPacketBytes),
  });
}

export function narrowAcquisitionRouteCollection(
  runId: string,
  response: CapturedResponse<unknown>,
): AcquisitionRouteCollection {
  const packet = acquisitionRouteListResponseSchema.parse(response.packet);
  if (packet.run_id !== runId) {
    throw new TypeError("contract_error: acquisition route list run mismatch");
  }
  return Object.freeze({
    packet,
    rawPacketBytes: requireCapturedBytes(response.rawPacketBytes),
  });
}

export function narrowAcquisitionRouteDetail(
  runId: string,
  routeId: string,
  response: CapturedResponse<unknown>,
): AcquisitionRouteDetail {
  const packet = acquisitionRouteProjectionSchema.parse(response.packet);
  if (packet.run_id !== runId || packet.route_id !== routeId) {
    throw new TypeError(
      "contract_error: acquisition route detail binding mismatch",
    );
  }
  return Object.freeze({
    packet,
    rawPacketBytes: requireCapturedBytes(response.rawPacketBytes),
  });
}

export function acquisitionGrowthQueryOptions(
  client: AcquisitionRoutesClient = runtimeAcquisitionRoutesClient,
) {
  return {
    queryFn: async () =>
      narrowAcquisitionGrowthProjection(await client.getAcquisitionGrowth()),
    queryKey: queryKeys.acquisitionGrowth(),
  };
}

export function acquisitionRoutesQueryOptions(
  runId: string,
  client: AcquisitionRoutesClient = runtimeAcquisitionRoutesClient,
) {
  return {
    queryFn: async () =>
      narrowAcquisitionRouteCollection(
        runId,
        await client.listAcquisitionRoutes(runId),
      ),
    queryKey: queryKeys.runAcquisitionRoutes(runId),
  };
}

export function acquisitionRouteQueryOptions(
  runId: string,
  routeId: string,
  client: AcquisitionRoutesClient = runtimeAcquisitionRoutesClient,
) {
  return {
    queryFn: async () =>
      narrowAcquisitionRouteDetail(
        runId,
        routeId,
        await client.getAcquisitionRoute(runId, routeId),
      ),
    queryKey: queryKeys.runAcquisitionRoute(runId, routeId),
  };
}

export function acquisitionAuthorityQueryPolicy() {
  return { kind: "never_cache_authority" } as const;
}

export function useAcquisitionGrowth(
  client: AcquisitionRoutesClient = runtimeAcquisitionRoutesClient,
) {
  return useGovernedQuery(
    governedQueryOptions(
      acquisitionGrowthQueryOptions(client),
      acquisitionAuthorityQueryPolicy(),
    ),
  );
}

export function useAcquisitionRoutes(
  runId: string,
  client: AcquisitionRoutesClient = runtimeAcquisitionRoutesClient,
) {
  return useGovernedQuery(
    governedQueryOptions(
      acquisitionRoutesQueryOptions(runId, client),
      acquisitionAuthorityQueryPolicy(),
    ),
  );
}

export function useAcquisitionRoute(
  runId: string,
  routeId: string,
  client: AcquisitionRoutesClient = runtimeAcquisitionRoutesClient,
) {
  return useGovernedQuery(
    governedQueryOptions(
      acquisitionRouteQueryOptions(runId, routeId, client),
      acquisitionAuthorityQueryPolicy(),
    ),
  );
}

export async function requestAcquisitionDecision(
  runId: string,
  routeId: string,
  body: AcquisitionRouteMutationRequest,
): Promise<AcquisitionDecisionRequestResponse> {
  const response = await captureRuntimeResponse((client) =>
    client.requestRunAcquisitionDecision({
      body,
      route_id: routeId,
      run_id: runId,
    }),
  );
  return acquisitionDecisionRequestResponseSchema.parse(response.packet);
}

export async function executeAcquisitionRoute(
  runId: string,
  routeId: string,
  body: AcquisitionRouteMutationRequest,
): Promise<AcquisitionExecutionResponse> {
  const response = await captureRuntimeResponse((client) =>
    client.executeRunAcquisitionRoute({
      body,
      route_id: routeId,
      run_id: runId,
    }),
  );
  return acquisitionExecutionResponseSchema.parse(response.packet);
}
