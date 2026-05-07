import assert from "node:assert/strict";
import test from "node:test";

import { RuntimeApiClient } from "./runtimeApiClient.js";

function createClient(calls) {
  return new RuntimeApiClient({
    baseUrl: "https://runtime.test/",
    fetchImpl: async (url, init) => {
      calls.push({ url, init });
      return new Response(JSON.stringify({ ok: true }), {
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
