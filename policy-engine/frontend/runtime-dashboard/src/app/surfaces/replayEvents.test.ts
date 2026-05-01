import {
  createReplayEventEnvelope,
  createSurfaceOpenedReplayEvent,
  parseReplayEventEnvelope,
  REPLAY_EVENT_SCHEMA,
} from "./replayEvents";

describe("replay event envelope", () => {
  it("creates deterministic event ids for the same envelope payload", () => {
    const input = {
      kind: "threshold.changed" as const,
      occurredAt: "2026-04-29T09:10:00.000Z",
      payload: { next: 0.8, previous: 0.6 },
      route: {
        fullPath: "/runs/run-1/causal?surface=causal-atlas",
        path: "/runs/run-1/causal",
      },
      sequence: 7,
      surfaceId: "runs.causalAtlas" as const,
    };

    expect(createReplayEventEnvelope(input).eventId).toBe(
      createReplayEventEnvelope(input).eventId,
    );
  });

  it("creates first-class surface opened events", () => {
    const event = createSurfaceOpenedReplayEvent({
      fullPath: "/runs/run-1/workflow?surface=choreography",
      occurredAt: "2026-04-29T09:00:00.000Z",
      path: "/runs/run-1/workflow",
      routeId: "runs.tab.workflow",
      runId: "run-1",
      sequence: 1,
      sessionId: "session-1",
      surfaceId: "runs.runChoreography",
    });

    expect(event).toMatchObject({
      context: { runId: "run-1", sessionId: "session-1" },
      kind: "surface.opened",
      schema: REPLAY_EVENT_SCHEMA,
      surfaceId: "runs.runChoreography",
    });
  });

  it("validates replay envelopes before replay import", () => {
    const event = createSurfaceOpenedReplayEvent({
      fullPath: "/runs/run-1/causal?surface=causal-atlas",
      occurredAt: "2026-04-29T09:05:00.000Z",
      path: "/runs/run-1/causal",
      routeId: "runs.tab.causal",
      runId: "run-1",
      sequence: 2,
      surfaceId: "runs.causalAtlas",
    });

    expect(parseReplayEventEnvelope(event)).toEqual(event);
    expect(
      parseReplayEventEnvelope({
        ...event,
        surfaceId: "runs.unknown",
      }),
    ).toBeNull();
    expect(
      parseReplayEventEnvelope({
        ...event,
        schema: "legacy.replay_event",
      }),
    ).toBeNull();
  });

  it("keeps stable ids across object key ordering", () => {
    const first = createReplayEventEnvelope({
      kind: "threshold.changed",
      occurredAt: "2026-04-29T09:10:00.000Z",
      payload: { next: 0.8, previous: 0.6 },
      route: {
        fullPath: "/runs/run-1/causal?surface=causal-atlas",
        path: "/runs/run-1/causal",
      },
      sequence: 7,
      surfaceId: "runs.causalAtlas",
    });
    const second = createReplayEventEnvelope({
      kind: "threshold.changed",
      occurredAt: "2026-04-29T09:10:00.000Z",
      payload: { previous: 0.6, next: 0.8 },
      route: {
        path: "/runs/run-1/causal",
        fullPath: "/runs/run-1/causal?surface=causal-atlas",
      },
      sequence: 7,
      surfaceId: "runs.causalAtlas",
    });

    expect(first.eventId).toBe(second.eventId);
  });

  it("accepts operator craft audit events as replayable envelopes", () => {
    const annotation = createReplayEventEnvelope({
      kind: "annotation.created",
      occurredAt: "2026-04-29T09:15:00.000Z",
      payload: {
        annotationId: "annotation-1",
        packetHash: "pub:abc",
        targetRef: "claim:run-1",
      },
      route: {
        fullPath: "/runs/run-1/overview?surface=annotation-surface",
        path: "/runs/run-1/overview",
      },
      sequence: 3,
      surfaceId: "runs.annotationSurface",
    });

    expect(parseReplayEventEnvelope(annotation)).toEqual(annotation);
  });
});
