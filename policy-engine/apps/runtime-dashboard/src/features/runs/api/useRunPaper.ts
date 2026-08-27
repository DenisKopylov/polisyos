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

const RUN_PAPER_AUTHORITY_NONRECEIPT_REQUIREMENTS = [
  {
    deniedUses: [
      "grounding_state",
      "grounded_case_projection",
      "available_run_paper_case",
    ],
    field: "grounding_nonreceipt",
    missingAuthority: "generation_cycle_grounding_authority",
    ownerRoute: "polisyos.runtime.quality.generation_cycle.GroundingStatus",
  },
  {
    deniedUses: [
      "admission_state",
      "admitted_case_projection",
      "available_run_paper_case",
    ],
    field: "admission_nonreceipt",
    missingAuthority: "hypothesis_ledger_admission_authority",
    ownerRoute:
      "polisyos.runtime.quality.hypothesis_ledger.HypothesisAdmissionState",
  },
  {
    deniedUses: [
      "promotion_state",
      "governed_case_projection",
      "available_run_paper_case",
    ],
    field: "promotion_nonreceipt",
    missingAuthority: "layer3_g4_promotion_authority",
    ownerRoute:
      "polisyos.runtime.quality.proving_ground.governed_promotion_gate.Layer3G4PromotionRecord.promotion_state",
  },
] as const;

type ObservedArtifactRef = Readonly<{
  artifact_id: string;
  kind: string;
  media_type: string;
}>;

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

function observedArtifactRef(
  value: unknown,
  expectedKind?: string,
): ObservedArtifactRef | null {
  if (
    !isRecord(value) ||
    !hasExactKeys(value, ["artifact_id", "kind", "media_type"]) ||
    typeof value.artifact_id !== "string" ||
    value.artifact_id.length === 0 ||
    typeof value.kind !== "string" ||
    value.kind.length === 0 ||
    typeof value.media_type !== "string" ||
    value.media_type.length === 0 ||
    (expectedKind !== undefined && value.kind !== expectedKind)
  ) {
    return null;
  }
  return value as ObservedArtifactRef;
}

function hasExactAuthorityNonreceipt(
  value: unknown,
  requirement: (typeof RUN_PAPER_AUTHORITY_NONRECEIPT_REQUIREMENTS)[number],
): boolean {
  return (
    isRecord(value) &&
    hasExactKeys(value, [
      "authority_state",
      "denied_uses",
      "kind",
      "missing_authority",
      "owner_route",
      "status",
    ]) &&
    value.authority_state === "absent/unallocated" &&
    hasExactStringMembers(value.denied_uses, requirement.deniedUses) &&
    value.kind === "run_paper_authority_nonreceipt" &&
    value.missing_authority === requirement.missingAuthority &&
    value.owner_route === requirement.ownerRoute &&
    value.status === "not_established"
  );
}

