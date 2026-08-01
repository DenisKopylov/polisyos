import {
  initialRunsLiveState,
  parseRunsLiveEvent,
  reduceRunsLiveState,
  shouldInvalidateRunsForEvent,
} from "@/app/providers/runsLiveMachine";

describe("runsLiveMachine", () => {
  it("keeps initial connect in connecting state", () => {
    expect(
      reduceRunsLiveState(initialRunsLiveState, {
        type: "connect",
        retryAttempt: 0,
      }),
    ).toMatchObject({
      retryAttempt: 0,
      status: "connecting",
    });
  });

  it("marks reconnect attempts as degraded until stream opens", () => {
    const degraded = reduceRunsLiveState(initialRunsLiveState, {
      type: "connect",
      retryAttempt: 2,
    });

    expect(degraded.status).toBe("degraded");
    expect(
      reduceRunsLiveState(degraded, {
        type: "stream-open",
      }),
    ).toMatchObject({
      retryAttempt: 0,
      status: "live",
    });
  });

  it("updates cursor and heartbeat timestamp on messages", () => {
    const next = reduceRunsLiveState(initialRunsLiveState, {
      type: "stream-event",
      event: {
        cursor: "cursor-42",
        kind: "runs.snapshot",
      },
      now: 42,
    });

    expect(next).toMatchObject({
      cursor: "cursor-42",
      lastHeartbeatAt: 42,
      status: "live",
    });
  });

  it("falls back to polling after heartbeat timeout", () => {
    const timedOut = reduceRunsLiveState(initialRunsLiveState, {
      type: "heartbeat-timeout",
      now: 500,
    });

    expect(
      reduceRunsLiveState(timedOut, {
        type: "polling-started",
      }),
    ).toMatchObject({
      lastHeartbeatAt: 500,
      status: "polling",
    });
  });

  it("goes offline for chromeless routes", () => {
    expect(
      reduceRunsLiveState(initialRunsLiveState, {
        type: "offline",
      }),
    ).toMatchObject({
      cursor: null,
      retryAttempt: 0,
      status: "offline",
    });
  });

  it("parses heartbeat frames without invalidation", () => {
    const event = parseRunsLiveEvent({
      data: JSON.stringify({ kind: "heartbeat" }),
      lastEventId: "cursor-1",
    });

    expect(event).toEqual({
      cursor: "cursor-1",
      kind: "heartbeat",
    });
    expect(shouldInvalidateRunsForEvent(event)).toBe(false);
  });

  it("parses update frames and invalidates runs", () => {
    const event = parseRunsLiveEvent({
      data: JSON.stringify({
        runs: [{ run_id: "run-1" }],
        type: "snapshot",
      }),
      lastEventId: "cursor-2",
    });

    expect(event).toEqual({
      cursor: "cursor-2",
      entity: "runs",
      event: "snapshot",
      kind: "runs.snapshot",
    });
    expect(shouldInvalidateRunsForEvent(event)).toBe(true);
  });

  it("parses thin SSE envelopes for run status updates", () => {
    const event = parseRunsLiveEvent({
      data: JSON.stringify({
        cursor: "cursor-9",
        entity: "run",
        event: "status.updated",
        id: "run-9",
        status: "waiting_for_human_decision",
        terminal: false,
      }),
      lastEventId: "cursor-8",
    });

    expect(event).toEqual({
      cursor: "cursor-9",
      entity: "run",
      event: "status.updated",
      kind: "run.status",
      runId: "run-9",
      status: "waiting_for_human_decision",
      terminal: false,
    });
  });

  it("does not infer terminal from a novel status when the producer terminal field is absent", () => {
    const event = parseRunsLiveEvent({
      data: JSON.stringify({
        cursor: "cursor-novel",
        event: "status.updated",
        run_id: "run-novel",
        status: "completed_future",
      }),
    });

    expect(event.status).toBe("completed_future");
    expect(event.terminal).toBeUndefined();
  });

  it("preserves an absent producer terminal fact instead of authoring false", () => {
    const event = parseRunsLiveEvent({
      data: JSON.stringify({
        event: "node.updated",
        run_id: "run-no-terminal",
        status: "blocked_by_external_owner",
      }),
    });

    expect(event).not.toHaveProperty("terminal");
  });

  it("treats malformed payloads as unknown events", () => {
    const event = parseRunsLiveEvent({
      data: "{invalid",
      lastEventId: "cursor-3",
    });

    expect(event).toEqual({
      cursor: "cursor-3",
      kind: "unknown",
    });
    expect(shouldInvalidateRunsForEvent(event)).toBe(true);
  });
});
