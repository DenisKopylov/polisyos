import assert from "node:assert/strict";
import test from "node:test";

import { RuntimeApiClient } from "./canonicalRuntimeApiClient.js";

function createClient(calls, payload = { ok: true }) {
  return new RuntimeApiClient({
    baseUrl: "https://runtime.test/",
    fetchImpl: async (url, init) => {
      calls.push({ url, init });
      return new Response(JSON.stringify(payload), {
        status: 200,
        headers: {
          "Content-Type": "application/json",
        },
      });
    },
  });
}

test("normative evidence submission forwards the source head and signed refs", async () => {
  const calls = [];
  const payload = { status: "admitted", head_ref: "sha256:admitted" };
  const client = new RuntimeApiClient({
    baseUrl: "https://runtime.test/",
    fetchImpl: async (url, init) => {
      calls.push({ url, init });
      return Response.json(payload);
    },
  });
  const body = {
    job_id: "job-source-bound",
    expected_prior_head_ref: null,
    evidence: {
      by_node: {
        "leaf/novel": {
          authorization_ref: "sha256:authorization",
          frontier_ref: "sha256:frontier",
          scope_ref: "sha256:scope",
        },
      },
    },
  };
  const response = await client.submitRunNormativeEvidence({
    run_id: "run/with space",
    body,
  });
  assert.deepEqual(response, payload);
  assert.equal(calls.length, 1);
  assert.equal(
    calls[0].url,
    "https://runtime.test/api/v1/control/runs/run%2Fwith%20space/normative-evidence",
  );
  assert.equal(calls[0].init.method, "POST");
  assert.deepEqual(JSON.parse(calls[0].init.body), body);
});

test("batch POST methods forward request bodies to fetch", async () => {
  const calls = [];
  const client = createClient(calls);

  await client.getArtifactBatch({ body: { artifact_ids: ["artifact-1"] } });
  await client.getRunsBatch({ body: { run_ids: ["run-1"] } });

  assert.equal(calls.length, 2);
  assert.equal(calls[0].url, "https://runtime.test/api/v1/artifacts/batch");
  assert.equal(calls[0].init.method, "POST");
  assert.equal(
    calls[0].init.body,
    JSON.stringify({ artifact_ids: ["artifact-1"] }),
  );
  assert.equal(calls[1].url, "https://runtime.test/api/v1/runs/batch");
  assert.equal(calls[1].init.method, "POST");
  assert.equal(calls[1].init.body, JSON.stringify({ run_ids: ["run-1"] }));
});

test("cycle board static operation forwards both complete replay identities", async () => {
  const calls = [];
  const client = createClient(calls);

  await client.getDepthNCycleBoardProjection({
    replay_target: "raw_v1",
    artifact_content_hash: "sha256:artifact",
    projection_hash: "sha256:raw-projection",
    source_dependency_hash: "sha256:raw-dependencies",
    source_as_of: "2026-07-29T10:00:00Z",
  });
  await client.getDepthNCycleBoardProjection({
    replay_target: "composed_v2",
    projection_rule_version: "policyos.runtime.depth_n_cycle_board.v2",
    composition_manifest_hash: "sha256:manifest",
    projection_hash: "sha256:v2-projection",
    source_dependency_hash: "sha256:v2-dependencies",
  });

  assert.equal(calls.length, 2);
  const rawUrl = new URL(calls[0].url);
  const composedUrl = new URL(calls[1].url);
  assert.equal(rawUrl.pathname, composedUrl.pathname);
  assert.equal(
    rawUrl.pathname,
    "/api/v1/exports/governed-projections/depth-n-cycle-board",
  );
  assert.deepEqual(Object.fromEntries(rawUrl.searchParams), {
    artifact_content_hash: "sha256:artifact",
    projection_hash: "sha256:raw-projection",
    replay_target: "raw_v1",
    source_as_of: "2026-07-29T10:00:00Z",
    source_dependency_hash: "sha256:raw-dependencies",
  });
  assert.deepEqual(Object.fromEntries(composedUrl.searchParams), {
    composition_manifest_hash: "sha256:manifest",
    projection_hash: "sha256:v2-projection",
    projection_rule_version: "policyos.runtime.depth_n_cycle_board.v2",
    replay_target: "composed_v2",
    source_dependency_hash: "sha256:v2-dependencies",
  });
  assert.equal(calls[0].init.method, "GET");
  assert.equal(calls[1].init.method, "GET");
});

