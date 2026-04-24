import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { expect, type Page, type Request, type Route } from "@playwright/test";
import {
  loadRuntimeContractFixture,
  matchRuntimeContractFixture,
} from "../../src/test/contracts/runtimeContractFixtures";

const currentDir = path.dirname(fileURLToPath(import.meta.url));
const dashboardRoot = path.resolve(currentDir, "../..");
const fixtureMetadataPath = path.resolve(
  dashboardRoot,
  ".tmp/fixture-runtime.json",
);

const LIVE_STORAGE_KEY = "polisyos.runtime.disableLive";
const THEME_STORAGE_KEY = "polisyos.runtime.theme";
const ROUTE_PATTERN = "**/api/v1/**";
const DEFAULT_TIMEOUT = 30_000;

let cachedFixtureMetadata: RuntimeFixtureMetadata | null = null;

export type RuntimeFixtureMetadata = {
  core_run_id: string;
  core_run_id_secondary: string;
  data_snapshot_artifact_id: string;
  promotion_candidate_id: string;
  root_artifact_id: string;
  [key: string]: string;
};

export type RuntimeApiScenario =
  | "ok"
  | "empty"
  | "401"
  | "5xx"
  | "network-fail";

type SurfaceReadyKey =
  | "login"
  | "dashboard"
  | "composer"
  | "runs-list"
  | "run-compare"
  | "run-report"
  | "run-overview"
  | "run-governance"
  | "run-evidence"
  | "run-workflow"
  | "run-artifacts"
  | "run-agents"
  | "run-debug"
  | "artifact"
  | "evidence"
  | "knowledge"
  | "platform";

type RuntimeApiOverride = {
  body?:
    | unknown
    | ((_input: {
        metadata: RuntimeFixtureMetadata;
        payload: unknown;
        request: Request;
        url: URL;
      }) => Promise<unknown> | unknown);
  headers?: Record<string, string>;
  matcher: RegExp | string;
  method?: string;
  status?: number;
};

export type DashboardRouteSurface = {
  name: string;
  path: (_metadata: RuntimeFixtureMetadata) => string;
  ready: SurfaceReadyKey;
};

const SURFACE_TEST_IDS: Record<SurfaceReadyKey, string[]> = {
  login: ["login-page"],
  dashboard: ["dashboard-page"],
  composer: ["composer-page"],
  "runs-list": ["runs-list-page"],
  "run-compare": ["run-compare-page"],
  "run-report": ["run-report-page"],
  "run-overview": ["run-detail-page", "run-tab-overview"],
  "run-governance": ["run-detail-page", "run-tab-governance"],
  "run-evidence": ["run-detail-page", "run-tab-evidence"],
  "run-workflow": ["run-detail-page", "run-tab-workflow"],
  "run-artifacts": ["run-detail-page", "run-tab-artifacts"],
  "run-agents": ["run-detail-page", "run-tab-agents"],
  "run-debug": ["run-detail-page", "run-tab-debug"],
  artifact: ["artifact-page"],
  evidence: ["evidence-page"],
  knowledge: ["lex-page"],
  platform: ["platform-page"],
};

export const DASHBOARD_ROUTE_SURFACES: DashboardRouteSurface[] = [
  {
    name: "login",
    path: () => "/login",
    ready: "login",
  },
  {
    name: "dashboard",
    path: () => "/",
    ready: "dashboard",
  },
  {
    name: "composer",
    path: () => "/compose",
    ready: "composer",
  },
  {
    name: "runs-list",
    path: () => "/runs",
    ready: "runs-list",
  },
  {
    name: "run-compare",
    path: (metadata) =>
      `/runs/compare?base=${metadata.core_run_id}&target=${metadata.core_run_id_secondary}`,
    ready: "run-compare",
  },
  {
    name: "run-report",
    path: (metadata) => `/runs/${metadata.core_run_id}/report`,
    ready: "run-report",
  },
  {
    name: "run-overview",
    path: (metadata) => `/runs/${metadata.core_run_id}/overview`,
    ready: "run-overview",
  },
  {
    name: "run-governance",
    path: (metadata) => `/runs/${metadata.core_run_id}/governance`,
    ready: "run-governance",
  },
  {
    name: "run-evidence",
    path: (metadata) => `/runs/${metadata.core_run_id}/evidence`,
    ready: "run-evidence",
  },
  {
    name: "run-workflow",
    path: (metadata) => `/runs/${metadata.core_run_id}/workflow`,
    ready: "run-workflow",
  },
  {
    name: "run-artifacts",
    path: (metadata) => `/runs/${metadata.core_run_id}/artifacts`,
    ready: "run-artifacts",
  },
  {
    name: "run-agents",
    path: (metadata) => `/runs/${metadata.core_run_id}/agents`,
    ready: "run-agents",
  },
  {
    name: "run-debug",
    path: (metadata) => `/runs/${metadata.core_run_id}/debug`,
    ready: "run-debug",
  },
  {
    name: "artifact",
    path: (metadata) => `/artifacts/${metadata.root_artifact_id}`,
    ready: "artifact",
  },
  {
    name: "evidence",
    path: (metadata) =>
      `/evidence?runId=${metadata.core_run_id}&focus=promotion&promotionId=${metadata.promotion_candidate_id}`,
    ready: "evidence",
  },
  {
    name: "knowledge",
    path: () => "/knowledge",
    ready: "knowledge",
  },
  {
    name: "platform",
    path: () => "/platform",
    ready: "platform",
  },
];

