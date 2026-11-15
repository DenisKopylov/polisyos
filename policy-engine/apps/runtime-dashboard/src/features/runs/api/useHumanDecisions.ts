import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react";
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
  coreArtifactRefSchema,
  humanDecisionDigestSchema,
  type HumanDecisionCreateReceipt,
  humanDecisionCreateResponseReceiptSchema,
  humanDecisionGateResponseSchema,
  humanDecisionReviewEffectivenessSchema,
  humanDecisionReplaySelectorSchema,
} from "@/api/validators";
import { authAwareRuntimeFetch } from "@/app/auth/authSession";
import { API_BASE_URL } from "@/shared/lib/constants";

export type { HumanDecisionCreateReceipt };

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
type HumanDecisionCreateInput = Readonly<{
  body: HumanDecisionMutationRequest;
  exposureSessionRef: string;
  runId: string;
}>;
type HumanDecisionRecoveryResponse =
  paths["/api/v1/runs/{run_id}/human-decisions/recovery"]["post"]["responses"][200]["content"]["application/json"];
type HumanDecisionRecoveryCommitted = Extract<
  HumanDecisionRecoveryResponse,
  { status: "committed" }
>;
export type HumanDecisionSubmissionResult =
  | Readonly<{
      kind: "created";
      receipt: HumanDecisionCreateReceipt;
    }>
  | Readonly<{
      kind: "recovered_committed";
      receipt: HumanDecisionCreateReceipt;
      recovery: HumanDecisionRecoveryCommitted;
    }>
  | Readonly<{
      kind: "recovery_pending";
      recovery: Extract<HumanDecisionRecoveryResponse, { status: "pending" }>;
    }>
  | Readonly<{
      kind: "recovery_not_established";
      recovery: Extract<
        HumanDecisionRecoveryResponse,
        { status: "not_established" }
      >;
    }>
  | Readonly<{
      kind: "recovered_expired";
      receipt: HumanDecisionCreateReceipt;
      recovery: HumanDecisionRecoveryCommitted;
    }>;
export type HumanDecisionRecoveryPosture =
  | Extract<
      HumanDecisionSubmissionResult,
      { kind: "recovery_pending" | "recovery_not_established" }
    >
  | Readonly<{ kind: "recovery_unavailable"; code: string }>;
type RuntimeFetch = (request: Request) => Promise<Response>;

export class HumanDecisionRecoveryAttemptError extends Error {
  readonly code: string;
  readonly status: number;

  constructor(code: string, status: number, message: string, cause: unknown) {
    super(message, { cause });
    this.name = "HumanDecisionRecoveryAttemptError";
    this.code = code;
    this.status = status;
  }
}

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

export const HUMAN_DECISION_OWNED_QUERY_KEYS = Object.freeze([
  "source_kind",
  ...SELECTOR_QUERY_KEYS,
  "appeal_case_id",
] as const);

const humanDecisionOwnedQueryKeySet = new Set<string>(
  HUMAN_DECISION_OWNED_QUERY_KEYS,
);

function decodedQueryKey(segment: string): string | null {
  const separator = segment.indexOf("=");
  const encoded = separator === -1 ? segment : segment.slice(0, separator);
  try {
    return decodeURIComponent(encoded.replace(/\+/g, " "));
  } catch {
    return null;
  }
}

/** Removes only query items owned by the human-decision workspace. */
export function withoutHumanDecisionOwnedQuery(rawSearch: string): string {
  const prefixed = rawSearch.startsWith("?");
  const serialized = prefixed ? rawSearch.slice(1) : rawSearch;
  if (!serialized) {
    return "";
  }
  const retained = serialized.split("&").filter((segment) => {
    const key = decodedQueryKey(segment);
    return key === null || !humanDecisionOwnedQueryKeySet.has(key);
  });
  if (retained.length === 0) {
    return "";
  }
  return `${prefixed ? "?" : ""}${retained.join("&")}`;
}

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

function exactHumanDecisionInput(
  input: HumanDecisionCreateInput,
): HumanDecisionCreateInput {
  return Object.freeze({
    body: Object.freeze({ ...input.body }),
    exposureSessionRef: input.exposureSessionRef,
    runId: input.runId,
  });
}

function isCustodyNonreceipt(error: unknown): error is RuntimeApiRequestError {
  return (
    error instanceof RuntimeApiRequestError &&
    error.status === 503 &&
    error.code === "human_decision_custody_nonreceipt"
  );
}

