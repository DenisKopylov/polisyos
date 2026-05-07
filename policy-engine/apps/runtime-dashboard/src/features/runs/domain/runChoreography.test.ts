import { buildRunChoreographyView } from "./runChoreography";

import type { RunTimelinePayload, RunWorkflowPayload } from "@/api/validators";

const timelineEvents = [
  {
    event: "parse input",
    index: 2,
    input_artifact_ids: ["request"],
    output_artifact_ids: ["manifest"],
    parent_span_id: "root",
    phase: "parse",
    span_id: "parse",
    timestamp: "2026-03-09T10:00:02Z",
  },
  {
    error_count: 1,
    event: "execute retry attempt",
    index: 3,
    metrics: { duration_ms: 900 },
    parent_span_id: "root",
    phase: "execute",
    span_id: "execute",
    timestamp: "2026-03-09T10:00:06Z",
    warning_count: 0,
  },
  {
    event: "audit packet",
    index: 4,
    phase: "audit",
    timestamp: "2026-03-09T10:00:08Z",
    warning_count: 1,
  },
  {
    event: "bootstrap",
    index: 1,
    phase: "parse",
    span_id: "root",
    timestamp: "2026-03-09T10:00:01Z",
  },
] satisfies NonNullable<RunTimelinePayload["timeline"]["events"]>;

const workflow = {
  edges: [
    {
      from_alias: "parse",
      to_alias: "execute",
    },
    {
      from_alias: "execute",
      to_alias: "audit",
    },
  ],
  nodes: [
    {
      alias: "parse",
      depth: 0,
      duration_ms: 120,
      status: "ok",
    },
    {
      alias: "execute",
      depth: 1,
      duration_ms: 900,
      status: "fail",
    },
    {
      alias: "audit",
      depth: 2,
      duration_ms: 80,
      status: "unknown",
    },
  ],
  run_id: "run-1",
  source_kind: "core_run",
  summary: {
    critical_path_duration_ms: 1100,
    edge_count: 2,
    fail_count: 1,
    max_depth: 2,
    node_count: 3,
    ok_count: 1,
    skip_count: 0,
  },
} satisfies RunWorkflowPayload["workflow"];

describe("buildRunChoreographyView", () => {
  it("orders lanes from workflow and enriches timeline events", () => {
    const view = buildRunChoreographyView({
      timelineEvents,
      workflow,
    });

    expect(view.laneOrder).toEqual(["parse", "execute", "audit"]);
    expect(view.totalEvents).toBe(4);
    expect(view.criticalPathMs).toBe(1100);
    expect(view.lanes.find((lane) => lane.id === "parse")).toMatchObject({
      durationMs: 240,
      retries: 0,
      status: "complete",
    });
    expect(view.lanes.find((lane) => lane.id === "execute")).toMatchObject({
      durationMs: 900,
      retries: 1,
      status: "blocked",
    });
    expect(
      view.lanes
        .find((lane) => lane.id === "parse")
        ?.events.some((event) => event.branch),
    ).toBe(true);
    expect(view.lanes.find((lane) => lane.id === "audit")).toMatchObject({
      durationMs: 80,
      status: "running",
    });
  });

  it("keeps event-only lanes when no workflow node exists", () => {
    const view = buildRunChoreographyView({
      timelineEvents: [
        {
          event: "transport pulse",
          index: 1,
          phase: "sse",
          timestamp: "2026-03-09T10:00:00Z",
        },
      ],
      workflow: null,
    });

    expect(view.laneOrder).toEqual(["sse"]);
    expect(view.lanes[0]).toMatchObject({
      durationMs: 0,
      id: "sse",
      status: "complete",
    });
  });
});
