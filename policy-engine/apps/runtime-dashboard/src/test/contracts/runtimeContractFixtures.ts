import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import type { ZodType } from "zod";

import {
  authMeSchema,
  capabilityManifestSchema,
  compareRunsSchema,
  counterfactualMetricsSchema,
  fabricImpactAnalysisSchema,
  fabricQualityBatchSchema,
  fabricReplaySchema,
  fabricSourceScorecardsSchema,
  fabricTrustBatchSchema,
  governanceDebugSchema,
  healthSchema,
  lineageBatchResponseSchema,
  lineageResponseSchema,
  lexSearchResponseSchema,
  promotionCandidatesSchema,
  promotionDecisionResponseSchema,
  runFabricDecisionDataSchema,
  runDetailsSchema,
  runEvidenceContextSchema,
  runQuantitiesSchema,
  runsListSchema,
  runTimelineSchema,
  temporalCapabilitiesSchema,
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
    | "compare-run"
    | "counterfactual-metrics"
    | "fabric-impact"
    | "fabric-quality-batch"
    | "fabric-replay"
    | "fabric-source-scorecards"
    | "fabric-trust-batch"
    | "governance-debug"
    | "health"
    | "lineage"
    | "lineage-batch"
    | "lex-search"
    | "promotion-approve"
    | "promotion-candidates"
    | "promotion-reject"
    | "run-details"
    | "run-evidence-context"
    | "run-fabric-decision-data"
    | "run-quantities"
    | "run-timeline"
    | "runs-list"
    | "temporal-capabilities";
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

export const runtimeContractFixtureDefinitions: RuntimeContractFixtureDefinition[] =
  [
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
      fileName: "run-quantities.json",
      key: "run-quantities",
      matcher: /^\/api\/v1\/runs\/[^/]+\/quantities$/,
      method: "GET",
      mswPath: "*/api/v1/runs/:runId/quantities",
      record: ({ runId }) => ({
        method: "GET",
        path: `/api/v1/runs/${runId}/quantities`,
      }),
      schema: runQuantitiesSchema,
    },
    {
      fileName: "run-fabric-decision-data.json",
      key: "run-fabric-decision-data",
      matcher: /^\/api\/v1\/runs\/[^/]+\/fabric-decision-data$/,
      method: "GET",
      mswPath: "*/api/v1/runs/:runId/fabric-decision-data",
      record: ({ runId }) => ({
        method: "GET",
        path: `/api/v1/runs/${runId}/fabric-decision-data`,
      }),
      schema: runFabricDecisionDataSchema,
    },
    {
      fileName: "lineage.json",
      key: "lineage",
      matcher: /^\/api\/v1\/lineage\/[^/]+$/,
      method: "GET",
      mswPath: "*/api/v1/lineage/:lineageId",
      record: ({ runId }) => ({
        method: "GET",
        path: `/api/v1/lineage/artifact:${runId}`,
      }),
      schema: lineageResponseSchema,
    },
    {
      fileName: "lineage-batch.json",
      key: "lineage-batch",
      matcher: /^\/api\/v1\/lineage\/batch$/,
      method: "POST",
      mswPath: "*/api/v1/lineage/batch",
      record: ({ runId }) => ({
        body: { lineage_ids: [`artifact:${runId}`] },
        method: "POST",
        path: "/api/v1/lineage/batch",
      }),
      schema: lineageBatchResponseSchema,
    },
    {
      fileName: "temporal-capabilities.json",
      key: "temporal-capabilities",
      matcher: /^\/api\/v1\/temporal\/capabilities$/,
      method: "GET",
      mswPath: "*/api/v1/temporal/capabilities",
      record: ({ runId }) => ({
        method: "GET",
        path: `/api/v1/temporal/capabilities?run_id=${runId}`,
      }),
      schema: temporalCapabilitiesSchema,
    },
    {
      fileName: "compare-run.json",
      key: "compare-run",
      matcher: /^\/api\/v1\/runs\/[^/]+\/compare\/[^/]+$/,
      method: "GET",
      mswPath: "*/api/v1/runs/:runId/compare/:otherRunId",
      record: ({ runId }) => ({
        method: "GET",
        path: `/api/v1/runs/${runId}/compare/${runId}`,
      }),
      schema: compareRunsSchema,
    },
    {
      fileName: "counterfactual-metrics.json",
      key: "counterfactual-metrics",
      matcher: /^\/api\/v1\/runs\/[^/]+\/metrics$/,
      method: "GET",
      mswPath: "*/api/v1/runs/:runId/metrics",
      record: ({ runId }) => ({
        method: "GET",
        path: `/api/v1/runs/${runId}/metrics?scenario_id=scn_fixture_001`,
      }),
      schema: counterfactualMetricsSchema,
    },
    {
      fileName: "fabric-source-scorecards.json",
      key: "fabric-source-scorecards",
      matcher: /^\/api\/v1\/fabric\/source-scorecards$/,
      method: "GET",
      mswPath: "*/api/v1/fabric/source-scorecards",
      record: {
        method: "GET",
        path: "/api/v1/fabric/source-scorecards",
      },
      schema: fabricSourceScorecardsSchema,
    },
    {
      fileName: "fabric-quality-batch.json",
      key: "fabric-quality-batch",
      matcher: /^\/api\/v1\/fabric\/quality\/batch$/,
      method: "POST",
      mswPath: "*/api/v1/fabric/quality/batch",
      record: ({ runId }) => ({
        body: { run_id: runId },
        method: "POST",
        path: "/api/v1/fabric/quality/batch",
      }),
      schema: fabricQualityBatchSchema,
    },
    {
      fileName: "fabric-trust-batch.json",
      key: "fabric-trust-batch",
      matcher: /^\/api\/v1\/fabric\/trust\/batch$/,
      method: "POST",
      mswPath: "*/api/v1/fabric/trust/batch",
      record: ({ runId }) => ({
        body: { run_id: runId },
        method: "POST",
        path: "/api/v1/fabric/trust/batch",
      }),
      schema: fabricTrustBatchSchema,
    },
    {
      fileName: "fabric-replay.json",
      key: "fabric-replay",
      matcher: /^\/api\/v1\/fabric\/runs\/[^/]+\/replay$/,
      method: "GET",
      mswPath: "*/api/v1/fabric/runs/:runId/replay",
      record: ({ runId }) => ({
        method: "GET",
        path: `/api/v1/fabric/runs/${runId}/replay`,
      }),
      schema: fabricReplaySchema,
    },
    {
      fileName: "fabric-impact.json",
      key: "fabric-impact",
      matcher: /^\/api\/v1\/fabric\/impact$/,
      method: "POST",
      mswPath: "*/api/v1/fabric/impact",
      record: ({ runId }) => ({
        body: { run_id: runId, source_contract_ids: ["worldbank.wdi.generic"] },
        method: "POST",
        path: "/api/v1/fabric/impact",
      }),
      schema: fabricImpactAnalysisSchema,
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
