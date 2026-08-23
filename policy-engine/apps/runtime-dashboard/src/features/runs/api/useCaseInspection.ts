import { runtimeApiClient } from "@/api/client";
import {
  governedQueryOptions,
  useGovernedQuery,
} from "@/api/governedQueryPolicy";
import { createRuntimeApiError } from "@/api/http";
import { authAwareRuntimeFetch } from "@/app/auth/authSession";
import {
  type CapturedRunPaper,
  narrowCapturedRunPaper,
} from "@/features/runs/api/useRunPaper";
import { API_BASE_URL } from "@/shared/lib/constants";

export type CaseInspectionClient = Readonly<{
  getCaseInspection: (
    runId: string,
    rawSearch: string,
  ) => Promise<CapturedRunPaper>;
}>;

type CaseInspectionFetch = (request: Request) => Promise<Response>;

export async function fetchCaseInspection(
  runId: string,
  rawSearch: string,
  fetchImpl: CaseInspectionFetch = authAwareRuntimeFetch,
): Promise<CapturedRunPaper> {
  const serializedQuery = rawSearch.startsWith("?")
    ? rawSearch.slice(1)
    : rawSearch;
  const applicationOrigin =
    typeof window === "undefined" ? "http://localhost" : window.location.origin;
  const baseUrl = API_BASE_URL
    ? new URL(API_BASE_URL, applicationOrigin).toString()
    : applicationOrigin;
  let rawPacketBytes: Uint8Array | null = null;
  const { data, error, response } = await runtimeApiClient.GET(
    "/api/v1/runs/{run_id}/case-inspection",
    {
      baseUrl,
      fetch: async (request) => {
        const captured = await fetchImpl(request);
        rawPacketBytes = new Uint8Array(await captured.clone().arrayBuffer());
        return captured;
      },
      params: { path: { run_id: runId } },
      querySerializer: () => serializedQuery,
    },
  );
  if (error || !response.ok || !data) {
    throw createRuntimeApiError(
      response,
      error,
      "Failed to load the replay-bound case inspection packet",
    );
  }
  return narrowCapturedRunPaper(runId, data, rawPacketBytes);
}

const runtimeCaseInspectionClient: CaseInspectionClient = Object.freeze({
  getCaseInspection: fetchCaseInspection,
});

export function caseInspectionQueryOptions(
  client: CaseInspectionClient,
  runId: string,
  rawSearch: string,
) {
  return {
    queryKey: [
      "runtime",
      "run",
      runId,
      "case-inspection",
      { rawReplaySearch: rawSearch },
    ] as const,
    queryFn: () => client.getCaseInspection(runId, rawSearch),
  };
}

export function caseInspectionQueryPolicy() {
  return { kind: "never_cache_authority" } as const;
}

export function useCaseInspection(
  runId: string,
  rawSearch: string,
  client: CaseInspectionClient = runtimeCaseInspectionClient,
) {
  return useGovernedQuery(
    governedQueryOptions(
      caseInspectionQueryOptions(client, runId, rawSearch),
      caseInspectionQueryPolicy(),
    ),
  );
}
