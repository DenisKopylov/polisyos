import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { existsSync, mkdtempSync, readdirSync, rmSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

const PACKAGE_ROOT = path.dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = path.resolve(PACKAGE_ROOT, "../..");
const SPEC_PATH = path.join(PROJECT_ROOT, "schemas/runtime_api_v1.openapi.json");
const GENERATOR = path.join(
  PACKAGE_ROOT,
  "scripts/generate-runtime-api-client.sh",
);

test("package generation keeps raw client intermediates outside the output family", () => {
  const outputRoot = mkdtempSync(
    path.join(os.tmpdir(), "polisyos-runtime-client-remediation-"),
  );
  try {
    execFileSync(
      "bash",
      [GENERATOR, "--openapi", SPEC_PATH, "--output-root", outputRoot],
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
  } finally {
    rmSync(outputRoot, { recursive: true, force: true });
  }
});

test("the committed package surface does not retain raw generated twins", () => {
  assert.equal(existsSync(path.join(PACKAGE_ROOT, "runtimeApiClient.ts")), false);
  assert.equal(existsSync(path.join(PACKAGE_ROOT, "runtimeApiClient.js")), false);
});
