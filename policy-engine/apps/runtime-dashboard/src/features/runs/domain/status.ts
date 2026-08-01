export type AnyRun = {
  status: string | null | undefined;
  duration_ms?: number | null;
  root_artifact_count?: number | null;
  root_artifacts?: Array<unknown> | null;
};

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
    if (typeof run.status !== "string") {
      continue;
    }
    const status = run.status;
    counts.set(status, (counts.get(status) ?? 0) + 1);
  }
  return Array.from(counts.entries())
    .map(([status, count]) => ({ status, count }))
    .sort(
      (left, right) =>
        right.count - left.count || left.status.localeCompare(right.status),
    );
}
