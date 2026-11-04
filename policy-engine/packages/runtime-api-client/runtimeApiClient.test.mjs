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

test("candidate acquisition experiment GET preserves unknown authority and replay pins", async () => {
  // Transport fixture only; these refs do not establish a verified source permit.
  const payload = {
    monetary_cost: "not_established",
    information_value: "not_established",
    action_authority: "not_established",
    publication_authority: false,
    replay_pins: {
      candidate_digest: "sha256:candidate",
      compiled_ref: { artifact_id: "sha256:compiled" },
      compiler_report_ref: { artifact_id: "sha256:compiler" },
      configured_port_source_ref: { artifact_id: "sha256:port-source" },
      planner_report_ref: { artifact_id: "sha256:planner" },
      policy_ref: { artifact_id: "sha256:policy" },
      request_content_hash: "sha256:request",
    },
  };
  const calls = [];
  const client = createClient(calls, payload);

  const response = await client.getRunCandidateAcquisitionExperiment({
    run_id: "run/with space",
  });

  assert.deepEqual(response, payload);
  assert.equal(calls.length, 1);
  assert.equal(
    calls[0].url,
    "https://runtime.test/api/v1/runs/run%2Fwith%20space/candidate-acquisition-experiment",
  );
  assert.equal(calls[0].init.method, "GET");
  assert.equal(calls[0].init.body, undefined);
  assert.deepEqual(response.replay_pins, payload.replay_pins);

  let deniedCalls = 0;
  const deniedClient = new RuntimeApiClient({
    baseUrl: "https://runtime.test",
    fetchImpl: async () => {
      deniedCalls += 1;
      return new Response('{"code":"forbidden"}', {
        status: 403,
        statusText: "Forbidden",
        headers: { "Content-Type": "application/problem+json" },
      });
    },
  });
  await assert.rejects(
    () =>
      deniedClient.getRunCandidateAcquisitionExperiment({
        run_id: "run/with space",
      }),
    {
      name: "Error",
      message: 'Runtime API request failed: 403 Forbidden {"code":"forbidden"}',
    },
  );
  assert.equal(deniedCalls, 1);
});

test("candidate acquisition experiment GET passes through current action projections", async () => {
  // Transport fixtures only; refs and statuses do not establish authority or a source permit.
  const runId = "run/with space";
  const routeId = `sha256:${"a".repeat(64)}`;
  const basePayload = {
    schema_version: "CandidateExperimentRouteProjection@1.0",
    tenant_id: "tenant-transport",
    cell_id: "cell-transport",
    run_id: runId,
    route_id: routeId,
    replay_pins: {
      source_job_id: "source-job-transport",
      source_payload_ref: `sha256:${"b".repeat(64)}`,
      request_content_hash: `sha256:${"c".repeat(64)}`,
      compiled_ref: {
        artifact_id: `sha256:${"d".repeat(64)}`,
        kind: "runtime.compiled_recursive_generation_cycle",
        media_type: "application/json",
        manifest_profile_sha256: `sha256:${"e".repeat(64)}`,
      },
      planner_report_ref: {
        artifact_id: `sha256:${"f".repeat(64)}`,
        kind: "runtime.acquisition_planner_report",
        media_type: "application/json",
        manifest_profile_sha256: `sha256:${"1".repeat(64)}`,
      },
      compiler_report_ref: {
        artifact_id: `sha256:${"2".repeat(64)}`,
        kind: "runtime.data_requirement_compilation_report",
        media_type: "application/json",
        manifest_profile_sha256: `sha256:${"3".repeat(64)}`,
      },
      configured_port_source_ref: {
        artifact_id: `sha256:${"4".repeat(64)}`,
        kind: "runtime.quality.n7_configured_candidate_port_source",
        media_type: "application/json",
        manifest_profile_sha256: `sha256:${"5".repeat(64)}`,
      },
      policy_ref: {
        artifact_id: `sha256:${"6".repeat(64)}`,
        kind: "runtime_quality.candidate_unpriced_acquisition_policy",
        media_type: "application/json",
        manifest_profile_sha256: `sha256:${"7".repeat(64)}`,
      },
      candidate_digest: `sha256:${"8".repeat(64)}`,
    },
    scheduler_action: "reject",
    scheduler_reason: "roi_below_threshold",
    monetary_cost: "not_established",
    information_value: "not_established",
    action_authority: "not_established",
    publication_authority: false,
  };
  const unknownPayload = {
    ...basePayload,
    current_action: { status: "unknown", evaluation_disposition: "unknown" },
  };
  const blockedPayload = {
    ...basePayload,
    current_action: {
      status: "blocked",
      action_generation: 2,
      job_id: "candidate-action-transport",
      job_state: "completed",
      coarse_phase: "terminal",
      receipt_phase: "terminal",
      recovery_state: "complete",
      selected_receipt_ref: {
        artifact_id: `sha256:${"9".repeat(64)}`,
        kind: "runtime_quality.acquisition_route_loop_receipt",
        media_type: "application/json",
        manifest_profile_sha256: `sha256:${"0".repeat(64)}`,
      },
      terminal_outcome: "candidate_blocked",
      evaluation_disposition: "blocked",
      selected_evaluation: null,
      blocker_reason: "required prior evaluation is unavailable",
    },
  };

  for (const payload of [unknownPayload, blockedPayload]) {
    const calls = [];
    const client = createClient(calls, payload);
    const response = await client.getRunCandidateAcquisitionExperiment({
      run_id: runId,
    });

    assert.deepEqual(response, payload);
    assert.equal(response.monetary_cost, "not_established");
    assert.equal(response.information_value, "not_established");
    assert.equal(response.action_authority, "not_established");
    assert.equal(response.publication_authority, false);
    assert.equal(calls.length, 1);
    assert.equal(
      calls[0].url,
      "https://runtime.test/api/v1/runs/run%2Fwith%20space/candidate-acquisition-experiment",
    );
    assert.equal(calls[0].init.method, "GET");
    assert.equal(calls[0].init.body, undefined);
  }
  assert.deepEqual(blockedPayload.current_action.selected_receipt_ref, {
    artifact_id: `sha256:${"9".repeat(64)}`,
    kind: "runtime_quality.acquisition_route_loop_receipt",
    media_type: "application/json",
    manifest_profile_sha256: `sha256:${"0".repeat(64)}`,
  });
});

