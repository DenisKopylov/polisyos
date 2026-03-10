import fs from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";

const currentDir = path.dirname(fileURLToPath(import.meta.url));
const dashboardRoot = path.resolve(currentDir, "..");
const fixturesDir = path.resolve(
  dashboardRoot,
  "src/test/contracts/fixtures",
);

function parseArgs(argv) {
  const args = new Map();
  for (let index = 0; index < argv.length; index += 1) {
    const value = argv[index];
    if (!value.startsWith("--")) {
      continue;
    }
    args.set(value.slice(2), argv[index + 1]);
    index += 1;
  }
  return args;
}

async function requestJson(baseUrl, request) {
  const response = await fetch(new URL(request.path, baseUrl), {
    body: request.body ? JSON.stringify(request.body) : undefined,
    headers: request.body
      ? {
          "content-type": "application/json",
        }
      : undefined,
    method: request.method,
  });
  const text = await response.text();
  const payload = text ? JSON.parse(text) : null;

  if (!response.ok) {
    throw new Error(
      `${request.method} ${request.path} failed with ${response.status}: ${text}`,
    );
  }

  return payload;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const baseUrl = new URL(
    args.get("base-url") ??
      process.env.RUNTIME_CONTRACT_BASE_URL ??
      "http://127.0.0.1:8000",
  );
  const lexOutputDir =
    args.get("lex-output-dir") ??
    process.env.RUNTIME_CONTRACT_LEX_OUTPUT_DIR ??
    "data/lex_knowledge";

  await fs.mkdir(fixturesDir, { recursive: true });

  const authMe = await requestJson(baseUrl, {
    method: "GET",
    path: "/api/v1/auth/me",
  });
  const capabilities = await requestJson(baseUrl, {
    method: "GET",
    path: "/api/v1/control/capabilities",
  });
  const health = await requestJson(baseUrl, {
    method: "GET",
    path: "/api/v1/health",
  });
  const runsList = await requestJson(baseUrl, {
    method: "GET",
    path: "/api/v1/runs?limit=24",
  });
  const runId = runsList?.runs?.[0]?.run_id;

  if (!runId) {
    throw new Error("Unable to record runtime contracts without a sample run id.");
  }

  const runDetails = await requestJson(baseUrl, {
    method: "GET",
    path: `/api/v1/runs/${runId}`,
  });
  const runTimeline = await requestJson(baseUrl, {
    method: "GET",
    path: `/api/v1/runs/${runId}/timeline`,
  });
  const governanceDebug = await requestJson(baseUrl, {
    method: "GET",
    path: `/api/v1/debug/runs/${runId}/governance`,
  });
  const runEvidenceContext = await requestJson(baseUrl, {
    method: "GET",
    path: `/api/v1/runs/${runId}/evidence-context`,
  });
  const promotionCandidates = await requestJson(baseUrl, {
    method: "GET",
    path: "/api/v1/control/data/promotion/candidates",
  });
  const promotionId =
    promotionCandidates?.candidates?.[0]?.promotion_id ??
    runEvidenceContext?.context?.promotion_candidates?.[0]?.promotion_id;

  if (!promotionId) {
    throw new Error(
      "Unable to record promotion mutation contracts without a promotion id.",
    );
  }

  const lexSearch = await requestJson(baseUrl, {
    method: "POST",
    path: "/api/v1/control/lex/search",
    body: {
      output_dir: lexOutputDir,
      query: "governance",
      top_k: 20,
    },
  });
  const promotionApprove = await requestJson(baseUrl, {
    method: "POST",
    path: `/api/v1/control/data/promotion/${promotionId}/approve`,
    body: {
      reason: "runtime-dashboard contract snapshot approve",
    },
  });
  const promotionReject = await requestJson(baseUrl, {
    method: "POST",
    path: `/api/v1/control/data/promotion/${promotionId}/reject`,
    body: {
      reason: "runtime-dashboard contract snapshot reject",
    },
  });

  const fixtures = {
    "auth-me.json": authMe,
    "capabilities.json": capabilities,
    "governance-debug.json": governanceDebug,
    "health.json": health,
    "lex-search.json": lexSearch,
    "promotion-approve.json": promotionApprove,
    "promotion-candidates.json": promotionCandidates,
    "promotion-reject.json": promotionReject,
    "run-details.json": runDetails,
    "run-evidence-context.json": runEvidenceContext,
    "run-timeline.json": runTimeline,
    "runs-list.json": runsList,
  };

  await Promise.all(
    Object.entries(fixtures).map(([fileName, payload]) =>
      fs.writeFile(
        path.join(fixturesDir, fileName),
        `${JSON.stringify(payload, null, 2)}\n`,
        "utf-8",
      ),
    ),
  );

  process.stdout.write(
    `${JSON.stringify(
      {
        baseUrl: baseUrl.toString(),
        lexOutputDir,
        promotionId,
        recorded: Object.keys(fixtures),
        runId,
      },
      null,
      2,
    )}\n`,
  );
}

main().catch((error) => {
  process.stderr.write(`${error instanceof Error ? error.stack : String(error)}\n`);
  process.exitCode = 1;
});
