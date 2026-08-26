import { describe, expect, it } from "vitest";

import type { CapturedCapabilitySearch } from "@/api/hooks/useCapabilitySearch";

import {
  capabilityDiscoveryTwin,
  decodeCapabilityDiscoveryDom,
} from "./capabilityDiscoveryTwin";

const now = "2026-08-26T00:00:00Z";
const digest = "sha256:" + "a".repeat(64);
const outputDigest = "sha256:" + "b".repeat(64);
const capabilityTime = {
  freshness: "current",
  observed_at: now,
  valid_from: now,
  valid_until: null,
} as const;

function candidate(ref: string, limitation: string[] = []) {
  return {
    authority_boundary: { candidate_only: true },
    candidate_ref: ref,
    evidence_refs: ["evidence:" + ref],
    limitation_refs: limitation,
    match_mode: "lexical" as const,
    may_not_use_for: ["authority"],
    score: limitation.length > 0 ? 0.2 : 0.9,
    source_layer: "owner-index",
  };
}

function result(ref: string) {
  return {
    authoritative_for: [],
    authority_purpose: "capability_discovery",
    authority_result: {
      authority_purpose: "capability_discovery",
      binding_ref: null,
      currentness_ref: null,
      producer_ref: "authority-owner",
      provenance_refs: ["authority-port"],
      reason_codes: ["not_established"],
      state: "bridge_missing" as const,
      time: capabilityTime,
    },
    capability_ref: ref,
    content_digest: digest,
    description: "Owner-projected row " + ref,
    discovery_result: {
      freshness_ref: "freshness:" + ref,
      producer_ref: "index-owner",
      provenance_refs: ["owner-index"],
      reason_codes: [],
      snapshot_ref: "snapshot:" + ref,
      state: "discoverable" as const,
      time: capabilityTime,
    },
    execution_result: {
      conformance_ref: "conformance:" + ref,
      operation_ref: "operation:" + ref,
      policy_ref: "policy:current",
      producer_ref: "operation-owner",
      provenance_refs: ["operation-registry"],
      reason_codes: [],
      state: "executable" as const,
      time: capabilityTime,
    },
    label: "Candidate " + ref,
    may_not_use_for: ["authority"],
    provenance_refs: ["owner-index", "operation-registry"],
    resource_kind: "legal_norm" as const,
    rule_version: "policyos.capability_discovery.v1",
    schema_version: "policyos.capability_discovery.v1" as const,
    time: capabilityTime,
  };
}

const selected = [
  candidate("capability:first"),
  candidate("capability:second"),
];
const rejected = [
  candidate("capability:rejected-a", ["below_cutoff"]),
  candidate("capability:rejected-b", ["query_mismatch"]),
];
const captured = {
  rawBytes: new Uint8Array(),
  response: {
    audience: "REVIEWER",
    authority_purpose: "capability_discovery",
    frontier: {
      actual_cutoff: 0.5,
      candidates: selected,
      completeness_status: "budget_cutoff",
      configured_store_path: null,
      corpus_kind: "canonical",
      corpus_path: "owner-index://legal-norm",
      corpus_ref: "lex-capability-index",
      corpus_snapshot_hash: digest,
      evaluated_count: 4,
      incompleteness: { budget_exhausted: true },
      incompleteness_reasons: ["budget_cutoff"],
      index_freshness: { legal_norm: { state: "current" } },
      index_version_refs: ["epoch:1", "epoch:2"],
      indexes_used: ["lex-capability-index"],
      no_hit_frontier: ["case:producer_missing"],
      query_expansion_traces: [{ source: "alias", value: "housing" }],
      query_plan: { match: "all_terms" },
      rejected_candidates: rejected,
      replay_command: "capability-search --request request",
      replay_expected_output_hash: outputDigest,
      replay_key: "replay:request",
      request_ref: "request",
      requested_count: 2,
      returned_count: 2,
      schema_version: "policyos.core.contracts.search.v1",
    },
    meta: {
      generated_at: now,
      request_id: "request",
      source_kinds: ["core_run"],
    },
    provenance_refs: ["owner-index"],
    request: {
      audience: "REVIEWER",
      resource_kinds: ["legal_norm"],
      search: {
        allowed_modes: ["lexical"],
        authority_purpose: "capability_discovery",
        budget: { top_k: 2 },
        construct_refs: ["housing"],
        intent: "capability_discovery",
        query_text: "housing",
        request_id: "request",
        required_layers: ["capability_discovery"],
        rule_version: "policyos.capability_discovery.v1",
        schema_version: "policyos.core.contracts.search.v1",
      },
    },
    request_digest: digest,
    results: [result("capability:first"), result("capability:second")],
    rule_version: "policyos.capability_discovery.v1",
    schema_version: "policyos.capability_discovery.v1",
    time: capabilityTime,
  },
  serverEpoch: '["epoch:1","epoch:2"]',
} as unknown as CapturedCapabilitySearch;

type PathPart = number | string;
type LeafType = "array" | "boolean" | "null" | "number" | "object" | "string";

