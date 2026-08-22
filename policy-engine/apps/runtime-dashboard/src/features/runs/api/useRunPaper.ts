import type { components } from "@/api/types";

import { runtimeApiClient } from "@/api/client";
import { createRuntimeApiError } from "@/api/http";
import { queryKeys } from "@/api/queryKeys";
import {
  governedQueryOptions,
  useGovernedQuery,
} from "@/api/governedQueryPolicy";
import { authAwareRuntimeFetch } from "@/app/auth/authSession";
import { API_BASE_URL } from "@/shared/lib/constants";

export type RunPaperPacket = components["schemas"]["RunPaperPacket"];

export type CapturedRunPaper = Readonly<{
  packet: RunPaperPacket;
  rawPacketBytes: Uint8Array;
}>;

export type RunPaperClient = Readonly<{
  getRunPaper: (runId: string, rawSearch: string) => Promise<CapturedRunPaper>;
}>;

type PaperFetch = (request: Request) => Promise<Response>;

const RUN_PAPER_CASE_DENIED_USES = [
  "case_identity",
  "design_record",
  "grounding_state",
  "admission_state",
  "promotion_state",
  "blockers",
  "limitations",
  "objections",
  "abstentions",
] as const;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function hasExactKeys(
  value: Record<string, unknown>,
  keys: readonly string[],
): boolean {
  const actual = Object.keys(value).sort();
  const expected = [...keys].sort();
  return (
    actual.length === expected.length &&
    actual.every((key, index) => key === expected[index])
  );
}

function hasExactStringMembers(
  value: unknown,
  expected: readonly string[],
): boolean {
  return (
    Array.isArray(value) &&
    value.length === expected.length &&
    value.every((member, index) => member === expected[index])
  );
}

function assertFrozenPaperPacket(
  value: unknown,
): asserts value is RunPaperPacket {
  if (!isRecord(value)) {
    throw new TypeError("contract_error: run paper packet is not an object");
  }
  if (value.packet_schema_version !== "policyos.runtime.run_paper_packet.v1") {
    throw new TypeError(
      "contract_error: run paper packet version is unsupported",
    );
  }
  if (value.projection_rule_version !== "policyos.runtime.run_paper.v1") {
    throw new TypeError(
      "contract_error: run paper projection rule is unsupported",
    );
  }
  if (
    !Array.isArray(value.intended_audiences) ||
    value.intended_audiences.length !== 2 ||
    value.intended_audiences[0] !== "reviewer" ||
    value.intended_audiences[1] !== "expert"
  ) {
    throw new TypeError("contract_error: run paper audience tuple is invalid");
  }
  const packetRun = value.run;
  if (
    !isRecord(packetRun) ||
    typeof packetRun.run_id !== "string" ||
    !["terminal", "non_terminal", "not_established"].includes(
      String(packetRun.run_terminality),
    )
  ) {
    throw new TypeError("contract_error: run paper run identity is invalid");
  }
  const pins = value.replay_pins;
  if (
    !isRecord(pins) ||
    !hasExactKeys(pins, [
      "manifest_artifact_id",
      "manifest_schema_version",
      "paper_projection_hash",
      "paper_projection_rule_version",
    ]) ||
    Object.values(pins).some((pin) => typeof pin !== "string")
  ) {
    throw new TypeError("contract_error: run paper replay tuple is invalid");
  }
  const caseRecord = value.case_record;
  if (!isRecord(caseRecord)) {
    throw new TypeError("contract_error: run paper case union is invalid");
  }
  if (caseRecord.availability === "artifact_missing") {
    if (
      !hasExactKeys(caseRecord, [
        "availability",
        "capability_state",
        "closure_signal",
        "may_not_use_for",
        "owner_route",
        "reason_code",
      ]) ||
      caseRecord.capability_state !== "producer_missing" ||
      caseRecord.reason_code !== "case-record-not-run-bound" ||
      caseRecord.closure_signal !== "case-record-not-run-bound" ||
      caseRecord.owner_route !== "team-runtime" ||
      !hasExactStringMembers(
        caseRecord.may_not_use_for,
        RUN_PAPER_CASE_DENIED_USES,
      )
    ) {
      throw new TypeError(
        "contract_error: run paper unavailable case is invalid",
      );
    }
  } else if (caseRecord.availability === "available") {
    if (
      !hasExactKeys(caseRecord, [
        "abstentions",
        "admission_state",
        "availability",
        "blockers",
        "case_id",
        "design_record",
        "design_record_binding",
        "grounding_state",
        "limitations",
        "objections",
        "promotion_state",
      ])
    ) {
      throw new TypeError(
        "contract_error: run paper available case is invalid",
      );
    }
  } else {
    throw new TypeError(
      "contract_error: run paper case discriminator is invalid",
    );
  }
  if (!Array.isArray(value.artifact_links)) {
    throw new TypeError("contract_error: run paper artifact links are invalid");
  }
  for (const link of value.artifact_links) {
    if (
      !isRecord(link) ||
      !isRecord(link.artifact_ref) ||
      link.href !== `/api/v1/artifacts/${String(link.artifact_ref.artifact_id)}`
    ) {
      throw new TypeError("contract_error: run paper artifact link is unbound");
    }
  }
  if (
    typeof value.projection_hash !== "string" ||
    pins.paper_projection_hash !== value.projection_hash ||
    typeof value.stable_address !== "string" ||
    value.stable_address !== `/api/v1/runs/${packetRun.run_id}/paper`
  ) {
    throw new TypeError("contract_error: run paper replay identity is invalid");
  }
}

export function narrowCapturedRunPaper(
  expectedRunId: string,
  packet: unknown,
  rawPacketBytes: Uint8Array | null,
): CapturedRunPaper {
  assertFrozenPaperPacket(packet);
  if (packet.run.run_id !== expectedRunId) {
    throw new TypeError(
      "contract_error: run paper response does not bind the requested run",
    );
  }
  if (rawPacketBytes === null) {
    throw new TypeError(
      "contract_error: run paper response bytes were not captured",
    );
  }
  return Object.freeze({
    packet: Object.freeze(packet),
    rawPacketBytes: new Uint8Array(rawPacketBytes),
  });
}

export async function fetchRunPaper(
  runId: string,
  rawSearch: string,
  fetchImpl: PaperFetch = authAwareRuntimeFetch,
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
    "/api/v1/runs/{run_id}/paper",
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
      "Failed to load the replay-bound run paper packet",
    );
  }
  return narrowCapturedRunPaper(runId, data, rawPacketBytes);
}

const runtimeRunPaperClient: RunPaperClient = Object.freeze({
  getRunPaper: fetchRunPaper,
});

export function runPaperQueryOptions(
  client: RunPaperClient,
  runId: string,
  rawSearch: string,
) {
  return {
    queryKey: queryKeys.runPaper(runId, rawSearch),
    queryFn: () => client.getRunPaper(runId, rawSearch),
  };
}

export function runPaperQueryPolicy() {
  return { kind: "never_cache_authority" } as const;
}

export function useRunPaper(
  runId: string,
  rawSearch: string,
  client: RunPaperClient = runtimeRunPaperClient,
) {
  return useGovernedQuery(
    governedQueryOptions(
      runPaperQueryOptions(client, runId, rawSearch),
      runPaperQueryPolicy(),
    ),
  );
}
