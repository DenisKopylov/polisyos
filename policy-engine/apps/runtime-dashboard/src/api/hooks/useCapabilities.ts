import {
  queryOptions,
  useQuery,
  useSuspenseQuery,
  type UseQueryResult,
} from "@tanstack/react-query";

import { isCapabilityEnabled } from "@/shared/lib/capabilities";
import type { CapabilityManifestPayload } from "@/api/validators";
import { runtimeApiClient } from "../client";
import { createRuntimeApiError } from "../http";
import { queryKeys } from "../queryKeys";
import type { components } from "../types";
import { capabilityManifestSchema } from "../validators";

export type CapabilityManifestResponse =
  components["schemas"]["CapabilityManifestResponse"];

const capabilityDiscoveryBrand: unique symbol = Symbol(
  "owner-issued-capability-discovery",
);
const issuedCapabilityDiscoveries = new WeakSet();

export type CapabilityDiscoveryUnavailableReason =
  | "error"
  | "loading"
  | "missing_data"
  | "offline";

type AvailableCapabilityDiscovery = Readonly<{
  readonly [capabilityDiscoveryBrand]: true;
  readonly manifest: CapabilityManifestPayload;
  readonly state: "available";
}>;

type UnavailableCapabilityDiscovery = Readonly<{
  readonly [capabilityDiscoveryBrand]: true;
  readonly reason: CapabilityDiscoveryUnavailableReason;
  readonly state: "unavailable";
}>;

export type CapabilityDiscovery =
  | AvailableCapabilityDiscovery
  | UnavailableCapabilityDiscovery;

function issueCapabilityDiscovery(
  discovery:
    | Omit<AvailableCapabilityDiscovery, typeof capabilityDiscoveryBrand>
    | Omit<UnavailableCapabilityDiscovery, typeof capabilityDiscoveryBrand>,
): CapabilityDiscovery {
  const issued = Object.freeze({
    ...discovery,
    [capabilityDiscoveryBrand]: true as const,
  });
  issuedCapabilityDiscoveries.add(issued);
  return issued;
}

export function isIssuedCapabilityDiscovery(
  value: unknown,
): value is CapabilityDiscovery {
  return (
    typeof value === "object" &&
    value !== null &&
    Object.isFrozen(value) &&
    issuedCapabilityDiscoveries.has(value)
  );
}

function isCapabilityDiscoveryAvailable(
  discovery: CapabilityDiscovery,
): discovery is AvailableCapabilityDiscovery {
  return (
    isIssuedCapabilityDiscovery(discovery) && discovery.state === "available"
  );
}

export function isDiscoveryCapabilityEnabled(
  discovery: CapabilityDiscovery,
  key: string,
): boolean {
  return (
    isCapabilityDiscoveryAvailable(discovery) &&
    isCapabilityEnabled(discovery.manifest, key)
  );
}

export async function fetchCapabilities(): Promise<CapabilityManifestResponse> {
  const { data, error, response } = await runtimeApiClient.GET(
    "/api/v1/control/capabilities",
    {
      parseAs: "json",
    },
  );

  if (error || !response.ok || !data) {
    throw createRuntimeApiError(
      response,
      error,
      "Failed to load control capability manifest",
    );
  }

  return capabilityManifestSchema.parse(data);
}

export function capabilitiesQueryOptions() {
  return queryOptions({
    queryKey: queryKeys.capabilities(),
    queryFn: fetchCapabilities,
    staleTime: Number.POSITIVE_INFINITY,
    retry: 1,
  });
}

export function useCapabilities() {
  return useQuery(capabilitiesQueryOptions());
}

export function useSuspenseCapabilities() {
  return useSuspenseQuery(capabilitiesQueryOptions());
}

function discoverCapabilities(
  query: UseQueryResult<CapabilityManifestResponse>,
): CapabilityDiscovery {
  if (query.isPaused) {
    return issueCapabilityDiscovery({
      reason: "offline",
      state: "unavailable",
    });
  }
  if (query.isError) {
    return issueCapabilityDiscovery({ reason: "error", state: "unavailable" });
  }
  if (query.isLoading) {
    return issueCapabilityDiscovery({
      reason: "loading",
      state: "unavailable",
    });
  }
  if (!query.data) {
    return issueCapabilityDiscovery({
      reason: "missing_data",
      state: "unavailable",
    });
  }
  return issueCapabilityDiscovery({ manifest: query.data, state: "available" });
}

export function useCapabilityManifestAvailability(): CapabilityDiscovery {
  return discoverCapabilities(useCapabilities());
}
