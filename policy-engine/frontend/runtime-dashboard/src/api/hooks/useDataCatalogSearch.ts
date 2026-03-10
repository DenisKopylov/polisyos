import { useQuery } from "@tanstack/react-query";

import { runtimeApiClient } from "../client";
import { createRuntimeApiError } from "../http";
import { queryKeys } from "../queryKeys";
import type { components } from "../types";

export type DataCatalogSearchResponse =
  components["schemas"]["DataCatalogSearchResponse"];

type CatalogSearchParams = {
  metricQuery: string;
  geography?: string | null;
  limit?: number;
  enabled?: boolean;
};

async function fetchDataCatalogSearch(
  metricQuery: string,
  geography: string | null,
  limit: number,
): Promise<DataCatalogSearchResponse> {
  const { data, error, response } = await runtimeApiClient.GET(
    "/api/v1/control/data/catalog/search",
    {
      params: {
        query: {
          metric: metricQuery,
          geo: geography || undefined,
          limit,
        },
      },
    },
  );
  if (error || !response.ok || !data) {
    throw createRuntimeApiError(
      response,
      error,
      "Failed to search data catalog",
    );
  }
  return data as DataCatalogSearchResponse;
}

export function useDataCatalogSearch({
  metricQuery,
  geography = null,
  limit = 25,
  enabled = true,
}: CatalogSearchParams) {
  const normalizedQuery = metricQuery.trim();
  return useQuery({
    queryKey: queryKeys.dataCatalogSearch(normalizedQuery, geography, limit),
    queryFn: () => fetchDataCatalogSearch(normalizedQuery, geography, limit),
    enabled: enabled && normalizedQuery.length > 0,
    staleTime: 5_000,
  });
}
