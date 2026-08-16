import { spawnSync } from "node:child_process";
import { existsSync, mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";

import { createServer } from "vite";

const currentFile = fileURLToPath(import.meta.url);
const dashboardRoot = path.resolve(path.dirname(currentFile), "..");
const policyEngineRoot = path.resolve(dashboardRoot, "../..");
const persistenceBridgePath = "apps/runtime-dashboard/scripts/persist_atlas_evidence.py";
const routeTestPath = "src/app/routes/routes.test.tsx";

function readCasRoot(argv) {
  if (argv.length !== 2 || argv[0] !== "--cas-root" || !argv[1]) {
    throw new TypeError("reconciliation requires --cas-root PATH");
  }
  return path.resolve(argv[1]);
}

function readInvocation(argv) {
  if (argv.length === 1 && argv[0] === "--canonical-facts") {
    return { mode: "canonical-facts" };
  }
  return { mode: "persist", casRoot: readCasRoot(argv) };
}

function readJson(relativePath) {
  return JSON.parse(readFileSync(path.resolve(policyEngineRoot, relativePath), "utf8"));
}

/**
 * C10 owns the behavioral receipt: this runs the real route test and returns
 * its JSON bytes for the typed reconciler to parse and content-bind.
 */
function runRouteTestMatrix() {
  const reportRoot = mkdtempSync(path.join(tmpdir(), "polisyos-c10-routes-"));
  const reportPath = path.join(reportRoot, "routes-vitest.json");
  const result = spawnSync(
    "corepack",
    [
      "pnpm",
      "exec",
      "vitest",
      "run",
      routeTestPath,
      "--maxWorkers=2",
      "--reporter=json",
      `--outputFile=${reportPath}`,
    ],
    {
      cwd: dashboardRoot,
      encoding: "utf8",
      maxBuffer: 8 * 1024 * 1024,
    },
  );
  if (existsSync(reportPath)) {
    return {
      bytes: readFileSync(reportPath),
      exit_code: result.status ?? 1,
      cleanup: () => rmSync(reportRoot, { recursive: true, force: true }),
    };
  }
  return {
    bytes: Buffer.from(
      JSON.stringify({
        runner_error: result.error?.message ?? result.stderr ?? "route test produced no JSON",
        success: false,
      }),
    ),
    exit_code: result.status ?? 1,
    cleanup: () => rmSync(reportRoot, { recursive: true, force: true }),
  };
}

const invocation = readInvocation(process.argv.slice(2));
const server = await createServer({
  root: dashboardRoot,
  appType: "custom",
  logLevel: "silent",
  server: { hmr: false, middlewareMode: true },
});
let routeTest;

try {
  const reconciliationModule = await server.ssrLoadModule(
    "/src/test/evidence/atlasSurfaceReadinessReconciliation.ts",
  );
  if (invocation.mode === "canonical-facts") {
    const routesModule = await server.ssrLoadModule("/src/app/routes/routes.tsx");
    process.stdout.write(
      `${JSON.stringify({
        redirects: reconciliationModule.collectCanonicalDeprecatedRedirects(
          routesModule.APP_ROUTES,
        ),
      })}\n`,
    );
  } else {
    routeTest = runRouteTestMatrix();
    const captureModule = await server.ssrLoadModule(
      "/src/test/evidence/atlasAutomatedEvidenceCapture.ts",
    );
    const reconciliation = reconciliationModule.buildAtlasSurfaceReadinessReconciliation({
      adoption_ledger: readJson("architecture/atlas_surfaces/atlas-v15-adoption-ledger.json"),
      readiness_ledger: readJson(
        "architecture/atlas_surfaces/live-application-readiness-ledger.json",
      ),
      route_test_report_bytes: routeTest.bytes,
      route_test_exit_code: routeTest.exit_code,
      observed_at: new Date().toISOString(),
      verified_at: new Date().toISOString(),
    });
    const bridge = spawnSync(
      "uv",
      ["run", "--frozen", "python", persistenceBridgePath],
      {
        cwd: policyEngineRoot,
        encoding: "utf8",
        input: JSON.stringify({
          operation: "persist_atlas_evidence",
          raw_report_base64: Buffer.from(reconciliation.raw_report_bytes).toString(
            "base64",
          ),
          payload: reconciliation.payload,
          receipt: reconciliation.receipt_without_payload_ref,
        }),
        env: {
          ...process.env,
          POLISYOS_CAS_BACKEND: "filesystem",
          POLISYOS_CAS_ROOT: invocation.casRoot,
        },
        maxBuffer: 8 * 1024 * 1024,
      },
    );
    const persisted = JSON.parse(bridge.stdout);
    if (bridge.status !== 0) {
      throw new TypeError(`C10 persistence bridge failed: ${JSON.stringify(persisted)}`);
    }
    captureModule.assertAtlasEvidencePersistenceResult(persisted);
    process.stdout.write(
      `${JSON.stringify({
        reconciliation: reconciliation.payload.result,
        route_test_exit_code: routeTest.exit_code,
        persistence: persisted,
      })}\n`,
    );
    process.exitCode = reconciliation.exit_code;
  }
} catch (error) {
  process.stderr.write(`${error instanceof Error ? error.stack : String(error)}\n`);
  process.exitCode = 1;
} finally {
  routeTest?.cleanup();
  await server.close();
}
