import assert from "node:assert/strict";
import test from "node:test";

import { RuntimeApiClient } from "../../packages/runtime-api-client/canonicalRuntimeApiClient.js";
import { verifyGovernedProjectionCatalog } from "./governedProjectionProof.js";

test("reference-shell proof consumes the generated catalog operation", async () => {
  const calls = [];
  const client = new RuntimeApiClient({
    baseUrl: "https://runtime.test/",
    fetchImpl: async (url, init) => {
      calls.push({ url, init });
      return new Response(
        JSON.stringify({
          projections: [
            {
              projection_id: "depth-n-cycle-board",
              expected_source_path:
                "architecture/policy_design_case/layer3_gy_depth_n_universality_contract.json",
              source_policy: "required",
              intended_audience: "MACHINE",
              authoritative_for: ["cycle_board_domain_runs"],
              may_not_use_for: ["publication_authority"],
              expected_source_schema_version:
                "policyos.policy_design_case.gy_n10.depth_n_universality.v1",
              expected_source_rule_version:
                "policyos.layer3.gy.n10.depth_n_universality.v1",
              owner_validator_id:
                "tools.quality.validation.check_layer3_gy_depth_n_universality_contract",
              owner_validator_version:
                "policyos.policy_design_case.gy_n10.depth_n_universality.v1",
              stable_address:
                "/api/v1/exports/governed-projections/depth-n-cycle-board",
            },
          ],
          schema_version: "policyos.runtime.governed_projection_catalog.v1",
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      );
    },
  });

  const result = await verifyGovernedProjectionCatalog(client);

  assert.deepEqual(result, { status: "available", projectionCount: 1 });
  assert.equal(calls.length, 1);
  assert.equal(
    calls[0].url,
    "https://runtime.test/api/v1/exports/governed-projections",
  );
  assert.equal(calls[0].init.method, "GET");
});

test("reference-shell proof reports generated-client transport failures", async () => {
  const client = new RuntimeApiClient({
    baseUrl: "https://runtime.test",
    fetchImpl: async () =>
      new Response("temporarily unavailable", {
        status: 503,
        statusText: "Service Unavailable",
      }),
  });

  const result = await verifyGovernedProjectionCatalog(client);

  assert.equal(result.status, "unavailable");
  assert.match(result.reason, /503 Service Unavailable/);
});
