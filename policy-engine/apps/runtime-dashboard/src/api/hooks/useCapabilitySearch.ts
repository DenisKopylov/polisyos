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

const observedEpochByPartition = new Map<string, string>();

function epochPartition(request: CapabilitySearchRequest) {
  return JSON.stringify({
    audience: request.audience,
    authorityPurpose: request.search.authority_purpose,
    resourceKinds: request.resource_kinds,
  });
}

export function createCapabilitySearchRequest(
  queryText: string,
  requestId: string,
): CapabilitySearchRequest {
  const normalizedQuery = queryText.trim();
  const matchAll = normalizedQuery.length === 0;
  const ownerQuery = matchAll ? "*" : normalizedQuery;
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
      budget: matchAll ? { match_all: true } : {},
      construct_refs: [ownerQuery],
      intent: authorityPurpose,
      query_text: ownerQuery,
      request_id: requestId,
      required_layers: ["capability_discovery"],
      rule_version: "policyos.capability_discovery.v1",
      schema_version: "policyos.core.contracts.search.v1",
    },
  };
}

export function withCapabilitySearchQuery(
  request: CapabilitySearchRequest,
  queryText: string,
): CapabilitySearchRequest {
  const normalizedQuery = queryText.trim();
  const matchAll = normalizedQuery.length === 0;
  const ownerQuery = matchAll ? "*" : normalizedQuery;
  const budget = Object.fromEntries(
    Object.entries(request.search.budget ?? {}).filter(
      ([key]) => key !== "match_all",
    ),
  );
  return {
    ...request,
    search: {
      ...request.search,
      budget: matchAll ? { ...budget, match_all: true } : budget,
      construct_refs: [ownerQuery],
      query_text: ownerQuery,
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
  return response.frontier.index_version_refs.length > 0
    ? JSON.stringify([...response.frontier.index_version_refs].sort())
    : null;
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
  const partition = epochPartition(request);
  const observedEpoch = observedEpochByPartition.get(partition) ?? null;
  return queryOptions({
    enabled,
    gcTime: 0,
    queryKey: queryKeys.capabilitySearch(request, observedEpoch),
    queryFn: async () => {
      const captured = await fetchCapabilitySearch(
        request,
        authAwareRuntimeFetch,
        baseUrl,
      );
      if (captured.serverEpoch !== null) {
        observedEpochByPartition.set(partition, captured.serverEpoch);
      }
      return captured;
    },
    refetchOnMount: "always",
    staleTime: 0,
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
