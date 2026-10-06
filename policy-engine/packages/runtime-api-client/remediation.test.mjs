import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import {
  existsSync,
  mkdtempSync,
  readdirSync,
  readFileSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

const PACKAGE_ROOT = path.dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = path.resolve(PACKAGE_ROOT, "../..");
const SPEC_PATH = path.join(
  PROJECT_ROOT,
  "schemas/runtime_api_v1.openapi.json",
);
const GENERATOR = path.join(
  PACKAGE_ROOT,
  "scripts/generate-runtime-api-client.sh",
);

test("package generation keeps raw client intermediates outside the output family", () => {
  const outputRoot = mkdtempSync(
    path.join(os.tmpdir(), "polisyos-runtime-client-remediation-"),
  );
  const specRoot = mkdtempSync(
    path.join(os.tmpdir(), "polisyos-runtime-client-remediation-spec-"),
  );
  const openapiPath = path.join(specRoot, "override.openapi.json");
  try {
    const openapi = JSON.parse(readFileSync(SPEC_PATH, "utf8"));
    openapi.paths["/api/v1/cli-01-openapi-override-witness"] = {
      get: {
        operationId: "get_cli_01_openapi_override_witness",
        responses: {
          200: {
            content: {
              "application/json": {
                schema: {
                  properties: { witness: { type: "string" } },
                  required: ["witness"],
                  type: "object",
                },
              },
            },
            description: "CLI-01 override witness",
          },
        },
      },
    };
    writeFileSync(openapiPath, JSON.stringify(openapi), "utf8");
    execFileSync(
      "bash",
      [GENERATOR, "--openapi", openapiPath, "--output-root", outputRoot],
      { cwd: PROJECT_ROOT, stdio: "pipe" },
    );

    const observed = [];
    const walk = (directory) => {
      for (const entry of readdirSync(directory, { withFileTypes: true })) {
        const entryPath = path.join(directory, entry.name);
        if (entry.isDirectory()) walk(entryPath);
        else observed.push(path.relative(outputRoot, entryPath));
      }
    };
    walk(outputRoot);

    assert.deepEqual(observed.sort(), [
      "packages/runtime-api-client/canonicalRuntimeApiClient.js",
      "packages/runtime-api-client/canonicalRuntimeApiClient.ts",
      "packages/runtime-api-client/types.ts",
    ]);
    assert.match(
      readFileSync(
        path.join(
          outputRoot,
          "packages/runtime-api-client/canonicalRuntimeApiClient.ts",
        ),
        "utf8",
      ),
      /cli-01-openapi-override-witness/,
    );
  } finally {
    rmSync(outputRoot, { recursive: true, force: true });
    rmSync(specRoot, { recursive: true, force: true });
  }
});

test("the committed package surface does not retain raw generated twins", () => {
  assert.equal(
    existsSync(path.join(PACKAGE_ROOT, "runtimeApiClient.ts")),
    false,
  );
  assert.equal(
    existsSync(path.join(PACKAGE_ROOT, "runtimeApiClient.js")),
    false,
  );
});

test("the packed package serves dashboard and Atlas ESM and type consumers", () => {
  const archiveRoot = mkdtempSync(
    path.join(os.tmpdir(), "polisyos-runtime-client-pack-"),
  );
  const consumers = [
    {
      name: "dashboard",
      runtime: `import assert from "node:assert/strict";
import { RuntimeApiClient } from "@polisyos/runtime-api-client";

const calls = [];
const bytes = Uint8Array.from([0, 255, 17, 34]);
const client = new RuntimeApiClient({
  baseUrl: "https://runtime.test/",
  fetchImpl: async (url, init) => {
    calls.push({ url, init });
    return new Response(bytes, {
      status: 200,
      headers: { "Content-Type": "application/pdf" },
    });
  },
});
const delivered = await client.getRunHumanDecisionEvidenceContent({
  run_id: "run/with space",
  artifact_id: "sha256:evidence",
  "X-PolicyOS-Human-Decision-Exposure": "sha256:verified-exposure",
});

assert.deepEqual(Array.from(new Uint8Array(delivered)), [0, 255, 17, 34]);
assert.equal(calls.length, 1);
assert.equal(
  calls[0].url,
  "https://runtime.test/api/v1/runs/run%2Fwith%20space/human-decision-evidence/sha256%3Aevidence/content",
);
assert.equal(calls[0].init.method, "GET");
assert.equal(
  new Headers(calls[0].init.headers).get("X-PolicyOS-Human-Decision-Exposure"),
  "sha256:verified-exposure",
);
`,
      types: `import { RuntimeApiClient } from "@polisyos/runtime-api-client";
import type { ArtifactID } from "@polisyos/runtime-api-client";
import type { components } from "@polisyos/runtime-api-client/types";

const artifactId: ArtifactID = "sha256:evidence";
const schemaArtifactId: components["schemas"]["ArtifactID"] = artifactId;
type EvidenceRequest = Parameters<RuntimeApiClient["getRunHumanDecisionEvidenceContent"]>[0];
const validRequest: EvidenceRequest = {
  run_id: "run-1",
  artifact_id: schemaArtifactId,
  "X-PolicyOS-Human-Decision-Exposure": "sha256:verified-exposure",
};
void validRequest;
// @ts-expect-error The exported request contract requires the exposure binding.
const invalidRequest: EvidenceRequest = { run_id: "run-1", artifact_id: artifactId };
void invalidRequest;
`,
    },
    {
      name: "atlas",
      runtime: `import assert from "node:assert/strict";
import { RuntimeApiClient } from "@polisyos/runtime-api-client";

const calls = [];
const client = new RuntimeApiClient({
  baseUrl: "https://runtime.test/",
  fetchImpl: async (url, init) => {
    calls.push({ url, init });
    return Response.json({ runs: [] });
  },
});
const response = await client.getRunsBatch({ body: { run_ids: ["run-1"] } });

assert.deepEqual(response, { runs: [] });
assert.equal(calls.length, 1);
assert.equal(calls[0].url, "https://runtime.test/api/v1/runs/batch");
assert.equal(calls[0].init.method, "POST");
assert.equal(calls[0].init.body, JSON.stringify({ run_ids: ["run-1"] }));
`,
      types: `import type { RuntimeApiClient, QuantityValueOutput } from "@polisyos/runtime-api-client";
import type { components } from "@polisyos/runtime-api-client/types";

type RunsBatchRequest = Parameters<RuntimeApiClient["getRunsBatch"]>[0];
const validRequest: RunsBatchRequest = { body: { run_ids: ["run-1"] } };
type QuantityContract = QuantityValueOutput;
type SchemaArtifactId = components["schemas"]["ArtifactID"];
void validRequest;
declare const quantity: QuantityContract;
declare const artifactId: SchemaArtifactId;
void quantity;
void artifactId;
// @ts-expect-error Batch run IDs are strings in the exported package types.
const invalidRequest: RunsBatchRequest = { body: { run_ids: [42] } };
void invalidRequest;
`,
    },
  ];

  try {
    const packedJson = execFileSync(
      "npm",
      ["pack", "--ignore-scripts", "--json", "--pack-destination", archiveRoot],
      { cwd: PACKAGE_ROOT, encoding: "utf8", stdio: "pipe" },
    );
    const [pack] = JSON.parse(packedJson);
    assert.equal(pack.name, "@polisyos/runtime-api-client");
    const entries = pack.files.map(({ path: entry }) => entry);
    assert.ok(entries.includes("canonicalRuntimeApiClient.js"));
    assert.ok(entries.includes("canonicalRuntimeApiClient.ts"));
    assert.ok(entries.includes("types.ts"));
    assert.equal(entries.includes("runtimeApiClient.js"), false);
    assert.equal(entries.includes("runtimeApiClient.ts"), false);
    const tarball = path.join(archiveRoot, pack.filename);
    assert.equal(existsSync(tarball), true);

    for (const consumer of consumers) {
      const consumerRoot = mkdtempSync(
        path.join(os.tmpdir(), `polisyos-${consumer.name}-client-consumer-`),
      );
      try {
        writeFileSync(
          path.join(consumerRoot, "package.json"),
          JSON.stringify({
            name: `polisyos-${consumer.name}-client-consumer`,
            private: true,
            type: "module",
          }),
        );
        execFileSync(
          "npm",
          [
            "install",
            "--offline",
            "--ignore-scripts",
            "--no-audit",
            "--no-fund",
            tarball,
          ],
          { cwd: consumerRoot, encoding: "utf8", stdio: "pipe" },
        );
        const runtimePath = path.join(consumerRoot, "consumer.mjs");
        const typesPath = path.join(consumerRoot, "consumer.ts");
        writeFileSync(runtimePath, consumer.runtime);
        writeFileSync(typesPath, consumer.types);

        execFileSync(process.execPath, [runtimePath], {
          cwd: consumerRoot,
          encoding: "utf8",
          stdio: "pipe",
        });
        execFileSync(
          process.execPath,
          [
            path.join(PACKAGE_ROOT, "node_modules/typescript/bin/tsc"),
            "--noEmit",
            "--strict",
            "--skipLibCheck",
            "--target",
            "ES2022",
            "--lib",
            "ES2022,DOM",
            "--module",
            "ESNext",
            "--moduleResolution",
            "Bundler",
            typesPath,
          ],
          { cwd: consumerRoot, encoding: "utf8", stdio: "pipe" },
        );
      } finally {
        rmSync(consumerRoot, { recursive: true, force: true });
      }
    }
  } finally {
    rmSync(archiveRoot, { recursive: true, force: true });
  }
});