export function readFixtureMetadata() {
  if (!cachedFixtureMetadata) {
    cachedFixtureMetadata = JSON.parse(
      fs.readFileSync(fixtureMetadataPath, "utf-8"),
    ) as RuntimeFixtureMetadata;
  }
  return cachedFixtureMetadata;
}

export async function installDashboardTestState(
  page: Page,
  options?: { theme?: "dark" | "light" },
) {
  await page.addInitScript(
    ({ liveStorageKey, testTheme, themeStorageKey }) => {
      window.localStorage.setItem(liveStorageKey, "true");
      if (testTheme) {
        window.localStorage.setItem(themeStorageKey, testTheme);
      }
      (
        window as Window & {
          __RUNTIME_DASHBOARD_TEST__?: boolean;
        }
      ).__RUNTIME_DASHBOARD_TEST__ = true;
    },
    {
      liveStorageKey: LIVE_STORAGE_KEY,
      testTheme: options?.theme ?? null,
      themeStorageKey: THEME_STORAGE_KEY,
    },
  );
}

export async function waitForDashboardSurface(
  page: Page,
  surface: SurfaceReadyKey,
) {
  await page.waitForLoadState("domcontentloaded");
  for (const testId of SURFACE_TEST_IDS[surface]) {
    await expect(page.getByTestId(testId)).toBeVisible({
      timeout: DEFAULT_TIMEOUT,
    });
  }
}

