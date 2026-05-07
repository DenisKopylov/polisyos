import {
  getBlockedRunCount,
  getDecisionQueue,
  getRunBadgeKind,
  groupRunsByStatus,
  isRunFailed,
  isRunRunning,
  isRunSuccess,
  isRunTerminal,
} from "./status";

describe("run status helpers", () => {
  const runs = [
    {
      run_id: "run-1",
      status: "running",
      root_artifact_count: 0,
      duration_ms: 1_000,
    },
    {
      run_id: "run-2",
      status: "blocked_preflight",
      root_artifact_count: 2,
      duration_ms: 2_000,
    },
    {
      run_id: "run-3",
      status: "completed",
      root_artifact_count: 1,
      duration_ms: 3_000,
    },
  ];

  it("classifies statuses consistently", () => {
    expect(isRunSuccess("completed")).toBe(true);
    expect(isRunFailed("blocked_preflight")).toBe(true);
    expect(isRunRunning("running")).toBe(true);
    expect(isRunTerminal("completed")).toBe(true);
    expect(getRunBadgeKind("blocked_preflight")).toBe("fail");
  });

  it("derives blocked count and decision queue", () => {
    expect(getBlockedRunCount(runs)).toBe(1);
    expect(getDecisionQueue(runs).map((run) => run.run_id)).toEqual([
      "run-2",
      "run-3",
    ]);
  });

  it("groups runs by status", () => {
    expect(groupRunsByStatus(runs)).toEqual([
      { status: "blocked_preflight", count: 1, badgeKind: "fail" },
      { status: "completed", count: 1, badgeKind: "ok" },
      { status: "running", count: 1, badgeKind: "warn" },
    ]);
  });
});
