import { useCallback, useEffect, useMemo, useState } from "react";
import {
  onlineManager,
  useMutation,
  useQueryClient,
} from "@tanstack/react-query";

import { runtimeApiClient } from "@/api/client";
import {
  governedQueryOptions,
  useGovernedQuery,
} from "@/api/governedQueryPolicy";
import { createRuntimeApiError, RuntimeApiRequestError } from "@/api/http";
import { queryKeys } from "@/api/queryKeys";
import type { components, paths } from "@/api/types";
import {
  type HumanDecisionCreateReceipt,
  humanDecisionCreateResponseReceiptSchema,
  humanDecisionGateResponseSchema,
  humanDecisionReviewEffectivenessSchema,
  humanDecisionReplaySelectorSchema,
} from "@/api/validators";
import { authAwareRuntimeFetch } from "@/app/auth/authSession";
import { API_BASE_URL } from "@/shared/lib/constants";

export type HumanDecisionGate =
  components["schemas"]["HumanDecisionGateResponse"];
export type HumanDecisionReplaySelector =
  | components["schemas"]["HumanDecisionPA2ReplaySelector"]
  | components["schemas"]["HumanDecisionProductionReplaySelector"];
export type HumanDecisionMutationRequest =
  components["schemas"]["HumanDecisionMutationRequest"];
export type HumanDecisionReviewEffectiveness =
  components["schemas"]["HumanDecisionReviewEffectivenessResponse"];

export type CapturedHumanDecisionGate = Readonly<{
  packet: HumanDecisionGate;
  rawPacketBytes: Uint8Array;
}>;

export type VerifiedHumanDecisionEvidence = Readonly<{
  bytes: Uint8Array;
  mediaType: string;
}>;

type GateQuery =
  paths["/api/v1/runs/{run_id}/human-decision-gate"]["get"]["parameters"]["query"];
type RuntimeFetch = (request: Request) => Promise<Response>;

const SELECTOR_QUERY_KEYS = [
  "action_kind",
  "basis_digest",
  "decision_request_ref",
  "exposure_session_ref",
  "presentation_contract_ref",
  "principal_binding_ref",
  "production_packet_ref",
  "reviewer_separation_ref",
  "source_ref",
] as const;

function gateResponseMatchesSelector(
  packet: HumanDecisionGate,
  selector: GateQuery,
): boolean {
  const replay = packet.continuation;
  const replayValue = (key: keyof HumanDecisionReplaySelector) =>
    replay && key in replay ? replay[key] : undefined;
  const actionKind =
    replay?.source_kind === "agent_action_authority"
      ? replay.action_kind
      : undefined;
  const replaySelectorsMatch =
    replay === null || replay === undefined
      ? packet.status !== "available"
      : (selector.action_kind === undefined ||
          selector.action_kind === actionKind) &&
        (selector.basis_digest === undefined ||
          selector.basis_digest === replayValue("basis_digest")) &&
        (selector.exposure_session_ref === undefined ||
          selector.exposure_session_ref ===
            replayValue("exposure_session_ref")) &&
        (selector.presentation_contract_ref === undefined ||
          selector.presentation_contract_ref ===
            replayValue("presentation_contract_ref")) &&
        (selector.principal_binding_ref === undefined ||
          selector.principal_binding_ref ===
            replayValue("principal_binding_ref")) &&
        (selector.reviewer_separation_ref === undefined ||
          selector.reviewer_separation_ref ===
            replayValue("reviewer_separation_ref"));
  return (
    packet.source_kind === selector.source_kind &&
    (selector.source_ref === undefined ||
      packet.source_ref === selector.source_ref) &&
    (selector.decision_request_ref === undefined ||
      packet.decision_request_ref === selector.decision_request_ref) &&
    replaySelectorsMatch &&
    (selector.production_packet_ref === undefined ||
      (packet.status === "invalid_source" &&
        packet.reason_codes.includes("DS9-DECISION-SOURCE-INVALID")))
  );
}

function runtimeBaseUrl(): string {
  const origin =
    typeof window === "undefined" ? "http://localhost" : window.location.origin;
  return API_BASE_URL ? new URL(API_BASE_URL, origin).toString() : origin;
}

function humanDecisionRequestError(
  code: string,
  detail: string,
  status = 0,
): RuntimeApiRequestError {
  return new RuntimeApiRequestError(
    {
      code,
      detail,
      error: null,
      instance: null,
      request_id: null,
      status,
      status_code: status,
      title: "Human decision unavailable",
      type: "about:blank",
    },
    status,
    detail,
  );
}

async function sha256Digest(bytes: Uint8Array): Promise<string> {
  if (!globalThis.crypto?.subtle) {
    throw new TypeError("human-decision evidence hashing is unavailable");
  }
  const copy = new Uint8Array(bytes);
  const digest = await globalThis.crypto.subtle.digest("SHA-256", copy.buffer);
  return `sha256:${Array.from(new Uint8Array(digest), (value) =>
    value.toString(16).padStart(2, "0"),
  ).join("")}`;
}

