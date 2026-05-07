import type { QueryClient } from "@tanstack/react-query";

import {
  isRunFailed,
  isRunRunning,
  isRunSuccess,
} from "@/features/runs/domain/status";
import { queryKeys } from "@/api/queryKeys";
import type { PromotionCandidatesResponse } from "@/api/hooks/useDataPromotionCandidates";
import type { IndexStatsResponse } from "@/api/hooks/useDataIndexStats";
import type { RunsFilters } from "@/api/hooks/useRuns";
import type { components } from "@/api/types";

export type RunSummary = components["schemas"]["RunSummary"];
export type RunDetailsResponse = {
  meta: components["schemas"]["ApiMeta"];
  run: components["schemas"]["RunDetails"];
};
export type RunEvidenceContextResponse = {
  context: components["schemas"]["RunEvidenceContextView"];
  meta: components["schemas"]["ApiMeta"];
};
export type RunsQueryData = {
  meta: components["schemas"]["ApiMeta"];
  page: components["schemas"]["CursorPage"];
  runs: RunSummary[];
};
export type RunsQuerySnapshot = Array<
  readonly [readonly unknown[], RunsQueryData | undefined]
>;

function normalizeStatus(status: string | null | undefined) {
  return (status ?? "").trim().toLowerCase();
}

function createOptimisticMeta(runId: string): components["schemas"]["ApiMeta"] {
  return {
    request_id: `optimistic-${runId}`,
    generated_at: new Date().toISOString(),
    source_kinds: ["core_run"],
  };
}

function matchesRunFilters(run: RunSummary, filters: RunsFilters | undefined) {
  if (!filters) {
    return true;
  }
  if (filters.status) {
    const normalizedFilter = normalizeStatus(filters.status);
    const matchesStatus =
      normalizedFilter === "running"
        ? isRunRunning(run.status)
        : normalizedFilter === "completed"
          ? isRunSuccess(run.status)
          : normalizedFilter === "fail"
            ? isRunFailed(run.status)
            : normalizeStatus(run.status).includes(normalizedFilter);
    if (!matchesStatus) {
      return false;
    }
  }

  const startedAt = run.started_at ? new Date(run.started_at).getTime() : NaN;
  if (
    filters.from_ts &&
    Number.isFinite(startedAt) &&
    startedAt < new Date(filters.from_ts).getTime()
  ) {
    return false;
  }
  if (
    filters.to_ts &&
    Number.isFinite(startedAt) &&
    startedAt > new Date(filters.to_ts).getTime()
  ) {
    return false;
  }
  return true;
}

function upsertRun(
  data: RunsQueryData,
  run: RunSummary,
  options?: { replaceId?: string; incrementTotal?: boolean },
) {
  const replaceId = options?.replaceId;
  const incrementTotal = options?.incrementTotal ?? false;
  const existingIds = new Set<string>([run.run_id]);
  if (replaceId) {
    existingIds.add(replaceId);
  }
  const nextRuns = [
    run,
    ...data.runs.filter((item) => !existingIds.has(item.run_id)),
  ];
  const limit = data.page.limit ?? nextRuns.length;
  const replacedExisting = data.runs.some(
    (item) => item.run_id === replaceId || item.run_id === run.run_id,
  );

  return {
    ...data,
    page: {
      ...data.page,
      count: Math.min(nextRuns.length, limit),
      total:
        data.page.total == null
          ? data.page.total
          : data.page.total + (incrementTotal && !replacedExisting ? 1 : 0),
    },
    runs: nextRuns.slice(0, limit),
  };
}

export function createOptimisticRun(tempId: string): RunSummary {
  return {
    run_id: tempId,
    source_kind: "core_run",
    status: "running",
    started_at: new Date().toISOString(),
    finished_at: null,
    duration_ms: 0,
    tenant_id: null,
    has_trace: false,
    root_artifact_count: 0,
    has_workflow_report: false,
    warnings: [],
    control_job_id: null,
    decision_review_required: false,
    execution_profile: null,
    cell_id: null,
  };
}

