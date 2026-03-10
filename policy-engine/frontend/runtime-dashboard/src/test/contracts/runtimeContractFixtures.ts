import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import type { ZodType } from "zod";

import {
  authMeSchema,
  capabilityManifestSchema,
  governanceDebugSchema,
  healthSchema,
  lexSearchResponseSchema,
  promotionCandidatesSchema,
  promotionDecisionResponseSchema,
  runDetailsSchema,
  runEvidenceContextSchema,
  runsListSchema,
  runTimelineSchema,
} from "../../api/validators";

type RecordContext = {
  outputDir: string;
  promotionId: string;
  runId: string;
};

type RecordRequest =
  | {
      body?: unknown;
      method: "GET" | "POST";
      path: string;
    }
  | ((context: RecordContext) => {
      body?: unknown;
      method: "GET" | "POST";
      path: string;
    });

export type RuntimeContractFixtureDefinition = {
  fileName: string;
  key:
    | "auth-me"
    | "capabilities"
    | "governance-debug"
    | "health"
    | "lex-search"
    | "promotion-approve"
    | "promotion-candidates"
    | "promotion-reject"
    | "run-details"
    | "run-evidence-context"
    | "run-timeline"
    | "runs-list";
  matcher: RegExp;
  method: "GET" | "POST";
  mswPath: string;
  record: RecordRequest;
  schema: ZodType;
};

const fixturesDir = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "fixtures",
);

export const runtimeContractFixtureDefinitions: RuntimeContractFixtureDefinition[] = [
  {
    fileName: "auth-me.json",
    key: "auth-me",
    matcher: /^\/api\/v1\/auth\/me$/,
    method: "GET",
    mswPath: "*/api/v1/auth/me",
    record: {
      method: "GET",
      path: "/api/v1/auth/me",
    },
    schema: authMeSchema,
  },
  {
    fileName: "capabilities.json",
    key: "capabilities",
    matcher: /^\/api\/v1\/control\/capabilities$/,
    method: "GET",
    mswPath: "*/api/v1/control/capabilities",
    record: {
      method: "GET",
      path: "/api/v1/control/capabilities",
    },
    schema: capabilityManifestSchema,
  },
  {
    fileName: "health.json",
    key: "health",
    matcher: /^\/api\/v1\/health$/,
    method: "GET",
    mswPath: "*/api/v1/health",
    record: {
      method: "GET",
      path: "/api/v1/health",
    },
    schema: healthSchema,
  },
  {
    fileName: "runs-list.json",
    key: "runs-list",
    matcher: /^\/api\/v1\/runs$/,
    method: "GET",
    mswPath: "*/api/v1/runs",
    record: {
      method: "GET",
      path: "/api/v1/runs?limit=24",
    },
    schema: runsListSchema,
  },
  {
    fileName: "run-details.json",
    key: "run-details",
    matcher: /^\/api\/v1\/runs\/[^/]+$/,
    method: "GET",
    mswPath: "*/api/v1/runs/:runId",
    record: ({ runId }) => ({
      method: "GET",
      path: `/api/v1/runs/${runId}`,
    }),
    schema: runDetailsSchema,
  },
  {
    fileName: "run-timeline.json",
    key: "run-timeline",
    matcher: /^\/api\/v1\/runs\/[^/]+\/timeline$/,
    method: "GET",
    mswPath: "*/api/v1/runs/:runId/timeline",
    record: ({ runId }) => ({
      method: "GET",
      path: `/api/v1/runs/${runId}/timeline`,
    }),
    schema: runTimelineSchema,
  },
  {
    fileName: "governance-debug.json",
    key: "governance-debug",
    matcher: /^\/api\/v1\/debug\/runs\/[^/]+\/governance$/,
    method: "GET",
    mswPath: "*/api/v1/debug/runs/:runId/governance",
    record: ({ runId }) => ({
      method: "GET",
      path: `/api/v1/debug/runs/${runId}/governance`,
    }),
    schema: governanceDebugSchema,
  },
  {
    fileName: "run-evidence-context.json",
    key: "run-evidence-context",
    matcher: /^\/api\/v1\/runs\/[^/]+\/evidence-context$/,
    method: "GET",
    mswPath: "*/api/v1/runs/:runId/evidence-context",
    record: ({ runId }) => ({
      method: "GET",
      path: `/api/v1/runs/${runId}/evidence-context`,
    }),
    schema: runEvidenceContextSchema,
  },
  {
    fileName: "promotion-candidates.json",
    key: "promotion-candidates",
    matcher: /^\/api\/v1\/control\/data\/promotion\/candidates$/,
    method: "GET",
    mswPath: "*/api/v1/control/data/promotion/candidates",
    record: {
      method: "GET",
      path: "/api/v1/control/data/promotion/candidates",
    },
    schema: promotionCandidatesSchema,
  },
  {
    fileName: "lex-search.json",
    key: "lex-search",
    matcher: /^\/api\/v1\/control\/lex\/search$/,
    method: "POST",
    mswPath: "*/api/v1/control/lex/search",
    record: ({ outputDir }) => ({
      body: {
        output_dir: outputDir,
        query: "governance",
        top_k: 20,
      },
      method: "POST",
      path: "/api/v1/control/lex/search",
    }),
    schema: lexSearchResponseSchema,
  },
  {
    fileName: "promotion-approve.json",
    key: "promotion-approve",
    matcher: /^\/api\/v1\/control\/data\/promotion\/[^/]+\/approve$/,
    method: "POST",
    mswPath: "*/api/v1/control/data/promotion/:promotionId/approve",
    record: ({ promotionId }) => ({
      body: {
        reason: "runtime-dashboard contract snapshot approve",
      },
      method: "POST",
      path: `/api/v1/control/data/promotion/${promotionId}/approve`,
    }),
    schema: promotionDecisionResponseSchema,
  },
  {
    fileName: "promotion-reject.json",
    key: "promotion-reject",
    matcher: /^\/api\/v1\/control\/data\/promotion\/[^/]+\/reject$/,
    method: "POST",
    mswPath: "*/api/v1/control/data/promotion/:promotionId/reject",
    record: ({ promotionId }) => ({
      body: {
        reason: "runtime-dashboard contract snapshot reject",
      },
      method: "POST",
      path: `/api/v1/control/data/promotion/${promotionId}/reject`,
    }),
    schema: promotionDecisionResponseSchema,
  },
];

export function getRuntimeContractFixturesDir() {
  return fixturesDir;
}

export function loadRuntimeContractFixture(
  definition: RuntimeContractFixtureDefinition,
) {
  const payload = JSON.parse(
    fs.readFileSync(path.join(fixturesDir, definition.fileName), "utf-8"),
  );

  return {
    ...definition,
    payload,
  };
}

export function loadAllRuntimeContractFixtures() {
  return runtimeContractFixtureDefinitions.map(loadRuntimeContractFixture);
}

export function matchRuntimeContractFixture(method: string, pathname: string) {
  return runtimeContractFixtureDefinitions.find(
    (fixture) =>
      fixture.method === method.toUpperCase() && fixture.matcher.test(pathname),
  );
}
