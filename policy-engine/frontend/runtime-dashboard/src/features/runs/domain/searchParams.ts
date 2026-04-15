import { z } from "zod";

import {
  buildSearchHref,
  parseSearchParamsWithSchema,
} from "@/lib/searchParams";

import type { RunDetailTab } from "@/features/runs/domain/runDetailTabs";

const runsListSearchSchema = z.object({
  cursor: z.string().trim().min(1).optional().catch(undefined),
  from: z.string().trim().min(1).optional().catch(undefined),
  q: z.string().trim().min(1).optional().catch(undefined),
  status: z.string().trim().min(1).optional().catch(undefined),
  to: z.string().trim().min(1).optional().catch(undefined),
});

const runCompareSearchSchema = z.object({
  base: z.string().trim().min(1).optional().catch(undefined),
  target: z.string().trim().min(1).optional().catch(undefined),
});

const runDetailLegacySearchSchema = z.object({
  tab: z.string().trim().min(1).optional().catch(undefined),
});

export type RunsListSearchParams = z.infer<typeof runsListSearchSchema>;
export type RunCompareSearchParams = z.infer<typeof runCompareSearchSchema>;
export type RunDetailLegacySearchParams = z.infer<
  typeof runDetailLegacySearchSchema
>;

export function parseRunsListSearchParams(
  input: string | URLSearchParams | URL,
) {
  return parseSearchParamsWithSchema(runsListSearchSchema, input);
}

export function buildRunsListHref(search?: Partial<RunsListSearchParams>) {
  return buildSearchHref("/runs", {
    cursor: search?.cursor,
    from: search?.from,
    q: search?.q,
    status: search?.status,
    to: search?.to,
  });
}

export function parseRunCompareSearchParams(
  input: string | URLSearchParams | URL,
) {
  return parseSearchParamsWithSchema(runCompareSearchSchema, input);
}

export function buildRunCompareHref(search?: Partial<RunCompareSearchParams>) {
  return buildSearchHref("/runs/compare", {
    base: search?.base,
    target: search?.target,
  });
}

export function parseRunDetailLegacySearchParams(
  input: string | URLSearchParams | URL,
) {
  return parseSearchParamsWithSchema(runDetailLegacySearchSchema, input);
}

export function buildRunDetailHref(
  runId: string,
  tab: RunDetailTab = "overview",
) {
  return `/runs/${runId}/${tab}`;
}

export function buildRunReportHref(runId: string) {
  return `/runs/${runId}/report`;
}
