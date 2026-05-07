import type { LoaderFunctionArgs } from "react-router-dom";

import { instrumentRouteLoader } from "@/app/routes/routeInstrumentation";
import {
  primeEvidenceWorkspace,
  primeRunDetail,
  primeRunTab,
  primeWorkspace,
  type RunTabKey,
} from "@/app/routes/prefetch";
import type { WorkspacePrefetchKey } from "@/app/workspaces";

function requireParam(value: string | undefined, paramName: string) {
  if (!value) {
    throw new Response(`Missing required route param: ${paramName}`, {
      status: 400,
    });
  }
  return value;
}

export function createWorkspaceLoader(
  routeId: string,
  workspacePrefetchKeys: WorkspacePrefetchKey[],
) {
  return async () =>
    instrumentRouteLoader(routeId, () => primeWorkspace(workspacePrefetchKeys));
}

export function createRunDetailLoader(routeId = "runs.detail") {
  return async ({ params }: LoaderFunctionArgs) =>
    instrumentRouteLoader(routeId, async () => {
      const runId = requireParam(params.runId, "runId");
      return primeRunDetail(runId);
    });
}

export function createRunTabLoader(tabKey: RunTabKey) {
  return async ({ params }: LoaderFunctionArgs) =>
    instrumentRouteLoader(`runs.tab.${tabKey}`, async () => {
      const runId = requireParam(params.runId, "runId");
      return primeRunTab(runId, tabKey);
    });
}

export const loadRunDetail = createRunDetailLoader();

export async function loadEvidenceWorkspace({ request }: LoaderFunctionArgs) {
  return instrumentRouteLoader("evidence.fabric", async () =>
    primeEvidenceWorkspace(request.url),
  );
}