test("mobility POST methods forward request bodies to fetch", async () => {
  const calls = [];
  const client = createClient(calls);

  await client.computeMobilityBounds({ body: { artifact_id: "artifact-1" } });
  await client.estimateMobility({
    body: {
      feature: "income",
      group_by: ["region"],
      outcome: "upward",
      run_id: "run-1",
    },
  });

  assert.equal(calls.length, 2);
  assert.equal(calls[0].url, "https://runtime.test/api/v1/mobility/bounds");
  assert.equal(calls[0].init.method, "POST");
  assert.equal(
    calls[0].init.body,
    JSON.stringify({ artifact_id: "artifact-1" }),
  );
  assert.equal(calls[1].url, "https://runtime.test/api/v1/mobility/estimate");
  assert.equal(calls[1].init.method, "POST");
  assert.equal(
    calls[1].init.body,
    JSON.stringify({
      feature: "income",
      group_by: ["region"],
      outcome: "upward",
      run_id: "run-1",
    }),
  );
});

test("human decision methods bind the exact exposure header and POST body", async () => {
  const calls = [];
  const evidenceBytes = Uint8Array.from([0, 255, 17, 34]);
  const client = new RuntimeApiClient({
    baseUrl: "https://runtime.test/",
    fetchImpl: async (url, init) => {
      calls.push({ url, init });
      if (init.method === "GET") {
        return new Response(evidenceBytes, {
          status: 200,
          headers: { "Content-Type": "application/pdf" },
        });
      }
      return new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    },
  });
  const exposure = "sha256:verified-exposure-session";

  const delivered = await client.getRunHumanDecisionEvidenceContent({
    run_id: "run-1",
    artifact_id: "sha256:evidence",
    "X-PolicyOS-Human-Decision-Exposure": exposure,
  });
  await client.createRunHumanDecision({
    run_id: "run-1",
    "X-PolicyOS-Human-Decision-Exposure": exposure,
    body: { decision_action: "approve" },
  });

  assert.equal(calls.length, 2);
  assert.deepEqual(new Uint8Array(delivered), evidenceBytes);
  assert.equal(
    new Headers(calls[0].init.headers).get(
      "X-PolicyOS-Human-Decision-Exposure",
    ),
    exposure,
  );
  assert.equal(calls[1].init.method, "POST");
  assert.equal(
    new Headers(calls[1].init.headers).get(
      "X-PolicyOS-Human-Decision-Exposure",
    ),
    exposure,
  );
  assert.equal(
    calls[1].init.body,
    JSON.stringify({ decision_action: "approve" }),
  );
});

// These are transport fixtures only. The bearer and CAS-like values do not
// establish authentication, permission, source ownership, or currentness.
const sourceTransportDigest = `sha256:${"a".repeat(64)}`;
const sourceTransportRef = {
  artifact_id: sourceTransportDigest,
  kind: "ir.data_view_request",
  media_type: "application/json",
};
const sourceWriteCases = [
  {
    method: "cancelControlJob",
    path: "/api/v1/control/jobs/job%2Fwith%20space/cancel",
    params: {
      job_id: "job/with space",
      body: { operation_id: "cancel-event", expected_attempt: 2 },
    },
  },
  {
    method: "registerSqlSource",
    path: "/api/v1/control/registered-sql/registrations",
    params: { body: { slot_id: "slot-1", event_id: "registration-1" } },
  },
  {
    method: "admitRegisteredSqlMaterialization",
    path: "/api/v1/control/registered-sql/materializations",
    params: {
      body: {
        slot_id: "slot-1",
        event_id: "admission-1",
        occurrence_id: "occurrence-1",
        request_ref: sourceTransportRef,
        expected_predecessor: sourceTransportDigest,
      },
    },
  },
  {
    method: "withdrawRegisteredSqlMaterialization",
    path: "/api/v1/control/registered-sql/withdrawals",
    params: {
      body: {
        slot_id: "slot-1",
        event_id: "withdrawal-1",
        expected_predecessor: sourceTransportDigest,
        target: {
          tenant_id: "tenant-1",
          cell_id: "cell-1",
          source_incarnation_id: "source-1",
          admission_scope_digest: sourceTransportDigest,
          occurrence_id: "occurrence-1",
          revision_digest: sourceTransportDigest,
          admission_epoch: "epoch-1",
          admission_event_ref: sourceTransportDigest,
          snapshot_ref: sourceTransportRef,
          use_contract_ref: sourceTransportRef,
        },
      },
    },
  },
];

