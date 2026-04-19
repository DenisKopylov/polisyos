import { governanceDebugQueryOptions } from "@/api/hooks/useGovernanceDebug";
import { runAgentsQueryOptions } from "@/api/hooks/useRunAgents";
import { runDetailsQueryOptions } from "@/api/hooks/useRunDetails";
import { runErrorsQueryOptions } from "@/api/hooks/useRunErrors";
import { runEvidenceContextQueryOptions } from "@/api/hooks/useRunEvidenceContext";
import { runLineageQueryOptions } from "@/api/hooks/useRunLineage";
import { runNodesQueryOptions } from "@/api/hooks/useRunNodes";
import { runTimelineQueryOptions } from "@/api/hooks/useRunTimeline";
import { runWorkflowQueryOptions } from "@/api/hooks/useRunWorkflow";
import { isRuntimeApiNotFound } from "@/api/http";
import { queryClient } from "@/api/queryClient";
import { resolveRoutePrefetchEntry } from "@/app/routes/routeManifest";
import {
  buildBootstrapQueryOptions,
  type WorkspacePrefetchKey,
} from "@/app/workspaces";
import { parseEvidenceSearchParams } from "@/features/evidence";
import type { RunDetailTab } from "@/features/runs/domain/runDetailTabs";

export type RunTabKey = RunDetailTab;
type RunTabQueryOptions =
  | ReturnType<typeof governanceDebugQueryOptions>
  | ReturnType<typeof runAgentsQueryOptions>
  | ReturnType<typeof runDetailsQueryOptions>
  | ReturnType<typeof runErrorsQueryOptions>
  | ReturnType<typeof runEvidenceContextQueryOptions>
  | ReturnType<typeof runLineageQueryOptions>
  | ReturnType<typeof runNodesQueryOptions>
  | ReturnType<typeof runTimelineQueryOptions>
  | ReturnType<typeof runWorkflowQueryOptions>;

const RUN_DETAIL_BOOTSTRAP_ATTEMPTS = 8;

function ensureQueryData(
  options: RunTabQueryOptions | ReturnType<typeof buildBootstrapQueryOptions>,
) {
  return queryClient.ensureQueryData(options as never);
}

function sleep(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function createRunTabQueries(
  runId: string,
): Record<RunTabKey, RunTabQueryOptions[]> {
  return {
    agents: [runAgentsQueryOptions(runId)],
    artifacts: [],
    causal: [],
    debug: [
      runErrorsQueryOptions(runId),
      runNodesQueryOptions(runId),
      runTimelineQueryOptions(runId),
    ],
    evidence: [runEvidenceContextQueryOptions(runId)],
    governance: [governanceDebugQueryOptions(runId)],
    overview: [
      runAgentsQueryOptions(runId),
      governanceDebugQueryOptions(runId),
      runEvidenceContextQueryOptions(runId),
      runTimelineQueryOptions(runId),
    ],
    workflow: [runWorkflowQueryOptions(runId), runLineageQueryOptions(runId)],
  };
}

function resolveUrl(input: string | URL) {
  if (input instanceof URL) {
    return input;
  }

  const base =
    typeof window === "undefined"
      ? "http://localhost"
      : window.location.origin || "http://localhost";
  return new URL(input, base);
}

export async function primeWorkspace(
  workspacePrefetchKeys: WorkspacePrefetchKey[],
) {
  const queries = workspacePrefetchKeys.map((key) =>
    buildBootstrapQueryOptions(key),
  );
  await Promise.all(queries.map((options) => ensureQueryData(options)));
  return null;
}

export async function ensureRunDetailReady(runId: string) {
  for (let attempt = 0; attempt < RUN_DETAIL_BOOTSTRAP_ATTEMPTS; attempt += 1) {
    try {
      await ensureQueryData(runDetailsQueryOptions(runId));
      return true;
    } catch (error) {
      const isBootstrap404 = isRuntimeApiNotFound(error);
      if (!isBootstrap404 || attempt === RUN_DETAIL_BOOTSTRAP_ATTEMPTS - 1) {
        if (!isBootstrap404) {
          throw error instanceof Error ? error : new Error(String(error));
        }
        return false;
      }
      await sleep(Math.min(300 * 2 ** attempt, 2_000));
    }
  }

  return false;
}

export async function primeRunDetail(runId: string) {
  const [, runBootstrapPending] = await Promise.all([
    ensureQueryData(buildBootstrapQueryOptions("capabilities")),
    ensureRunDetailReady(runId).then((ready) => !ready),
  ]);

  return { runBootstrapPending, runId };
}

export async function primeRunTab(runId: string, tabKey: RunTabKey) {
  const runReady = await ensureRunDetailReady(runId);
  const tabQueries = createRunTabQueries(runId);

  if (runReady) {
    await Promise.all(
      tabQueries[tabKey].map((options) => ensureQueryData(options)),
    );
  }

  return { runBootstrapPending: !runReady, runId, tabKey };
}

export async function primeEvidenceWorkspace(urlLike: string | URL) {
  const workspacePrefetchKeys =
    resolveRoutePrefetchEntry("/evidence")?.entry.handle.prefetch ?? [];
  await primeWorkspace(workspacePrefetchKeys);
  const search = parseEvidenceSearchParams(resolveUrl(urlLike));
  if (search.runId) {
    await ensureQueryData(runEvidenceContextQueryOptions(search.runId));
  }
  return search;
}

export async function prefetchRouteHref(href: string) {
  const url = resolveUrl(href);
  const resolved = resolveRoutePrefetchEntry(url.pathname);

  if (!resolved) {
    return;
  }

  if (resolved.entry.kind === "workspace") {
    if (resolved.entry.handle.prefetch?.length) {
      await primeWorkspace(resolved.entry.handle.prefetch);
    }
    return;
  }

  if (resolved.entry.kind === "evidence") {
    await primeEvidenceWorkspace(url);
    return;
  }

  if (resolved.entry.kind === "runReport" && resolved.params.runId) {
    await primeRunDetail(resolved.params.runId);
    return;
  }

  if (resolved.entry.kind === "runDeck" && resolved.params.runId) {
    await primeRunDetail(resolved.params.runId);
    return;
  }

  if (
    resolved.entry.kind === "runTab" &&
    resolved.params.runId &&
    resolved.params.tab
  ) {
    const tabKey = resolved.params.tab as RunTabKey;
    await Promise.all([
      primeRunDetail(resolved.params.runId),
      primeRunTab(resolved.params.runId, tabKey),
    ]);
  }
}
