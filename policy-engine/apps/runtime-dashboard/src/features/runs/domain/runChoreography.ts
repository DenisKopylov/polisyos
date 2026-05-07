import type { RunTimelinePayload, RunWorkflowPayload } from "@/api/validators";

export type RunChoreographyLane = {
  durationMs: number;
  events: RunChoreographyEvent[];
  id: string;
  retries: number;
  status: "blocked" | "complete" | "pending" | "running";
};

export type RunChoreographyEvent = {
  artifactCount: number;
  at: string;
  branch: boolean;
  durationMs: number | null;
  id: string;
  label: string;
  parentSpanId: string | null;
  retry: boolean;
  spanId: string | null;
  status: "blocked" | "complete" | "pending" | "running";
};

export type RunChoreographyView = {
  criticalPathMs: number | null;
  laneOrder: string[];
  lanes: RunChoreographyLane[];
  totalEvents: number;
  totalRetries: number;
};

type TimelineEvent = NonNullable<
  RunTimelinePayload["timeline"]["events"]
>[number];
type WorkflowView = RunWorkflowPayload["workflow"];

function eventStatus(event: TimelineEvent): RunChoreographyEvent["status"] {
  if ((event.error_count ?? 0) > 0) {
    return "blocked";
  }
  if ((event.warning_count ?? 0) > 0) {
    return "running";
  }
  return "complete";
}

function laneStatus(
  events: RunChoreographyEvent[],
): RunChoreographyLane["status"] {
  if (events.some((event) => event.status === "blocked")) {
    return "blocked";
  }
  if (events.some((event) => event.status === "running")) {
    return "running";
  }
  if (events.length === 0) {
    return "pending";
  }
  return "complete";
}

function eventDuration(event: TimelineEvent, workflow?: WorkflowView | null) {
  if (typeof event.metrics?.duration_ms === "number") {
    return event.metrics.duration_ms;
  }
  const matchingNode = workflow?.nodes?.find(
    (node) => node.alias === event.phase || node.alias === event.event,
  );
  return matchingNode?.duration_ms ?? null;
}

function isRetry(event: TimelineEvent) {
  return /retry|attempt|backoff/i.test(`${event.phase} ${event.event}`);
}

export function buildRunChoreographyView(input: {
  timelineEvents?: TimelineEvent[];
  workflow?: WorkflowView | null;
}): RunChoreographyView {
  const events = [...(input.timelineEvents ?? [])].sort(
    (a, b) => a.index - b.index,
  );
  const grouped = new Map<string, RunChoreographyEvent[]>();
  const childCounts = new Map<string, number>();
  for (const event of events) {
    if (event.parent_span_id) {
      childCounts.set(
        event.parent_span_id,
        (childCounts.get(event.parent_span_id) ?? 0) + 1,
      );
    }
  }

  for (const event of events) {
    const laneId = event.phase || "runtime";
    const artifactCount =
      (event.input_artifact_ids?.length ?? 0) +
      (event.output_artifact_ids?.length ?? 0);
    const projected: RunChoreographyEvent = {
      artifactCount,
      at: event.timestamp,
      branch: Boolean(
        event.parent_span_id ||
        (event.span_id && (childCounts.get(event.span_id) ?? 0) > 1),
      ),
      durationMs: eventDuration(event, input.workflow),
      id: `${event.index}:${event.event}`,
      label: event.event,
      parentSpanId: event.parent_span_id ?? null,
      retry: isRetry(event),
      spanId: event.span_id ?? null,
      status: eventStatus(event),
    };
    grouped.set(laneId, [...(grouped.get(laneId) ?? []), projected]);
  }

  const workflowLaneIds =
    input.workflow?.nodes
      ?.map((node) => node.alias)
      .filter((alias, index, aliases) => aliases.indexOf(alias) === index) ??
    [];
  const eventLaneIds = Array.from(grouped.keys());
  const laneOrder = [...workflowLaneIds, ...eventLaneIds].filter(
    (lane, index, lanes) => lanes.indexOf(lane) === index,
  );

  const lanes = laneOrder.map<RunChoreographyLane>((laneId) => {
    const laneEvents = grouped.get(laneId) ?? [];
    return {
      durationMs: laneEvents.reduce(
        (total, event) => total + (event.durationMs ?? 0),
        0,
      ),
      events: laneEvents,
      id: laneId,
      retries: laneEvents.filter((event) => event.retry).length,
      status: laneStatus(laneEvents),
    };
  });

  return {
    criticalPathMs: input.workflow?.summary.critical_path_duration_ms ?? null,
    laneOrder,
    lanes,
    totalEvents: events.length,
    totalRetries: lanes.reduce((total, lane) => total + lane.retries, 0),
  };
}