for (const operation of sourceWriteCases) {
  test(`${operation.method} forwards a scoped POST unchanged`, async () => {
    const calls = [];
    const payload = { transport_test_payload: operation.method };
    const client = new RuntimeApiClient({
      baseUrl: "https://runtime.test/",
      headers: {
        Authorization: "Bearer transport-test-token",
        "X-Tenant-ID": "tenant-1",
      },
      fetchImpl: async (url, init) => {
        calls.push({ url, init });
        // The staged OpenAPI declares a JSON 200 response for each operation.
        return Response.json(payload, { status: 200 });
      },
    });

    assert.deepEqual(await client[operation.method](operation.params), payload);
    assert.equal(calls.length, 1);
    assert.equal(calls[0].url, `https://runtime.test${operation.path}`);
    assert.equal(calls[0].init.method, "POST");
    assert.deepEqual(JSON.parse(calls[0].init.body), operation.params.body);
    const headers = new Headers(calls[0].init.headers);
    assert.equal(headers.get("content-type"), "application/json");
    assert.equal(headers.get("authorization"), "Bearer transport-test-token");
    assert.equal(headers.get("x-tenant-id"), "tenant-1");
    assert.equal(calls[0].url.includes("transport-test-token"), false);
    assert.equal(calls[0].init.body.includes("transport-test-token"), false);
  });

  test(`${operation.method} rejects a denied response`, async () => {
    let calls = 0;
    const client = new RuntimeApiClient({
      baseUrl: "https://runtime.test",
      fetchImpl: async () => {
        calls += 1;
        return new Response('{"code":"forbidden"}', {
          status: 403,
          statusText: "Forbidden",
          headers: { "Content-Type": "application/problem+json" },
        });
      },
    });

    await assert.rejects(() => client[operation.method](operation.params), {
      name: "Error",
      message: 'Runtime API request failed: 403 Forbidden {"code":"forbidden"}',
    });
    assert.equal(calls, 1);
  });
}

test("method-metric comparison GET preserves absence and candidate limitations", async () => {
  const calls = [];
  // These are transport fixtures; the values do not assert a verified ranking.
  const payloads = [
    { meta: { request_id: "transport-0" }, run_id: "run/with space" },
    {
      meta: { request_id: "transport-1" },
      run_id: "run/with space",
      candidate_comparison: null,
    },
    {
      meta: { request_id: "transport-2" },
      run_id: "run/with space",
      candidate_comparison: {
        status: "verification_missing",
        authority_status: "candidate_only",
        revalidation_required: true,
        limitations: ["current_candidate_comparison_owner_unavailable"],
      },
    },
    {
      meta: { request_id: "transport-3" },
      run_id: "run/with space",
      candidate_comparison: {
        status: "invalid",
        authority_status: "candidate_only",
        revalidation_required: true,
        limitations: ["completed_candidate_identity_duplicated"],
      },
    },
  ];
  const client = new RuntimeApiClient({
    baseUrl: "https://runtime.test/",
    headers: {
      Authorization: "Bearer transport-test-token",
      "X-Tenant-ID": "tenant-1",
    },
    fetchImpl: async (url, init) => {
      calls.push({ url, init });
      return Response.json(payloads[calls.length - 1], { status: 200 });
    },
  });

  for (const payload of payloads) {
    const response = await client.getRunMethodMetricComparison({
      run_id: "run/with space",
    });
    assert.deepEqual(response, payload);
  }
  assert.equal(calls.length, payloads.length);
  for (const { url, init } of calls) {
    assert.equal(
      url,
      "https://runtime.test/api/v1/runs/run%2Fwith%20space/method-metric-comparison",
    );
    assert.equal(init.method, "GET");
    assert.equal(init.body, undefined);
    const headers = new Headers(init.headers);
    assert.equal(headers.get("authorization"), "Bearer transport-test-token");
    assert.equal(headers.get("x-tenant-id"), "tenant-1");
  }
});

test("method-metric comparison GET propagates a denied response", async () => {
  let calls = 0;
  const client = new RuntimeApiClient({
    baseUrl: "https://runtime.test",
    fetchImpl: async () => {
      calls += 1;
      return new Response('{"code":"forbidden"}', {
        status: 403,
        statusText: "Forbidden",
        headers: { "Content-Type": "application/problem+json" },
      });
    },
  });

  await assert.rejects(
    () => client.getRunMethodMetricComparison({ run_id: "run-1" }),
    {
      name: "Error",
      message: 'Runtime API request failed: 403 Forbidden {"code":"forbidden"}',
    },
  );
  assert.equal(calls, 1);
});
