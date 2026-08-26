import { expect, type Locator, type Page } from "@playwright/test";

import type { components } from "../../src/api/types";

type CapabilityDiscoveryRequest =
  components["schemas"]["CapabilityDiscoveryRequest"];
type CapabilityDiscoveryResponse =
  components["schemas"]["CapabilityDiscoveryResponse"];
type SearchCandidate = components["schemas"]["SearchCandidate"];

export type CapabilityDiscoveryFixture = "executable" | "incomplete-no-hit";

const FIXED_TIME = "2026-01-01T00:00:00.000Z";
const SHA256_A = `sha256:${"a".repeat(64)}`;
const SHA256_B = `sha256:${"b".repeat(64)}`;
const GENERATED_CAPABILITY_REF = "legal-norm:ds10-generated-owner-row";

function time(freshness: "current" | "stale" | "unknown" = "current") {
  return {
    freshness,
    observed_at: FIXED_TIME,
    valid_from: FIXED_TIME,
    valid_until: null,
  } as const;
}

function candidate(
  candidateRef: string,
  score: number,
  limitationRefs: string[] = [],
): SearchCandidate {
  return {
    authority_boundary: {
      candidate_only: true,
      admission_must_be_established_independently: true,
    },
    candidate_ref: candidateRef,
    evidence_refs: [`owner-index:${candidateRef}`],
    limitation_refs: limitationRefs,
    match_mode: "lexical",
    may_not_use_for: ["admission", "authority", "permission"],
    score,
    source_layer: "owner-index",
  };
}

function buildResponse(
  request: CapabilityDiscoveryRequest,
  fixture: CapabilityDiscoveryFixture,
): CapabilityDiscoveryResponse {
  const selected = candidate(GENERATED_CAPABILITY_REF, 0.97);
  const rejected = candidate("legal-norm:rejected-near-match", 0.41, [
    "below_cutoff",
  ]);
  const executable = fixture === "executable";
  const incompletenessReasons = executable
    ? []
    : [
        "recall_unmeasured",
        "budget_cutoff",
        "legal_norm:index_stale",
        "case:producer_missing",
      ];

  return {
    audience: request.audience,
    authority_purpose: request.search.authority_purpose,
    frontier: {
      actual_cutoff: executable ? 0.75 : 0.64,
      candidates: executable ? [selected] : [],
      completeness_status: executable ? "complete" : "recall_unmeasured",
      configured_store_path: null,
      corpus_kind: "canonical",
      corpus_path: "owner-index://legal-norm",
      corpus_ref: "lex-capability-index",
      corpus_snapshot_hash: SHA256_A,
      evaluated_count: executable ? 2 : 5,
      incompleteness: executable
        ? {}
        : {
            budget_exhausted: true,
            missing_producers: ["case"],
            stale_indexes: ["legal_norm"],
          },
      incompleteness_reasons: incompletenessReasons,
      index_freshness: {
        legal_norm: executable ? "current" : "stale",
        case: executable ? "current" : "producer_missing",
      },
      index_version_refs: ["lex-capability-index:epoch:2026-01-01"],
      indexes_used: ["lex-capability-index"],
      no_hit_frontier: executable
        ? []
        : ["legal_norm:below_cutoff", "case:producer_missing"],
      query_expansion_traces: [],
      query_plan: {
        requested_resource_kinds: request.resource_kinds,
        strategy: "federated-owner-index",
      },
      rejected_candidates: [rejected],
      replay_command: `capability-search --request ${request.search.request_id}`,
      replay_expected_output_hash: SHA256_B,
      replay_key: `ds10:${request.search.request_id}`,
      request_ref: request.search.request_id,
      requested_count: request.resource_kinds.length,
      returned_count: executable ? 1 : 0,
      schema_version: "policyos.core.contracts.search.v1",
    },
    meta: {
      generated_at: FIXED_TIME,
      request_id: request.search.request_id,
      source_kinds: ["core_run"],
    },
    provenance_refs: ["owner-index:lex-capability-index", "route:fastapi"],
    request,
    request_digest: SHA256_B,
    results: executable
      ? [
          {
            authoritative_for: [],
            authority_purpose: request.search.authority_purpose,
            authority_result: {
              authority_purpose: request.search.authority_purpose,
              binding_ref: null,
              currentness_ref: null,
              producer_ref: "runtime.quality.capability_authority",
              provenance_refs: ["authority-port:typed-binding-missing"],
              reason_codes: [
                "not_established",
                "typed_capability_binding_missing",
              ],
              state: "bridge_missing",
              time: time("unknown"),
            },
            capability_ref: GENERATED_CAPABILITY_REF,
            content_digest: SHA256_A,
            description:
              "A generated legal-norm owner-index row, shown only as a candidate.",
            discovery_result: {
              freshness_ref: "lex-capability-index:epoch:2026-01-01",
              producer_ref: "runtime.quality.lex_capability_discovery",
              provenance_refs: ["owner-index:lex-capability-index"],
              reason_codes: [],
              snapshot_ref: SHA256_A,
              state: "discoverable",
              time: time(),
            },
            execution_result: {
              conformance_ref: "conformance:legal-norm-resolution",
              operation_ref: "operation:resolve-legal-norm",
              policy_ref: "policy:capability-execution:v1",
              producer_ref: "runtime.control.operation_registry",
              provenance_refs: ["operation-registry:current"],
              reason_codes: [],
              state: "executable",
              time: time(),
            },
            label: "Generated legal-norm candidate",
            may_not_use_for: ["admission", "authority", "permission"],
            provenance_refs: [
              "owner-index:lex-capability-index",
              "operation-registry:current",
            ],
            resource_kind: "legal_norm",
            rule_version: "policyos.capability_discovery.v1",
            schema_version: "policyos.capability_discovery.v1",
            time: time(),
          },
        ]
      : [],
    rule_version: "policyos.capability_discovery.v1",
    schema_version: "policyos.capability_discovery.v1",
    time: time(executable ? "current" : "stale"),
  };
}

export async function installCapabilityDiscoveryFixture(
  page: Page,
  fixture: CapabilityDiscoveryFixture,
) {
  await page.route("**/api/v1/control/capabilities/search", async (route) => {
    if (route.request().method() !== "POST") {
      await route.fallback();
      return;
    }
    const request = route
      .request()
      .postDataJSON() as CapabilityDiscoveryRequest;
    const response = buildResponse(request, fixture);
    await route.fulfill({
      body: JSON.stringify(response),
      contentType: "application/json",
      status: 200,
    });
  });
}

export async function openCapabilityDiscovery(
  page: Page,
  fixture: CapabilityDiscoveryFixture,
): Promise<Locator> {
  await installCapabilityDiscoveryFixture(page, fixture);
  const responsePromise = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return (
      response.request().method() === "POST" &&
      url.pathname === "/api/v1/control/capabilities/search" &&
      response.status() === 200
    );
  });
  await page.goto("/evidence");
  const panel = page.getByTestId("capability-discovery-panel");
  await expect(panel).toBeVisible();
  await responsePromise;
  await expect(panel.getByRole("status")).toContainText("Candidate search");
  return panel;
}
