import { RuntimeApiClient } from "@polisyos/runtime-api-client";

import {
  governedQueryOptions,
  useGovernedQuery,
} from "@/api/governedQueryPolicy";
import { authAwareRuntimeFetch } from "@/app/auth/authSession";
import { API_BASE_URL } from "@/shared/lib/constants";
import {
  temporalScopeKey,
  toApiTemporalParams,
  type TemporalScope,
} from "@/shared/lib/domain/temporal";

import {
  admitEpochStalenessResponseBytes,
  type AdmittedEpochStalenessProjection,
  type AdmittedEpochStalenessResponse,
} from "../domain/epochStaleness";

export type CapturedEpochStaleness = Readonly<{
  response: AdmittedEpochStalenessResponse;
  projection: AdmittedEpochStalenessProjection;
  rawBytes: Uint8Array;
}>;

export type EpochStalenessRequest = Readonly<{
  runId: string;
  temporalScope?: TemporalScope | null;
  exportProjectionHash?: string | null;
}>;

type RuntimeFetch = (request: Request) => Promise<Response>;

export type EpochStalenessClient = Readonly<{
  getRunEpochStaleness: (
    request: EpochStalenessRequest,
  ) => Promise<CapturedEpochStaleness>;
}>;

function runtimeApiBaseUrl(): string {
  const origin =
    typeof window === "undefined" ? "http://localhost" : window.location.origin;
  return API_BASE_URL ? new URL(API_BASE_URL, origin).toString() : origin;
}

/** Build the generated-client bridge that captures response bytes before JSON parse. */
export function createEpochStalenessClient(input: {
  baseUrl: string;
  fetchRuntime: RuntimeFetch;
}): EpochStalenessClient {
  return {
    async getRunEpochStaleness(request) {
      let capturedBytes: Uint8Array | null = null;
      const client = new RuntimeApiClient({
        baseUrl: input.baseUrl,
        fetchImpl: async (requestInfo, requestInit) => {
          const response = await input.fetchRuntime(
            new Request(requestInfo, requestInit),
          );
          const responseBuffer = await response.clone().arrayBuffer();
          capturedBytes = new Uint8Array(responseBuffer).slice();
          return response;
        },
      });
      const generatedResponse = await client.getRunEpochStaleness({
        run_id: request.runId,
        ...toApiTemporalParams(request.temporalScope),
        export_projection_hash: request.exportProjectionHash ?? undefined,
      });
      if (capturedBytes === null) {
        throw new TypeError(
          "contract_error: epoch staleness response bytes were not captured",
        );
      }
      const admitted = await admitEpochStalenessResponseBytes(capturedBytes);
      if (
        admitted.response.projection.run_id !== request.runId ||
        (request.exportProjectionHash !== null &&
          request.exportProjectionHash !== undefined &&
          admitted.response.projection.projection_semantic_hash !==
            request.exportProjectionHash)
      ) {
        throw new TypeError(
          "contract_error: epoch staleness response differs from requested replay identity",
        );
      }
      if (
        generatedResponse.projection.run_id !==
          admitted.response.projection.run_id ||
        generatedResponse.projection.projection_semantic_hash !==
          admitted.response.projection.projection_semantic_hash
      ) {
        throw new TypeError(
          "contract_error: generated epoch client differs from captured response",
        );
      }
      return Object.freeze({
        response: admitted.response,
        projection: admitted.response.projection,
        rawBytes: admitted.rawBytes.slice(),
      });
    },
  };
}

const defaultEpochStalenessClient = createEpochStalenessClient({
  baseUrl: runtimeApiBaseUrl(),
  fetchRuntime: authAwareRuntimeFetch,
});

/** Prepare a never-retained query for exact epoch semantics and captured MACHINE bytes. */
export function epochStalenessQueryOptions(
  client: EpochStalenessClient,
  request: EpochStalenessRequest,
) {
  return {
    queryKey: [
      "runtime",
      "run",
      request.runId,
      "epoch-staleness",
      {
        exportProjectionHash: request.exportProjectionHash ?? null,
        temporal: temporalScopeKey(request.temporalScope),
      },
    ] as const,
    queryFn: () => client.getRunEpochStaleness(request),
  };
}

/** Load strict epoch semantics and exact MACHINE bytes without retaining authority. */
export function useEpochStaleness(
  request: EpochStalenessRequest,
  client: EpochStalenessClient = defaultEpochStalenessClient,
) {
  return useGovernedQuery(
    governedQueryOptions(epochStalenessQueryOptions(client, request), {
      kind: "never_cache_authority",
    }),
  );
}