function recoveredReceiptMatchesInput(
  recovery: HumanDecisionRecoveryCommitted,
  input: HumanDecisionCreateInput,
): boolean {
  const selectedRef = coreArtifactRefSchema.safeParse(recovery.record_ref);
  return (
    recovery.run_id === input.runId &&
    !recovery.operational_authority &&
    recovery.authority_purpose === "historical_human_decision_custody_only" &&
    recovery.schema_version === "policyos.runtime.human_decision_recovery.v1" &&
    recovery.status === "committed" &&
    selectedRef.success &&
    selectedRef.data.kind === "runtime_quality.agent_action_human_decision" &&
    selectedRef.data.media_type === "application/json" &&
    typeof selectedRef.data.manifest_profile_sha256 === "string" &&
    selectedRef.data.artifact_id === recovery.record_digest &&
    humanDecisionDigestSchema.safeParse(recovery.record_digest).success &&
    humanDecisionDigestSchema.safeParse(recovery.binding_sha256).success &&
    recovery.reservation_id.length > 0 &&
    Number.isInteger(recovery.reservation_version) &&
    recovery.reservation_version > 0 &&
    recovery.durable_event_id.length > 0 &&
    [
      "policyos.runtime.human_decision_submission_binding.v2",
      "legacy_record_v2",
    ].includes(recovery.binding_rule)
  );
}

function hasExactRecoveryShape(
  value: unknown,
): value is HumanDecisionRecoveryResponse {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    return false;
  }
  const recovery = value as Record<string, unknown>;
  if (
    recovery.status !== "pending" &&
    recovery.status !== "not_established" &&
    recovery.status !== "committed"
  ) {
    return false;
  }
  const common = [
    "authority_purpose",
    "cell_id",
    "operational_authority",
    "run_id",
    "schema_version",
    "status",
    "tenant_id",
  ];
  const additional =
    recovery.status === "pending"
      ? [
          "binding_rule",
          "binding_sha256",
          "reservation_id",
          "reservation_version",
        ]
      : recovery.status === "not_established"
        ? ["reason_code"]
        : [
            "binding_rule",
            "binding_sha256",
            "durable_event_id",
            "record_digest",
            "record_ref",
            "record_valid_until",
            "reservation_id",
            "reservation_state",
            "reservation_version",
          ];
  const expected = new Set([...common, ...additional]);
  if (
    Object.keys(recovery).length !== expected.size ||
    !Object.keys(recovery).every((key) => expected.has(key)) ||
    recovery.authority_purpose !== "historical_human_decision_custody_only" ||
    (recovery.cell_id !== null &&
      (typeof recovery.cell_id !== "string" ||
        recovery.cell_id.length === 0)) ||
    recovery.operational_authority !== false ||
    typeof recovery.run_id !== "string" ||
    recovery.run_id.length === 0 ||
    recovery.schema_version !== "policyos.runtime.human_decision_recovery.v1" ||
    typeof recovery.tenant_id !== "string" ||
    recovery.tenant_id.length === 0
  ) {
    return false;
  }
  if (recovery.status === "pending") {
    return (
      recovery.binding_rule ===
        "policyos.runtime.human_decision_submission_binding.v2" &&
      humanDecisionDigestSchema.safeParse(recovery.binding_sha256).success &&
      typeof recovery.reservation_id === "string" &&
      recovery.reservation_id.length > 0 &&
      Number.isInteger(recovery.reservation_version) &&
      Number(recovery.reservation_version) >= 1
    );
  }
  if (recovery.status === "not_established") {
    return (
      typeof recovery.reason_code === "string" &&
      recovery.reason_code.length > 0
    );
  }
  const selectedRef = coreArtifactRefSchema.safeParse(recovery.record_ref);
  return (
    (recovery.binding_rule ===
      "policyos.runtime.human_decision_submission_binding.v2" ||
      recovery.binding_rule === "legacy_record_v2") &&
    humanDecisionDigestSchema.safeParse(recovery.binding_sha256).success &&
    typeof recovery.durable_event_id === "string" &&
    recovery.durable_event_id.length > 0 &&
    humanDecisionDigestSchema.safeParse(recovery.record_digest).success &&
    selectedRef.success &&
    typeof recovery.record_valid_until === "string" &&
    Number.isFinite(Date.parse(recovery.record_valid_until)) &&
    typeof recovery.reservation_id === "string" &&
    recovery.reservation_id.length > 0 &&
    (recovery.reservation_state === "committed" ||
      recovery.reservation_state === "expired") &&
    Number.isInteger(recovery.reservation_version) &&
    Number(recovery.reservation_version) >= 1
  );
}

