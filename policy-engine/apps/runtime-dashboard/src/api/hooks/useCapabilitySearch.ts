import { queryOptions, useQuery } from "@tanstack/react-query";

import { authAwareRuntimeFetch } from "@/app/auth/authSession";
import { runtimeApiClient } from "../client";
import { createRuntimeApiError } from "../http";
import { queryKeys } from "../queryKeys";
import type { components } from "../types";
import {
  capabilityDiscoveryResponseSchema,
  type CapabilityDiscoveryPayload,
} from "../validators";

export type CapabilitySearchRequest =
  components["schemas"]["CapabilityDiscoveryRequest"];

const allCapabilityResourceKinds = [
  "method",
  "dataset",
  "source",
  "legal_norm",
  "case",
  "agent",
] as const;

export function createCapabilitySearchRequest(
  queryText: string,
  requestId: string,
): CapabilitySearchRequest {
  const normalizedQuery = queryText.trim() || "all-capabilities";
  const authorityPurpose = "capability_discovery";
  return {
    audience: "REVIEWER",
    resource_kinds: [...allCapabilityResourceKinds],
    search: {
      allowed_modes: [
        "exact",
        "alias",
        "lexical",
        "semantic",
        "relational",
        "derived",
      ],
      authority_purpose: authorityPurpose,
      construct_refs: [normalizedQuery],
      intent: authorityPurpose,
      query_text: normalizedQuery,
      request_id: requestId,
      required_layers: ["capability_discovery"],
      rule_version: "policyos.capability_discovery.v1",
      schema_version: "policyos.core.contracts.search.v1",
    },
  };
}

export type CapturedCapabilitySearch = Readonly<{
  rawBytes: Uint8Array;
  response: CapabilityDiscoveryPayload;
  serverEpoch: string | null;
}>;

type CapabilitySearchFetch = (request: Request) => Promise<Response>;

function resolveServerEpoch(
  response: CapabilityDiscoveryPayload,
): string | null {
  return response.frontier.index_version_refs[0] ?? null;
}

export async function fetchCapabilitySearch(
  request: CapabilitySearchRequest,
  fetchImpl: CapabilitySearchFetch = authAwareRuntimeFetch,
  baseUrl?: string,
): Promise<CapturedCapabilitySearch> {
  let rawBytes: Uint8Array | null = null;
  const { data, error, response } = await runtimeApiClient.POST(
    "/api/v1/control/capabilities/search",
    {
      baseUrl,
      body: request,
      fetch: async (capturedRequest) => {
        const captured = await fetchImpl(capturedRequest);
        rawBytes = new Uint8Array(await captured.clone().arrayBuffer());
        return captured;
      },
      parseAs: "json",
    },
  );
  if (error || !response.ok || !data) {
    throw createRuntimeApiError(
      response,
      error,
      "Failed to search runtime capabilities",
    );
  }
  if (rawBytes === null) {
    throw new TypeError(
      "contract_error: capability search response bytes were not captured",
    );
  }
  const parsed = capabilityDiscoveryResponseSchema.parse(data);
  return Object.freeze({
    rawBytes: new Uint8Array(rawBytes),
    response: parsed,
    serverEpoch: resolveServerEpoch(parsed),
  });
}

export function capabilitySearchQueryOptions(
  request: CapabilitySearchRequest,
  baseUrl?: string,
  enabled = true,
) {
  return queryOptions({
    enabled,
    queryKey: queryKeys.capabilitySearch(request),
    queryFn: () =>
      fetchCapabilitySearch(request, authAwareRuntimeFetch, baseUrl),
    staleTime: 5_000,
    retry: 1,
  });
}

export function useCapabilitySearch(
  request: CapabilitySearchRequest,
  baseUrl?: string,
  enabled = true,
) {
  return useQuery(capabilitySearchQueryOptions(request, baseUrl, enabled));
}