export function buildLaunchedRunSummary(
  response: components["schemas"]["RunLaunchResponse"],
  fallbackStartedAt: string,
): RunSummary {
  return {
    run_id: response.run_id,
    source_kind: "core_run",
    status: response.status === "accepted" ? "running" : "rejected",
    started_at: fallbackStartedAt,
    finished_at:
      response.status === "accepted" ? null : new Date().toISOString(),
    duration_ms: 0,
    tenant_id: null,
    has_trace: false,
    root_artifact_count: 0,
    has_workflow_report: false,
    warnings: [],
    control_job_id: response.job_id,
    decision_review_required: false,
    execution_profile: response.effective_execution_profile,
    cell_id: null,
  };
}

export function createOptimisticRunDetails(
  run: RunSummary,
): RunDetailsResponse {
  return {
    meta: createOptimisticMeta(run.run_id),
    run: {
      ...run,
      manifest_ref: null,
      trace_ref: null,
      workflow_report_ref: null,
      root_artifacts: [],
      warnings: [],
    },
  };
}

export function snapshotRunsQueries(
  queryClient: QueryClient,
): RunsQuerySnapshot {
  return queryClient.getQueriesData<RunsQueryData>({
    queryKey: queryKeys.runsRoot(),
  });
}

export function restoreRunsQueries(
  queryClient: QueryClient,
  snapshot: RunsQuerySnapshot,
) {
  for (const [key, value] of snapshot) {
    queryClient.setQueryData(key, value);
  }
}

export function applyOptimisticRunToCache(
  queryClient: QueryClient,
  run: RunSummary,
) {
  for (const [key, current] of snapshotRunsQueries(queryClient)) {
    if (!current) {
      continue;
    }
    const filters = key[2] as RunsFilters | undefined;
    if (!matchesRunFilters(run, filters)) {
      continue;
    }
    queryClient.setQueryData<RunsQueryData>(
      key,
      upsertRun(current, run, { incrementTotal: true }),
    );
  }
  queryClient.setQueryData(
    queryKeys.run(run.run_id),
    createOptimisticRunDetails(run),
  );
}

export function replaceOptimisticRunInCache(
  queryClient: QueryClient,
  tempId: string,
  run: RunSummary,
) {
  for (const [key, current] of snapshotRunsQueries(queryClient)) {
    if (!current) {
      continue;
    }
    const filters = key[2] as RunsFilters | undefined;
    const containsTempRun = current.runs.some((item) => item.run_id === tempId);
    if (!containsTempRun && !matchesRunFilters(run, filters)) {
      continue;
    }
    queryClient.setQueryData<RunsQueryData>(
      key,
      upsertRun(current, run, { replaceId: tempId }),
    );
  }
  queryClient.removeQueries({ queryKey: queryKeys.run(tempId), exact: true });
  queryClient.setQueryData(
    queryKeys.run(run.run_id),
    createOptimisticRunDetails(run),
  );
}

export function updatePromotionCandidateStatus(
  queryClient: QueryClient,
  promotionId: string,
  status: components["schemas"]["PromotionDecisionResponse"]["status"],
) {
  queryClient.setQueryData<PromotionCandidatesResponse | undefined>(
    queryKeys.dataPromotionCandidates(),
    (current) => {
      if (!current) {
        return current;
      }
      return {
        ...current,
        candidates: (current.candidates ?? []).map((candidate) =>
          candidate.promotion_id === promotionId
            ? { ...candidate, status }
            : candidate,
        ),
      };
    },
  );
}

export function updateRunEvidencePromotionStatus(
  queryClient: QueryClient,
  runId: string,
  promotionId: string,
  status: components["schemas"]["PromotionDecisionResponse"]["status"],
) {
  queryClient.setQueryData<RunEvidenceContextResponse | undefined>(
    queryKeys.runEvidenceContext(runId),
    (current) => {
      if (!current) {
        return current;
      }
      return {
        ...current,
        context: {
          ...current.context,
          promotion_candidates: (
            current.context.promotion_candidates ?? []
          ).map((candidate) =>
            candidate.promotion_id === promotionId
              ? { ...candidate, status }
              : candidate,
          ),
        },
      };
    },
  );
}

export function updateIndexStatsAfterPromotion(queryClient: QueryClient) {
  queryClient.setQueryData<IndexStatsResponse | undefined>(
    queryKeys.dataIndexStats(),
    (current) => {
      if (!current) {
        return current;
      }
      return {
        ...current,
        stats: {
          ...current.stats,
          docs_added_last_run: (current.stats.docs_added_last_run ?? 0) + 1,
          last_updated: new Date().toISOString(),
        },
      };
    },
  );
}