function requireBoundCaseArtifactRefs(
  caseRecord: Record<string, unknown>,
  packetRun: Record<string, unknown>,
): readonly ObservedArtifactRef[] {
  const binding = caseRecord.design_record_binding;
  const designRecord = caseRecord.design_record;
  if (
    !isRecord(binding) ||
    !hasExactKeys(binding, [
      "binding_id",
      "case_id",
      "cell_id",
      "design_record_content_digest",
      "design_record_record_id",
      "design_record_ref",
      "design_record_schema_name",
      "design_record_schema_version",
      "producer",
      "run_id",
      "schema_version",
      "search_ledger_content_digest",
      "search_ledger_id",
      "search_ledger_ref",
      "tenant_id",
    ]) ||
    !isRecord(designRecord) ||
    !isRecord(binding.producer)
  ) {
    throw new TypeError("contract_error: run paper case binding is invalid");
  }
  const requiredBindingStrings = [
    binding.binding_id,
    binding.case_id,
    binding.design_record_content_digest,
    binding.design_record_record_id,
    binding.design_record_schema_version,
    binding.run_id,
    binding.search_ledger_content_digest,
    binding.search_ledger_id,
    binding.tenant_id,
    binding.producer.component,
    binding.producer.version,
  ];
  const designRecordRef = observedArtifactRef(
    binding.design_record_ref,
    "policyos.layer2_s2.design_record_v0",
  );
  const searchLedgerRef = observedArtifactRef(
    binding.search_ledger_ref,
    "policyos.layer2_s2.search_ledger",
  );
  if (
    requiredBindingStrings.some(
      (member) => typeof member !== "string" || member.length === 0,
    ) ||
    (binding.cell_id !== null && typeof binding.cell_id !== "string") ||
    binding.design_record_schema_name !==
      "policyos.layer2_s2.design_record_v0" ||
    binding.schema_version !==
      "policyos.pdc.run_bound_design_record_binding.v1" ||
    designRecordRef === null ||
    designRecordRef.media_type !== "application/json" ||
    searchLedgerRef === null ||
    searchLedgerRef.media_type !== "application/json" ||
    binding.design_record_content_digest !== designRecordRef.artifact_id ||
    binding.search_ledger_content_digest !== searchLedgerRef.artifact_id ||
    caseRecord.case_id !== binding.case_id ||
    designRecord.record_id !== binding.design_record_record_id ||
    designRecord.schema_version !== binding.design_record_schema_version ||
    packetRun.run_id !== binding.run_id ||
    packetRun.tenant_id !== binding.tenant_id ||
    packetRun.cell_id !== binding.cell_id
  ) {
    throw new TypeError("contract_error: run paper case binding is invalid");
  }
  return [designRecordRef, searchLedgerRef];
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
  let boundCaseArtifactRefs: readonly ObservedArtifactRef[] = [];
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
    boundCaseArtifactRefs = requireBoundCaseArtifactRefs(caseRecord, packetRun);
  } else if (
    caseRecord.availability === "record_available_authority_abstaining"
  ) {
    if (
      !hasExactKeys(caseRecord, [
        "admission_nonreceipt",
        "authority_projection",
        "availability",
        "case_id",
        "design_record",
        "design_record_binding",
        "grounding_nonreceipt",
        "promotion_nonreceipt",
      ]) ||
      caseRecord.authority_projection !== "abstained"
    ) {
      throw new TypeError(
        "contract_error: run paper authority-abstaining case is invalid",
      );
    }
    boundCaseArtifactRefs = requireBoundCaseArtifactRefs(caseRecord, packetRun);
    if (
      RUN_PAPER_AUTHORITY_NONRECEIPT_REQUIREMENTS.some(
        (requirement) =>
          !hasExactAuthorityNonreceipt(
            caseRecord[requirement.field],
            requirement,
          ),
      )
    ) {
      throw new TypeError(
        "contract_error: run paper authority nonreceipt is invalid",
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
  const admittedArtifactRefs: ObservedArtifactRef[] = [];
  for (const link of value.artifact_links) {
    const artifactRef = isRecord(link)
      ? observedArtifactRef(link.artifact_ref)
      : null;
    if (
      !isRecord(link) ||
      !hasExactKeys(link, ["artifact_ref", "href", "relation"]) ||
      artifactRef === null ||
      link.href !== `/api/v1/artifacts/${artifactRef.artifact_id}` ||
      link.relation !== "run_output"
    ) {
      throw new TypeError("contract_error: run paper artifact link is unbound");
    }
    admittedArtifactRefs.push(artifactRef);
  }
  for (const requiredRef of boundCaseArtifactRefs) {
    const matches = admittedArtifactRefs.filter(
      (candidate) =>
        candidate.artifact_id === requiredRef.artifact_id &&
        candidate.kind === requiredRef.kind &&
        candidate.media_type === requiredRef.media_type,
    );
    if (matches.length !== 1) {
      throw new TypeError(
        "contract_error: run paper bound artifact requirements are invalid",
      );
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
