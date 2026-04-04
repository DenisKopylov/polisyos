export type AnyRun = {
  status: string | null | undefined;
  duration_ms?: number | null;
  root_artifact_count?: number | null;
  root_artifacts?: Array<unknown> | null;
};
export type RunBadgeKind = "ok" | "fail" | "warn" | "unknown";

function normalizeStatus(status: string | null | undefined) {
  return (status ?? "").trim().toLowerCase();
}

export function isRunSuccess(status: string | null | undefined): boolean {
  const normalized = normalizeStatus(status);
  return (
    normalized === "completed" ||
    normalized === "ok" ||
    normalized === "success"
  );
}

export function isRunFailed(status: string | null | undefined): boolean {
  const normalized = normalizeStatus(status);
  return (
    normalized === "fail" ||
    normalized === "failed" ||
    normalized === "error" ||
    normalized === "rejected" ||
    normalized.includes("blocked") ||
    normalized.includes("preflight")
  );
}

export function isRunRunning(status: string | null | undefined): boolean {
  const normalized = normalizeStatus(status);
  return (
    normalized.includes("running") ||
    normalized.includes("execut") ||
    normalized.includes("evaluat") ||
    normalized.includes("plan") ||
    normalized.includes("pending")
  );
}

export function isRunTerminal(status: string | null | undefined): boolean {
  const normalized = normalizeStatus(status);
  return Boolean(normalized) && !isRunRunning(normalized);
}

export function isRunInReview(status: string | null | undefined): boolean {
  const normalized = normalizeStatus(status);
  return normalized.includes("review") || isRunFailed(normalized);
}

export function getRunBadgeKind(
  status: string | null | undefined,
): RunBadgeKind {
  if (isRunSuccess(status)) {
    return "ok";
  }
  if (isRunFailed(status)) {
    return "fail";
  }
  if (isRunRunning(status)) {
    return "warn";
  }
  if (normalizeStatus(status).length > 0) {
    return "warn";
  }
  return "unknown";
}

export function getBlockedRunCount(runs: AnyRun[]): number {
  return runs.filter((run) => isRunFailed(run.status)).length;
}

export function getDecisionQueue<T extends AnyRun>(runs: T[], limit = 6): T[] {
  return runs
    .filter(
      (run) => (run.root_artifact_count ?? run.root_artifacts?.length ?? 0) > 0,
    )
    .slice(0, limit);
}

export function getAverageRunDuration(runs: AnyRun[]): number | null {
  const values = runs
    .map((run) => run.duration_ms)
    .filter(
      (value): value is number =>
        typeof value === "number" && Number.isFinite(value),
    );
  if (values.length === 0) {
    return null;
  }
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

export function groupRunsByStatus(runs: AnyRun[]) {
  const counts = new Map<string, number>();
  for (const run of runs) {
    const status = normalizeStatus(run.status) || "unknown";
    counts.set(status, (counts.get(status) ?? 0) + 1);
  }
  return Array.from(counts.entries())
    .map(([status, count]) => ({
      status,
      count,
      badgeKind: getRunBadgeKind(status),
    }))
    .sort(
      (left, right) =>
        right.count - left.count || left.status.localeCompare(right.status),
    );
}
