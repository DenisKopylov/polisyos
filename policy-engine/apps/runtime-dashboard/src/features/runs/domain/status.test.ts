import {
  getDecisionQueue,
  groupRunsByStatus,
} from "./status";
import * as runStatus from "./status";

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

  it("preserves raw producer labels and exposes no lifecycle or badge classifier", () => {
    expect(
      groupRunsByStatus([
        { status: "awaiting_external_attestation" },
        { status: "awaiting_external_attestation" },
        { status: " completed_future " },
      ]),
    ).toEqual([
      { status: "awaiting_external_attestation", count: 2 },
      { status: " completed_future ", count: 1 },
    ]);
    expect(Object.keys(runStatus)).not.toEqual(
      expect.arrayContaining([
        "getBlockedRunCount",
        "getRunBadgeKind",
        "isRunFailed",
        "isRunInReview",
        "isRunRunning",
        "isRunSuccess",
        "isRunTerminal",
      ]),
    );
  });

  it("derives the artifact-backed decision queue without inspecting status", () => {
    expect(getDecisionQueue(runs).map((run) => run.run_id)).toEqual([
      "run-2",
      "run-3",
    ]);
  });

  it("groups runs by status", () => {
    expect(groupRunsByStatus(runs)).toEqual([
      { status: "blocked_preflight", count: 1 },
      { status: "completed", count: 1 },
      { status: "running", count: 1 },
    ]);
  });
});