function leafType(value: unknown): LeafType {
  if (value === null) return "null";
  if (Array.isArray(value)) return "array";
  if (typeof value === "object") return "object";
  return typeof value as LeafType;
}

function appendLeaves(
  root: HTMLElement,
  value: unknown,
  path: readonly PathPart[] = [],
) {
  const type = leafType(value);
  const entries: readonly (readonly [PathPart, unknown])[] = Array.isArray(
    value,
  )
    ? value.map((entry, index) => [index, entry] as const)
    : typeof value === "object" && value !== null
      ? Object.entries(value)
          .filter(([, entry]) => entry !== undefined)
          .sort(([left], [right]) => left.localeCompare(right))
      : [];
  const row = document.createElement("li");
  row.setAttribute("data-capability-packet-leaf", "");
  const pathValue = document.createElement("code");
  pathValue.setAttribute("data-capability-leaf-path", "");
  pathValue.textContent = JSON.stringify(path);
  const typeValue = document.createElement("span");
  typeValue.setAttribute("data-capability-leaf-type", "");
  typeValue.textContent = type;
  const leafValue = document.createElement("span");
  leafValue.setAttribute("data-capability-leaf-value", "");
  leafValue.textContent =
    type === "array" || type === "object"
      ? String(entries.length)
      : type === "null"
        ? "null"
        : String(value);
  row.append(pathValue, typeValue, leafValue);
  root.append(row);
  for (const [part, entry] of entries) {
    appendLeaves(root, entry, [...path, part]);
  }
}

function rootForTwin(value: CapturedCapabilitySearch = captured) {
  const root = document.createElement("div");
  appendLeaves(root, capabilityDiscoveryTwin(value));
  return root;
}

function packetLeaf(root: ParentNode, path: readonly PathPart[]) {
  const expected = JSON.stringify(path);
  const row = [
    ...root.querySelectorAll<HTMLElement>("[data-capability-packet-leaf]"),
  ].find(
    (candidateRow) =>
      candidateRow.querySelector("[data-capability-leaf-path]")?.textContent ===
      expected,
  );
  if (!row) {
    throw new TypeError("missing packet leaf " + expected);
  }
  return row;
}

describe("capability discovery DOM twin", () => {
  it("reconstructs every response leaf from visible DOM values", () => {
    expect(decodeCapabilityDiscoveryDom(rootForTwin())).toEqual(
      capabilityDiscoveryTwin(captured),
    );
  });

  it("detects omissions, reordering, selected/rejected, and posture mutations", () => {
    const expected = capabilityDiscoveryTwin(captured);

    const omitted = rootForTwin();
    packetLeaf(omitted, ["results", 0, "content_digest"]).remove();
    expect(() => decodeCapabilityDiscoveryDom(omitted)).toThrow(
      "container is incomplete",
    );

    const omittedEnvelope = rootForTwin();
    packetLeaf(omittedEnvelope, ["request_digest"]).remove();
    expect(() => decodeCapabilityDiscoveryDom(omittedEnvelope)).toThrow(
      "container is incomplete",
    );

    const reversed = {
      ...captured,
      response: {
        ...captured.response,
        results: [...captured.response.results].reverse(),
      },
    } as CapturedCapabilitySearch;
    expect(decodeCapabilityDiscoveryDom(rootForTwin(reversed))).not.toEqual(
      expected,
    );

    const selectedMutation = rootForTwin();
    packetLeaf(selectedMutation, [
      "frontier",
      "candidates",
      0,
      "candidate_ref",
    ]).querySelector<HTMLElement>("[data-capability-leaf-value]")!.textContent =
      "different-selected";
    expect(decodeCapabilityDiscoveryDom(selectedMutation)).not.toEqual(
      expected,
    );

    const rejectedMutation = rootForTwin();
    packetLeaf(rejectedMutation, [
      "frontier",
      "rejected_candidates",
      0,
      "limitation_refs",
      0,
    ]).querySelector<HTMLElement>("[data-capability-leaf-value]")!.textContent =
      "different-rejection";
    expect(decodeCapabilityDiscoveryDom(rejectedMutation)).not.toEqual(
      expected,
    );

    const postureMutation = rootForTwin();
    packetLeaf(postureMutation, [
      "results",
      0,
      "authority_result",
      "state",
    ]).querySelector<HTMLElement>("[data-capability-leaf-value]")!.textContent =
      "admitted_authority";
    expect(decodeCapabilityDiscoveryDom(postureMutation)).not.toEqual(expected);

    const audienceMutation = rootForTwin();
    packetLeaf(audienceMutation, ["audience"]).querySelector<HTMLElement>(
      "[data-capability-leaf-value]",
    )!.textContent = "MACHINE";
    expect(decodeCapabilityDiscoveryDom(audienceMutation)).not.toEqual(
      expected,
    );
  });

  it("fails when a value is removed while its generic leaf marker remains", () => {
    const markerOnly = rootForTwin();
    packetLeaf(markerOnly, ["results", 0, "authority_result", "state"])
      .querySelector("[data-capability-leaf-value]")
      ?.remove();

    expect(() => decodeCapabilityDiscoveryDom(markerOnly)).toThrow(
      "leaf value",
    );
  });
});