test("candidate acquisition experiment decision request POST forwards exact preparation pins", async () => {
  // Transport fixture only; refs and response do not establish permission or an external effect.
  const runId = "run/with space";
  const routeId = `sha256:${"a".repeat(64)}`;
  const selectedRef = (artifact_id, kind) => ({
    artifact_id,
    kind,
    media_type: "application/json",
    manifest_profile_sha256: `sha256:${"b".repeat(64)}`,
  });
  const body = {
    route_id: routeId,
    replay_pins: {
      source_job_id: "source-job",
      source_payload_ref: `sha256:${"c".repeat(64)}`,
      request_content_hash: `sha256:${"d".repeat(64)}`,
      compiled_ref: selectedRef(
        `sha256:${"e".repeat(64)}`,
        "runtime.compiled_recursive_generation_cycle",
      ),
      planner_report_ref: selectedRef(
        `sha256:${"f".repeat(64)}`,
        "runtime.acquisition_planner_report",
      ),
      compiler_report_ref: selectedRef(
        `sha256:${"1".repeat(64)}`,
        "runtime.data_requirement_compilation_report",
      ),
      configured_port_source_ref: selectedRef(
        `sha256:${"2".repeat(64)}`,
        "runtime.quality.n7_configured_candidate_port_source",
      ),
      policy_ref: selectedRef(
        `sha256:${"3".repeat(64)}`,
        "runtime_quality.candidate_unpriced_acquisition_policy",
      ),
      candidate_digest: `sha256:${"4".repeat(64)}`,
    },
    idempotency_key: "decision-request-fixture-1",
    human_decision_record_ref: `sha256:${"5".repeat(64)}`,
  };
  const originalBody = structuredClone(body);
  const responsePayload = {
    authority_decision_ref: `sha256:${"6".repeat(64)}`,
    outcome: "decision_required",
    human_decision_request: {
      request_id: "transport-request-1",
      state: "pending",
    },
    route_id: routeId,
    run_id: runId,
    world_growth: "not_established",
  };
  const calls = [];
  const client = createClient(calls, responsePayload);

  assert.deepEqual(
    await client.requestRunCandidateAcquisitionExperimentDecision({
      run_id: runId,
      route_id: routeId,
      body,
    }),
    responsePayload,
  );
  assert.deepEqual(body, originalBody);
  assert.equal(calls.length, 1);
  assert.equal(
    calls[0].url,
    `https://runtime.test/api/v1/runs/${encodeURIComponent(runId)}` +
      `/candidate-acquisition-experiment/${encodeURIComponent(routeId)}/decision-request`,
  );
  assert.equal(calls[0].init.method, "POST");
  assert.deepEqual(JSON.parse(calls[0].init.body), body);

  let deniedCalls = 0;
  const deniedClient = new RuntimeApiClient({
    baseUrl: "https://runtime.test",
    fetchImpl: async () => {
      deniedCalls += 1;
      return new Response('{"code":"forbidden"}', {
        status: 403,
        statusText: "Forbidden",
        headers: { "Content-Type": "application/problem+json" },
      });
    },
  });
  await assert.rejects(
    () =>
      deniedClient.requestRunCandidateAcquisitionExperimentDecision({
        run_id: runId,
        route_id: routeId,
        body,
      }),
    {
      name: "Error",
      message: 'Runtime API request failed: 403 Forbidden {"code":"forbidden"}',
    },
  );
  assert.equal(deniedCalls, 1);
});