async function readRecoveredHumanDecisionRecord(
  input: HumanDecisionCreateInput,
  recovery: HumanDecisionRecoveryCommitted,
): Promise<HumanDecisionCreateReceipt> {
  // The authenticated server reader verifies the selected CAS blob and signature.
  // The dashboard reconciles the typed record to the saved submission; it does not
  // claim that FastAPI's JSON serialization is the original canonical CAS byte stream.
  const { data, error, response } = await runtimeApiClient.GET(
    "/api/v1/runs/{run_id}/human-decisions",
    {
      baseUrl: runtimeBaseUrl(),
      params: {
        path: { run_id: input.runId },
        query: {
          manifest_profile_sha256: recovery.record_ref.manifest_profile_sha256,
          record_ref: recovery.record_ref.artifact_id,
        },
      },
    },
  );
  if (error || !response.ok || !data) {
    throw createRuntimeApiError(
      response,
      error,
      `Failed to read the recovered human-decision record for ${input.runId}`,
    );
  }
  if (
    data.tenant_id !== recovery.tenant_id ||
    data.run_id !== input.runId ||
    data.binding_sha256 !== recovery.binding_sha256 ||
    data.reservation_id !== recovery.reservation_id ||
    data.reservation_version !== recovery.reservation_version ||
    data.exposure_session_ref !== input.exposureSessionRef ||
    data.decision_action_exercised !== input.body.action ||
    data.decision_mode !== input.body.decision_mode ||
    data.accountability_statement !== input.body.accountability_statement ||
    data.dissent_statement !== input.body.dissent_statement ||
    data.override_reason !== input.body.override_reason ||
    data.blocking_reason !== input.body.blocking_reason ||
    data.source_kind !== input.body.source_kind ||
    data.source_ref !== input.body.source_ref ||
    data.source_digest !== input.body.source_ref ||
    data.human_decision_request_ref !== input.body.decision_request_ref ||
    data.decision_request_digest !== input.body.decision_request_digest ||
    data.basis_ref !== input.body.basis_ref ||
    data.basis_digest !== input.body.basis_digest ||
    data.principal_binding_ref !== input.body.principal_binding_ref ||
    data.principal_binding_digest !== input.body.principal_binding_ref ||
    data.reviewer_separation_ref !== input.body.reviewer_separation_ref ||
    data.reviewer_separation_digest !== input.body.reviewer_separation_ref ||
    data.presentation_contract_ref !== input.body.presentation_contract_ref ||
    data.presentation_contract_digest !==
      input.body.presentation_contract_ref ||
    data.exposure_session_digest !== input.exposureSessionRef ||
    typeof data.actor_ref !== "string" ||
    data.actor_ref.length === 0
  ) {
    throw humanDecisionRequestError(
      "human_decision_recovery_record_mismatch",
      "Recovered custody does not match the exact submitted record",
      409,
    );
  }
  return humanDecisionCreateResponseReceiptSchema.parse({
    durable_event_id: recovery.durable_event_id,
    record: data,
    record_digest: recovery.record_digest,
    record_ref: recovery.record_ref.artifact_id,
    reservation_id: recovery.reservation_id,
    reservation_version: recovery.reservation_version,
    run_id: recovery.run_id,
  });
}