function initialGateSelector(rawSearch: string): GateQuery | null {
  const search = new URLSearchParams(
    rawSearch.startsWith("?") ? rawSearch.slice(1) : rawSearch,
  );
  const sourceKind = search.get("source_kind");
  if (
    sourceKind !== "agent_action_authority" &&
    sourceKind !== "production_approval"
  ) {
    return null;
  }
  const selector: GateQuery = { source_kind: sourceKind };
  for (const key of SELECTOR_QUERY_KEYS) {
    const value = search.get(key);
    if (value) {
      selector[key] = value;
    }
  }
  return Object.freeze(selector);
}

function replayGateSelector(selector: HumanDecisionReplaySelector): GateQuery {
  const verified = humanDecisionReplaySelectorSchema.parse(selector);
  return Object.freeze({
    action_kind:
      verified.source_kind === "agent_action_authority"
        ? verified.action_kind
        : undefined,
    basis_digest: verified.basis_digest,
    decision_request_ref: verified.decision_request_ref,
    exposure_session_ref: verified.exposure_session_ref,
    presentation_contract_ref: verified.presentation_contract_ref,
    principal_binding_ref: verified.principal_binding_ref,
    reviewer_separation_ref: verified.reviewer_separation_ref,
    source_kind: verified.source_kind,
    source_ref: verified.source_ref,
  });
}

function selectorKey(selector: GateQuery | null): string {
  if (!selector) return "absent";
  return JSON.stringify(
    Object.fromEntries(
      Object.entries(selector).sort(([left], [right]) =>
        left.localeCompare(right),
      ),
    ),
  );
}

export async function fetchHumanDecisionGate(
  runId: string,
  selector: GateQuery,
  fetchImpl: RuntimeFetch = authAwareRuntimeFetch,
): Promise<CapturedHumanDecisionGate> {
  let rawPacketBytes: Uint8Array | null = null;
  const { data, error, response } = await runtimeApiClient.GET(
    "/api/v1/runs/{run_id}/human-decision-gate",
    {
      baseUrl: runtimeBaseUrl(),
      fetch: async (request) => {
        const captured = await fetchImpl(request);
        rawPacketBytes = new Uint8Array(await captured.clone().arrayBuffer());
        return captured;
      },
      params: { path: { run_id: runId }, query: selector },
    },
  );
  if (error || !response.ok || !data) {
    throw createRuntimeApiError(
      response,
      error,
      `Failed to resolve the human-decision gate for ${runId}`,
    );
  }
  const packet = humanDecisionGateResponseSchema.parse(
    data,
  ) as HumanDecisionGate;
  if (
    packet.run_id !== runId ||
    !gateResponseMatchesSelector(packet, selector) ||
    rawPacketBytes === null
  ) {
    throw new TypeError(
      "human-decision gate response is not bound to the requested run",
    );
  }
  return Object.freeze({
    packet,
    rawPacketBytes: new Uint8Array(rawPacketBytes),
  });
}

export async function fetchHumanDecisionEvidence(
  runId: string,
  artifactDigest: string,
  exposureSessionRef: string,
  fetchImpl: RuntimeFetch = authAwareRuntimeFetch,
): Promise<VerifiedHumanDecisionEvidence> {
  const origin =
    typeof window === "undefined" ? "http://localhost" : window.location.origin;
  const base = API_BASE_URL
    ? new URL(API_BASE_URL, origin)
    : new URL("/", origin);
  const url = new URL(
    `api/v1/runs/${encodeURIComponent(runId)}/human-decision-evidence/${encodeURIComponent(artifactDigest)}/content`,
    base,
  );
  const response = await fetchImpl(
    new Request(url, {
      headers: {
        Accept: "*/*",
        "X-PolicyOS-Human-Decision-Exposure": exposureSessionRef,
      },
      method: "GET",
    }),
  );
  if (!response.ok) {
    let problem: unknown = null;
    try {
      problem = await response.clone().json();
    } catch {
      problem = null;
    }
    throw createRuntimeApiError(
      response,
      problem,
      "Failed to open required human-decision evidence",
    );
  }
  const returnedSession = response.headers.get("X-PolicyOS-Exposure-Session");
  const returnedDigest = response.headers.get("ETag");
  if (
    returnedSession !== exposureSessionRef ||
    returnedDigest !== `"${artifactDigest}"` ||
    response.headers.get("Cache-Control") !== "no-store" ||
    response.headers.get("Content-Encoding") !== "identity" ||
    response.headers.get("X-Content-Type-Options") !== "nosniff"
  ) {
    throw new TypeError(
      "human-decision evidence response lost its exact custody binding",
    );
  }
  const body = new Uint8Array(await response.arrayBuffer());
  if ((await sha256Digest(body)) !== artifactDigest) {
    throw new TypeError(
      "human-decision evidence bytes do not match the exact CAS digest",
    );
  }
  return Object.freeze({
    bytes: new Uint8Array(body),
    mediaType:
      response.headers.get("Content-Type") ?? "application/octet-stream",
  });
}