export async function applyRuntimeApiScenario(
  page: Page,
  scenario: RuntimeApiScenario,
  overrides: RuntimeApiOverride[] = [],
) {
  const metadata = readFixtureMetadata();

  await page.route(ROUTE_PATTERN, async (route, request) => {
    try {
      const url = new URL(request.url());
      const override = overrides.find((candidate) =>
        runtimeApiOverrideMatches(candidate, request, url),
      );
      const contractFixtureDefinition = matchRuntimeContractFixture(
        request.method(),
        url.pathname,
      );
      const contractFixture = contractFixtureDefinition
        ? loadRuntimeContractFixture(contractFixtureDefinition)
        : null;

      if (scenario === "network-fail") {
        await route.abort("failed");
        return;
      }

      if (scenario === "401" || scenario === "5xx") {
        await fulfillRuntimeProblem(
          route,
          scenario === "401" ? 401 : 503,
          url,
          override,
        );
        return;
      }

      if (
        scenario === "empty" &&
        request.method() !== "GET" &&
        !override &&
        !contractFixture
      ) {
        await route.continue();
        return;
      }

      const upstreamResponse = contractFixture ? null : await route.fetch();
      const upstreamResponseBody = upstreamResponse
        ? await upstreamResponse.text()
        : "";
      const upstreamPayload = contractFixture
        ? contractFixture.payload
        : readJsonPayload(
            upstreamResponseBody,
            upstreamResponse?.headers()["content-type"],
          );

      let nextPayload =
        scenario === "empty"
          ? buildEmptyRuntimePayload(url, upstreamPayload)
          : upstreamPayload;

      if (override) {
        nextPayload = await resolveOverridePayload({
          metadata,
          override,
          payload: nextPayload,
          request,
          url,
        });
      }

      await route.fulfill({
        body:
          nextPayload === null || typeof nextPayload === "undefined"
            ? upstreamResponseBody
            : JSON.stringify(nextPayload),
        headers: {
          ...(upstreamResponse?.headers() ?? {}),
          "access-control-allow-origin": "*",
          "content-type": "application/json",
          ...override?.headers,
        },
        status: override?.status ?? upstreamResponse?.status() ?? 200,
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      if (
        message.includes("Target page, context or browser has been closed") ||
        message.includes("Response has been disposed")
      ) {
        return;
      }
      throw error;
    }
  });
}

export async function clearRuntimeApiScenarios(page: Page) {
  await page.unroute(ROUTE_PATTERN);
}

function runtimeApiOverrideMatches(
  override: RuntimeApiOverride,
  request: Request,
  url: URL,
) {
  if (
    override.method &&
    override.method.toUpperCase() !== request.method().toUpperCase()
  ) {
    return false;
  }

  if (typeof override.matcher === "string") {
    return url.pathname === override.matcher;
  }

  return override.matcher.test(url.pathname);
}

async function resolveOverridePayload(input: {
  metadata: RuntimeFixtureMetadata;
  override: RuntimeApiOverride;
  payload: unknown;
  request: Request;
  url: URL;
}) {
  if (typeof input.override.body === "function") {
    return input.override.body({
      metadata: input.metadata,
      payload: input.payload,
      request: input.request,
      url: input.url,
    });
  }

  if (typeof input.override.body !== "undefined") {
    return input.override.body;
  }

  return input.payload;
}

async function fulfillRuntimeProblem(
  route: Route,
  status: number,
  url: URL,
  override?: RuntimeApiOverride,
) {
  const code = status === 401 ? "runtime_unauthorized" : "runtime_unavailable";
  const detail =
    status === 401
      ? "Runtime API rejected the request"
      : "Runtime API is temporarily unavailable";

  await route.fulfill({
    body: JSON.stringify({
      code,
      detail,
      request_id: `playwright-${status}`,
      status,
      title: status === 401 ? "Unauthorized" : "Service Unavailable",
      type: "about:blank",
    }),
    headers: {
      "access-control-allow-origin": "*",
      "content-type": "application/json",
      "x-playwright-scenario": String(status),
      ...override?.headers,
    },
    status: override?.status ?? status,
  });
}

function readJsonPayload(
  responseBody: string,
  contentType: string | undefined,
): unknown {
  const normalizedContentType = contentType ?? "";

  if (!normalizedContentType.includes("application/json")) {
    return null;
  }

  try {
    return JSON.parse(responseBody) as unknown;
  } catch {
    return null;
  }
}

function buildEmptyRuntimePayload(url: URL, payload: unknown) {
  if (!payload || typeof payload !== "object") {
    return payload;
  }

  const record = structuredClone(payload as Record<string, unknown>);
  const pathname = url.pathname;

  if (pathname === "/api/v1/runs") {
    return {
      ...record,
      page: {
        ...(asRecord(record.page) ?? {}),
        count: 0,
        cursor: null,
        next_cursor: null,
        total: 0,
      },
      runs: [],
    };
  }

  if (pathname === "/api/v1/control/data/connectors") {
    return {
      ...record,
      connectors: [],
    };
  }

  if (pathname === "/api/v1/control/data/profiles") {
    return {
      ...record,
      profiles: [],
    };
  }

  if (pathname === "/api/v1/control/data/index/stats") {
    const stats = asRecord(record.stats);
    return {
      ...record,
      stats: stats ? zeroNumericFields(stats) : {},
    };
  }

  if (pathname === "/api/v1/control/data/promotion/candidates") {
    return {
      ...record,
      candidates: [],
    };
  }

  if (pathname === "/api/v1/control/lex/graph/stats") {
    return {
      ...record,
      db_exists: false,
      top_entity_types: [],
      top_predicates: [],
      total_entities: 0,
      total_facts: 0,
      total_provisions: 0,
    };
  }

  if (pathname.endsWith("/evidence-context")) {
    const context = asRecord(record.context) ?? {};
    return {
      ...record,
      context: {
        ...context,
        data_needs: [],
        data_snapshot_ref: null,
        evidence_bundle_ref: null,
        execution_plan_ref: null,
        fetch_plans: [],
        input_bindings_ref: null,
        promotion_candidates: [],
        related_artifacts: [],
        warnings: [],
      },
    };
  }

  if (pathname.endsWith("/timeline")) {
    const timeline = asRecord(record.timeline) ?? {};
    const summary = asRecord(timeline.summary);
    return {
      ...record,
      timeline: {
        ...timeline,
        events: [],
        notes: [],
        summary: summary ? zeroNumericFields(summary) : {},
      },
    };
  }

  if (pathname.endsWith("/lineage")) {
    const lineage = asRecord(record.lineage) ?? {};
    return {
      ...record,
      lineage: {
        ...lineage,
        corrupted_artifact_ids: [],
        edges: [],
        missing_artifact_ids: [],
        nodes: [],
        root_artifact_ids: [],
        total_edges: 0,
        total_nodes: 0,
        total_size_bytes: 0,
      },
    };
  }

  return record;
}

function zeroNumericFields(record: Record<string, unknown>) {
  return Object.fromEntries(
    Object.entries(record).map(([key, value]) => [
      key,
      typeof value === "number" ? 0 : value,
    ]),
  );
}

function asRecord(value: unknown) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }

  return value as Record<string, unknown>;
}