test("candidate acquisition experiment execute POST keeps decision request nested", async () => {
  // Transport fixture only; nested refs do not assert a PA2 grant or execution result.
  const runId = "run/with space";
  const routeId = `sha256:${"7".repeat(64)}`;
  const selectedRef = (artifact_id, kind, profileHex) => ({
    artifact_id,
    kind,
    media_type: "application/json",
    manifest_profile_sha256: `sha256:${profileHex.repeat(64)}`,
  });
  const request = {
    route_id: routeId,
    replay_pins: {
      source_job_id: "source-job",
      source_payload_ref: `sha256:${"8".repeat(64)}`,
      request_content_hash: `sha256:${"9".repeat(64)}`,
      compiled_ref: selectedRef(
        `sha256:${"a".repeat(64)}`,
        "runtime.compiled_recursive_generation_cycle",
        "1",
      ),
      planner_report_ref: selectedRef(
        `sha256:${"b".repeat(64)}`,
        "runtime.acquisition_planner_report",
        "2",
      ),
      compiler_report_ref: selectedRef(
        `sha256:${"c".repeat(64)}`,
        "runtime.data_requirement_compilation_report",
        "3",
      ),
      configured_port_source_ref: selectedRef(
        `sha256:${"d".repeat(64)}`,
        "runtime.quality.n7_configured_candidate_port_source",
        "4",
      ),
      policy_ref: selectedRef(
        `sha256:${"e".repeat(64)}`,
        "runtime_quality.candidate_unpriced_acquisition_policy",
        "5",
      ),
      candidate_digest: `sha256:${"f".repeat(64)}`,
    },
    idempotency_key: "execute-request-fixture-1",
    human_decision_record_ref: `sha256:${"0".repeat(64)}`,
  };
  const body = {
    request,
    decision_ref: `sha256:${"6".repeat(64)}`,
  };
  const originalBody = structuredClone(body);
  const responsePayload = {
    run_id: runId,
    route_id: routeId,
    job_id: "queued-job-fixture",
    authority_decision_ref: body.decision_ref,
    status: "accepted",
    receipt_phase: "requested",
    world_growth: "not_established",
  };
  const calls = [];
  const client = createClient(calls, responsePayload);

  assert.deepEqual(
    await client.executeRunCandidateAcquisitionExperiment({
      run_id: runId,
      route_id: routeId,
      body,
    }),
    responsePayload,
  );
  assert.deepEqual(body, originalBody);
  assert.equal(calls.length, 1);
  assert.equal(
    calls[0].url,
    `https://runtime.test/api/v1/runs/${encodeURIComponent(runId)}` +
      `/candidate-acquisition-experiment/${encodeURIComponent(routeId)}/execute`,
  );
  assert.equal(calls[0].init.method, "POST");
  assert.deepEqual(JSON.parse(calls[0].init.body), body);

  let deniedCalls = 0;
  const deniedClient = new RuntimeApiClient({
    baseUrl: "https://runtime.test",
    fetchImpl: async () => {
      deniedCalls += 1;
      return new Response('{"code":"forbidden"}', {
        status: 403,
        statusText: "Forbidden",
        headers: { "Content-Type": "application/problem+json" },
      });
    },
  });
  await assert.rejects(
    () =>
      deniedClient.executeRunCandidateAcquisitionExperiment({
        run_id: runId,
        route_id: routeId,
        body,
      }),
    {
      name: "Error",
      message: 'Runtime API request failed: 403 Forbidden {"code":"forbidden"}',
    },
  );
  assert.equal(deniedCalls, 1);
});

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