async function recoverHumanDecisionSubmission(
  input: HumanDecisionCreateInput,
): Promise<HumanDecisionSubmissionResult> {
  let recovery: HumanDecisionRecoveryResponse;
  try {
    const result = await runtimeApiClient.POST(
      "/api/v1/runs/{run_id}/human-decisions/recovery",
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
    if (result.error || !result.response.ok || !result.data) {
      throw createRuntimeApiError(
        result.response,
        result.error,
        `Failed to recover the human-decision receipt for ${input.runId}`,
      );
    }
    recovery = result.data;
  } catch (error) {
    throw recoveryAttemptError(error);
  }

  if (!hasExactRecoveryShape(recovery)) {
    throw recoveryAttemptError(
      humanDecisionRequestError(
        "human_decision_recovery_response_invalid",
        "The recovery response has an unknown status or malformed fields",
        409,
      ),
    );
  }
  if (
    recovery.run_id !== input.runId ||
    recovery.schema_version !== "policyos.runtime.human_decision_recovery.v1" ||
    recovery.operational_authority ||
    recovery.authority_purpose !== "historical_human_decision_custody_only"
  ) {
    throw recoveryAttemptError(
      humanDecisionRequestError(
        "human_decision_recovery_scope_mismatch",
        "Recovery is not bound to this run or is not custody-only",
        409,
      ),
    );
  }
  if (recovery.status === "pending") {
    if (
      recovery.binding_rule !==
        "policyos.runtime.human_decision_submission_binding.v2" ||
      !humanDecisionDigestSchema.safeParse(recovery.binding_sha256).success ||
      recovery.reservation_id.length === 0 ||
      !Number.isInteger(recovery.reservation_version) ||
      recovery.reservation_version < 1
    ) {
      throw recoveryAttemptError(
        humanDecisionRequestError(
          "human_decision_recovery_response_invalid",
          "The pending recovery response is incomplete or malformed",
          409,
        ),
      );
    }
    return { kind: "recovery_pending", recovery };
  }
  if (recovery.status === "not_established") {
    if (recovery.reason_code.length === 0) {
      throw recoveryAttemptError(
        humanDecisionRequestError(
          "human_decision_recovery_response_invalid",
          "The unestablished recovery response has no reason code",
          409,
        ),
      );
    }
    return { kind: "recovery_not_established", recovery };
  }
  if (!recoveredReceiptMatchesInput(recovery, input)) {
    throw recoveryAttemptError(
      humanDecisionRequestError(
        "human_decision_recovery_scope_mismatch",
        "Recovered record reference is not bound to the original submission",
        409,
      ),
    );
  }

  let receipt: HumanDecisionCreateReceipt;
  try {
    receipt = await readRecoveredHumanDecisionRecord(input, recovery);
  } catch (error) {
    throw recoveryAttemptError(error);
  }
  const validUntil = Date.parse(recovery.record_valid_until);
  if (!Number.isFinite(validUntil)) {
    throw recoveryAttemptError(
      humanDecisionRequestError(
        "human_decision_recovery_validity_not_established",
        "The recovered record has no usable validity boundary",
        409,
      ),
    );
  }
  if (recovery.reservation_state === "expired" || validUntil <= Date.now()) {
    return { kind: "recovered_expired", receipt, recovery };
  }
  return { kind: "recovered_committed", receipt, recovery };
}

function recoveryAttemptError(
  error: unknown,
): HumanDecisionRecoveryAttemptError {
  if (error instanceof HumanDecisionRecoveryAttemptError) return error;
  if (error instanceof RuntimeApiRequestError) {
    return new HumanDecisionRecoveryAttemptError(
      error.code,
      error.status,
      error.detail,
      error,
    );
  }
  if (
    typeof error === "object" &&
    error !== null &&
    "code" in error &&
    typeof error.code === "string"
  ) {
    return new HumanDecisionRecoveryAttemptError(
      error.code,
      "status" in error && typeof error.status === "number" ? error.status : 0,
      error instanceof Error ? error.message : error.code,
      error,
    );
  }
  return new HumanDecisionRecoveryAttemptError(
    "human_decision_recovery_unavailable",
    0,
    error instanceof Error
      ? error.message
      : "The original human-decision receipt remains unresolved",
    error,
  );
}

export async function createHumanDecision(
  input: HumanDecisionCreateInput,
): Promise<HumanDecisionSubmissionResult> {
  if (!onlineManager.isOnline()) {
    throw humanDecisionRequestError(
      "DS9-OFFLINE-REVALIDATION",
      "Human decisions are never queued",
    );
  }
  const savedInput = exactHumanDecisionInput(input);
  try {
    const { data, error, response } = await runtimeApiClient.POST(
      "/api/v1/runs/{run_id}/human-decisions",
      {
        baseUrl: runtimeBaseUrl(),
        body: savedInput.body,
        params: {
          header: {
            "X-PolicyOS-Human-Decision-Exposure": savedInput.exposureSessionRef,
          },
          path: { run_id: savedInput.runId },
        },
      },
    );
    if (error || !response.ok || !data) {
      throw createRuntimeApiError(
        response,
        error,
        `Failed to create a human-decision record for ${savedInput.runId}`,
      );
    }
    const receipt = humanDecisionCreateResponseReceiptSchema.parse(data);
    if (receipt.run_id !== savedInput.runId) {
      throw new TypeError(
        "human-decision create receipt is bound to another run",
      );
    }
    return { kind: "created", receipt };
  } catch (error) {
    if (!isCustodyNonreceipt(error)) {
      throw error;
    }
    try {
      return await recoverHumanDecisionSubmission(savedInput);
    } catch (recoveryError) {
      throw recoveryAttemptError(recoveryError);
    }
  }
}

export function useCreateHumanDecision(runId: string) {
  const queryClient = useQueryClient();
  const pendingInput = useRef<HumanDecisionCreateInput | null>(null);
  const activeRunId = useRef(runId);
  const [recoveryPosture, setRecoveryPosture] =
    useState<HumanDecisionRecoveryPosture | null>(null);

  useLayoutEffect(() => {
    activeRunId.current = runId;
    pendingInput.current = null;
    setRecoveryPosture(null);
  }, [runId]);

  const mutation = useMutation({
    mutationFn: async (input: HumanDecisionCreateInput) => {
      if (input.runId !== runId) {
        throw humanDecisionRequestError(
          "human_decision_submission_run_mismatch",
          "The saved submission belongs to another run",
          409,
        );
      }
      if (pendingInput.current && pendingInput.current.runId !== runId) {
        pendingInput.current = null;
        setRecoveryPosture(null);
      }
      if (pendingInput.current !== null) {
        throw humanDecisionRequestError(
          "human_decision_recovery_pending",
          "Resolve the saved human-decision submission before starting another",
          409,
        );
      }
      const savedInput = exactHumanDecisionInput(input);
      try {
        const result = await createHumanDecision(savedInput);
        if (activeRunId.current !== runId) {
          throw humanDecisionRequestError(
            "human_decision_submission_run_mismatch",
            "The route changed before the saved submission was resolved",
            409,
          );
        }
        if (
          result.kind === "recovery_pending" ||
          result.kind === "recovery_not_established"
        ) {
          pendingInput.current = savedInput;
          setRecoveryPosture(result);
        } else {
          pendingInput.current = null;
          setRecoveryPosture(null);
        }
        return result;
      } catch (error) {
        if (
          activeRunId.current === runId &&
          error instanceof HumanDecisionRecoveryAttemptError
        ) {
          pendingInput.current = savedInput;
          setRecoveryPosture({
            code: error.code,
            kind: "recovery_unavailable",
          });
        }
        throw error;
      }
    },
    mutationKey: ["runtime", "run", runId, "human-decision-create"],
    networkMode: "always",
    onSuccess: async (result) => {
      if (activeRunId.current !== runId) return;
      if (
        result.kind === "recovery_pending" ||
        result.kind === "recovery_not_established"
      ) {
        return;
      }
      await queryClient.invalidateQueries({
        queryKey: queryKeys.humanDecisionReviewEffectiveness(runId),
      });
      queryClient.removeQueries({
        queryKey: ["runtime", "run", runId, "human-decision-gate"],
      });
    },
  });

  const recoverPending = useCallback(async () => {
    if (activeRunId.current !== runId) {
      throw humanDecisionRequestError(
        "human_decision_recovery_run_mismatch",
        "The route changed before the saved submission was resolved",
        409,
      );
    }
    const savedInput = pendingInput.current;
    if (!savedInput) {
      throw humanDecisionRequestError(
        "human_decision_recovery_not_pending",
        "There is no unresolved human-decision submission to recover",
        409,
      );
    }
    if (savedInput.runId !== runId) {
      pendingInput.current = null;
      setRecoveryPosture(null);
      throw humanDecisionRequestError(
        "human_decision_recovery_run_mismatch",
        "The saved submission belongs to another run",
        409,
      );
    }
    try {
      const result = await recoverHumanDecisionSubmission(savedInput);
      if (activeRunId.current !== runId) {
        throw humanDecisionRequestError(
          "human_decision_recovery_run_mismatch",
          "The route changed before the saved submission was resolved",
          409,
        );
      }
      if (
        result.kind === "recovery_pending" ||
        result.kind === "recovery_not_established"
      ) {
        setRecoveryPosture(result);
        return result;
      }
      pendingInput.current = null;
      setRecoveryPosture(null);
      await queryClient.invalidateQueries({
        queryKey: queryKeys.humanDecisionReviewEffectiveness(runId),
      });
      queryClient.removeQueries({
        queryKey: ["runtime", "run", runId, "human-decision-gate"],
      });
      return result;
    } catch (error) {
      if (activeRunId.current !== runId) throw error;
      const recoveryError = recoveryAttemptError(error);
      setRecoveryPosture({
        code: recoveryError.code,
        kind: "recovery_unavailable",
      });
      throw recoveryError;
    }
  }, [queryClient, runId]);

  return {
    ...mutation,
    recoverPending,
    recoveryPosture,
  };
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
