import { describe, expect, it } from "vitest";

import type { CapturedCapabilitySearch } from "@/api/hooks/useCapabilitySearch";

import {
  capabilityDiscoveryTwin,
  decodeCapabilityDiscoveryDom,
} from "./capabilityDiscoveryTwin";

const captured = {
  response: {
    audience: "REVIEWER",
    authority_purpose: "capability_discovery",
    frontier: {
      actual_cutoff: 2,
      candidates: [
        {
          candidate_ref: "selected",
          evidence_refs: ["e"],
          limitation_refs: [],
          match_mode: "lexical",
          may_not_use_for: [],
          score: 1,
          source_layer: "owner",
        },
      ],
      completeness_status: "complete",
      corpus_kind: "canonical",
      corpus_path: "owner",
      corpus_ref: "owner",
      corpus_snapshot_hash: "hash",
      evaluated_count: 2,
      incompleteness_reasons: [],
      index_version_refs: ["epoch"],
      indexes_used: ["owner"],
      no_hit_frontier: ["none"],
      query_expansion_traces: [],
      rejected_candidates: [
        {
          candidate_ref: "rejected",
          evidence_refs: [],
          limitation_refs: ["limitation"],
          match_mode: "lexical",
          may_not_use_for: [],
          score: 0,
          source_layer: "owner",
        },
      ],
      replay_command: "replay",
      replay_expected_output_hash: "hash",
      replay_key: "key",
      request_ref: "request",
      requested_count: 2,
      returned_count: 1,
      schema_version: "policyos.core.contracts.search.v1",
    },
    meta: {
      generated_at: "now",
      request_id: "request",
      source_kinds: ["core_run"],
    },
    provenance_refs: ["owner"],
    request: {
      audience: "REVIEWER",
      resource_kinds: ["agent"],
      search: {
        allowed_modes: ["lexical"],
        authority_purpose: "capability_discovery",
        construct_refs: ["c"],
        intent: "capability_discovery",
        query_text: "query",
        request_id: "request",
        required_layers: ["capability_discovery"],
        rule_version: "v1",
        schema_version: "policyos.core.contracts.search.v1",
      },
    },
    request_digest: "digest",
    results: [
      {
        authoritative_for: [],
        authority_purpose: "capability_discovery",
        capability_ref: "first",
        content_digest: "digest",
        description: "first",
        label: "first",
        may_not_use_for: [],
        provenance_refs: ["owner"],
        resource_kind: "agent",
        rule_version: "v1",
        schema_version: "policyos.capability_discovery.v1",
        time: {
          freshness: "current",
          observed_at: "now",
          valid_from: "now",
          valid_until: null,
        },
        discovery_result: {
          producer_ref: "owner",
          provenance_refs: [],
          reason_codes: ["reason"],
          state: "discoverable",
          time: {
            freshness: "current",
            observed_at: "now",
            valid_from: "now",
            valid_until: null,
          },
        },
        execution_result: {
          producer_ref: "owner",
          provenance_refs: [],
          reason_codes: [],
          state: "executable",
          time: {
            freshness: "current",
            observed_at: "now",
            valid_from: "now",
            valid_until: null,
          },
        },
        authority_result: {
          authority_purpose: "capability_discovery",
          producer_ref: "owner",
          provenance_refs: [],
          reason_codes: ["not_established"],
          state: "bridge_missing",
          time: {
            freshness: "current",
            observed_at: "now",
            valid_from: "now",
            valid_until: null,
          },
        },
      },
    ],
    rule_version: "v1",
    schema_version: "policyos.capability_discovery.v1",
    time: {
      freshness: "current",
      observed_at: "now",
      valid_from: "now",
      valid_until: null,
    },
  },
} as unknown as CapturedCapabilitySearch;

function rootForTwin() {
  const twin = capabilityDiscoveryTwin(captured);
  const root = document.createElement("div");
  root.innerHTML = `<div data-capability-envelope='${JSON.stringify(twin.envelope)}'><div data-capability-frontier='${JSON.stringify(twin.frontier.envelope)}'></div></div>`;
  const parent = root.querySelector(
    "[data-capability-envelope]",
  ) as HTMLElement;
  for (const result of twin.results) {
    const row = document.createElement("div");
    row.dataset.capabilityResult = JSON.stringify(result);
    row.dataset.capabilityDiscoveryPosture = JSON.stringify(
      result.discovery_result,
    );
    row.dataset.capabilityExecutionPosture = JSON.stringify(
      result.execution_result,
    );
    row.dataset.capabilityAuthorityPosture = JSON.stringify(
      result.authority_result,
    );
    parent.append(row);
  }
  for (const candidate of twin.frontier.candidates) {
    const row = document.createElement("div");
    row.dataset.capabilityCandidate = JSON.stringify(candidate);
    parent.append(row);
  }
  for (const candidate of twin.frontier.rejectedCandidates) {
    const row = document.createElement("div");
    row.dataset.capabilityRejected = JSON.stringify(candidate);
    parent.append(row);
  }
  return root;
}

describe("capability discovery DOM twin", () => {
  it("detects omitted, reordered, selected/rejected, and posture mutations", () => {
    const expected = capabilityDiscoveryTwin(captured);
    expect(decodeCapabilityDiscoveryDom(rootForTwin())).toEqual(expected);

    const omitted = rootForTwin();
    omitted.querySelector("[data-capability-result]")?.remove();
    expect(decodeCapabilityDiscoveryDom(omitted)).not.toEqual(expected);

    const reordered = rootForTwin();
    const result = reordered.querySelector(
      "[data-capability-result]",
    ) as HTMLElement;
    result.dataset.capabilityResult = JSON.stringify({
      ...expected.results[0],
      capability_ref: "reordered",
    });
    expect(decodeCapabilityDiscoveryDom(reordered)).not.toEqual(expected);

    const frontierMutation = rootForTwin();
    const selected = frontierMutation.querySelector(
      "[data-capability-candidate]",
    ) as HTMLElement;
    selected.dataset.capabilityCandidate = JSON.stringify({
      ...expected.frontier.candidates[0],
      score: 99,
    });
    expect(decodeCapabilityDiscoveryDom(frontierMutation)).not.toEqual(
      expected,
    );

    const postureMutation = rootForTwin();
    const row = postureMutation.querySelector(
      "[data-capability-result]",
    ) as HTMLElement;
    row.dataset.capabilityAuthorityPosture = JSON.stringify({
      ...expected.results[0]?.authority_result,
      state: "admitted_authority",
    });
    expect(() => decodeCapabilityDiscoveryDom(postureMutation)).toThrow(
      "authority posture diverges",
    );
  });
});