export function humanDecisionGateQueryPolicy() {
  return { kind: "never_cache_authority" } as const;
}

export function useHumanDecisionGate(
  runId: string,
  rawSearch: string,
  enabled = true,
) {
  const queryClient = useQueryClient();
  const initialSelector = useMemo(
    () => initialGateSelector(rawSearch),
    [rawSearch],
  );
  const [consumed, setConsumed] = useState(false);
  const [latest, setLatest] = useState<CapturedHumanDecisionGate | null>(null);
  const [online, setOnline] = useState(() => onlineManager.isOnline());
  const key = selectorKey(initialSelector);
  const query = useGovernedQuery(
    governedQueryOptions(
      {
        enabled: enabled && initialSelector !== null && !consumed && online,
        queryFn: () => {
          if (!initialSelector) {
            throw new TypeError("human-decision selector is absent");
          }
          return fetchHumanDecisionGate(runId, initialSelector);
        },
        queryKey: queryKeys.humanDecisionGate(runId, key),
      },
      humanDecisionGateQueryPolicy(),
    ),
  );

  useEffect(() => {
    setConsumed(false);
    setLatest(null);
  }, [key, runId]);
  useEffect(
    () =>
      onlineManager.subscribe((nextOnline) => {
        setOnline(nextOnline);
        if (!nextOnline) {
          setLatest(null);
          queryClient.removeQueries({
            queryKey: ["runtime", "run", runId, "human-decision-gate"],
          });
        }
      }),
    [queryClient, runId],
  );

  const revalidate = useCallback(
    async (selector: HumanDecisionReplaySelector) => {
      if (!onlineManager.isOnline()) {
        setLatest(null);
        throw humanDecisionRequestError(
          "DS9-OFFLINE-REVALIDATION",
          "An online gate replay is required",
        );
      }
      const next = await fetchHumanDecisionGate(
        runId,
        replayGateSelector(selector),
      );
      setLatest(next);
      return next;
    },
    [runId],
  );
  const clear = useCallback(() => {
    setConsumed(true);
    setLatest(null);
    queryClient.removeQueries({
      queryKey: ["runtime", "run", runId, "human-decision-gate"],
    });
  }, [queryClient, runId]);

  return {
    ...query,
    data: consumed || !online ? undefined : (latest ?? query.data),
    clear,
    hasSelector: initialSelector !== null,
    revalidate,
  };
}

export async function createHumanDecision(input: {
  body: HumanDecisionMutationRequest;
  exposureSessionRef: string;
  runId: string;
}): Promise<HumanDecisionCreateReceipt> {
  if (!onlineManager.isOnline()) {
    throw humanDecisionRequestError(
      "DS9-OFFLINE-REVALIDATION",
      "Human decisions are never queued",
    );
  }
  const { data, error, response } = await runtimeApiClient.POST(
    "/api/v1/runs/{run_id}/human-decisions",
    {
      baseUrl: runtimeBaseUrl(),
      body: input.body,
      params: {
        header: {
          "X-PolicyOS-Human-Decision-Exposure": input.exposureSessionRef,
        },
        path: { run_id: input.runId },
      },
    },
  );
  if (error || !response.ok || !data) {
    throw createRuntimeApiError(
      response,
      error,
      `Failed to create a human-decision record for ${input.runId}`,
    );
  }
  const receipt = humanDecisionCreateResponseReceiptSchema.parse(data);
  if (receipt.run_id !== input.runId) {
    throw new TypeError(
      "human-decision create receipt is bound to another run",
    );
  }
  return receipt;
}

export function useCreateHumanDecision(runId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createHumanDecision,
    mutationKey: ["runtime", "run", runId, "human-decision-create"],
    networkMode: "always",
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: queryKeys.humanDecisionReviewEffectiveness(runId),
      });
      queryClient.removeQueries({
        queryKey: ["runtime", "run", runId, "human-decision-gate"],
      });
    },
  });
}

export async function fetchReviewEffectiveness(
  runId: string,
): Promise<HumanDecisionReviewEffectiveness> {
  const { data, error, response } = await runtimeApiClient.GET(
    "/api/v1/runs/{run_id}/human-decisions/review-effectiveness",
    {
      baseUrl: runtimeBaseUrl(),
      params: { path: { run_id: runId } },
    },
  );
  if (error || !response.ok || !data) {
    throw createRuntimeApiError(
      response,
      error,
      `Failed to load review-effectiveness telemetry for ${runId}`,
    );
  }
  const report = humanDecisionReviewEffectivenessSchema.parse(
    data,
  ) as HumanDecisionReviewEffectiveness;
  if (report.run_id !== runId) {
    throw new TypeError("review-effectiveness report is bound to another run");
  }
  return report;
}

export function useHumanDecisionReviewEffectiveness(
  runId: string,
  enabled = true,
) {
  return useGovernedQuery(
    governedQueryOptions(
      {
        enabled,
        queryFn: () => fetchReviewEffectiveness(runId),
        queryKey: queryKeys.humanDecisionReviewEffectiveness(runId),
      },
      { kind: "operational" },
    ),
  );
}
