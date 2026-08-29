import { RuntimeApiClient } from "@polisyos/runtime-api-client";

import { queryKeys } from "@/api/queryKeys";
import {
  governedQueryOptions,
  useGovernedQuery,
} from "@/api/governedQueryPolicy";
import { authAwareRuntimeFetch } from "@/app/auth/authSession";
import {
  admitConfidenceLedgerRiskSpendPacket,
  type ConfidenceLedgerRiskSpendPacket,
} from "@/features/runs/domain/confidenceLedgerRiskSpend";
import { API_BASE_URL } from "@/shared/lib/constants";

type CapturedConfidenceLedgerRiskSpend = Readonly<{
  packet: unknown;
  rawPacketBytes: Uint8Array;
}>;

type ConfidenceLedgerRiskSpendClient = Readonly<{
  getConfidenceLedgerRiskSpendProjection: (
    params: Record<string, never>,
  ) => Promise<CapturedConfidenceLedgerRiskSpend>;
}>;

export type ConfidenceLedgerRiskSpendProjection = Readonly<{
  packet: ConfidenceLedgerRiskSpendPacket;
  rawPacketBytes: Uint8Array;
}>;

function runtimeApiBaseUrl(): string {
  const applicationOrigin =
    typeof window === "undefined" ? "http://localhost" : window.location.origin;
  return API_BASE_URL
    ? new URL(API_BASE_URL, applicationOrigin).toString()
    : applicationOrigin;
}

const confidenceLedgerRiskSpendClient: ConfidenceLedgerRiskSpendClient = {
  async getConfidenceLedgerRiskSpendProjection(params) {
    let rawPacketBytes: Uint8Array | null = null;
    const client = new RuntimeApiClient({
      baseUrl: runtimeApiBaseUrl(),
      fetchImpl: async (input, init) => {
        const response = await authAwareRuntimeFetch(new Request(input, init));
        rawPacketBytes = new Uint8Array(await response.clone().arrayBuffer());
        return response;
      },
    });
    const packet = await client.getConfidenceLedgerRiskSpendProjection(params);
    if (rawPacketBytes === null) {
      throw new TypeError(
        "contract_error: confidence-ledger response bytes were not captured",
      );
    }
    return Object.freeze({ packet, rawPacketBytes });
  },
};

/** Prepare the protected specialized projection query. */
export function confidenceLedgerRiskSpendQueryOptions(
  client: ConfidenceLedgerRiskSpendClient,
) {
  return {
    queryKey: queryKeys.confidenceLedgerRiskSpendProjection(),
    queryFn: async (): Promise<ConfidenceLedgerRiskSpendProjection> => {
      const response = await client.getConfidenceLedgerRiskSpendProjection({});
      const packet = await admitConfidenceLedgerRiskSpendPacket(
        response.packet,
      );
      return Object.freeze({ packet, rawPacketBytes: response.rawPacketBytes });
    },
  };
}

/** Authority-bearing risk spend is never retained between observations. */
export function confidenceLedgerRiskSpendQueryPolicy() {
  return { kind: "never_cache_authority" } as const;
}

/** Fetch the protected confidence-ledger projection after reviewer authorization. */
export function useConfidenceLedgerRiskSpend(
  client: ConfidenceLedgerRiskSpendClient = confidenceLedgerRiskSpendClient,
) {
  return useGovernedQuery(
    governedQueryOptions(
      confidenceLedgerRiskSpendQueryOptions(client),
      confidenceLedgerRiskSpendQueryPolicy(),
    ),
  );
}
