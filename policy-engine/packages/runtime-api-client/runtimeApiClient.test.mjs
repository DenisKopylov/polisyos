import assert from "node:assert/strict";
import test from "node:test";

import { RuntimeApiClient } from "./runtimeApiClient.js";

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
