export type RunsLiveStatus =
  | "live"
  | "connecting"
  | "degraded"
  | "polling"
  | "offline";

export type RunsLiveStreamEvent = {
  cursor: string | null;
  entity?: string | null;
  event?: string | null;
  kind:
    | "governance.waiting"
    | "heartbeat"
    | "run.node"
    | "run.snapshot"
    | "run.status"
    | "runs.snapshot"
    | "unknown";
  runId?: string | null;
  status?: string | null;
  terminal?: boolean;
};

export type RunsLiveState = {
  cursor: string | null;
  lastHeartbeatAt: number | null;
  retryAttempt: number;
  status: RunsLiveStatus;
};

export type RunsLiveAction =
  | { type: "offline" }
  | { type: "connect"; retryAttempt: number }
  | { type: "stream-open" }
  | { type: "stream-event"; event: RunsLiveStreamEvent; now: number }
  | { type: "stream-error"; retryAttempt: number }
  | { type: "heartbeat-timeout"; now: number }
  | { type: "polling-started" };

export const initialRunsLiveState: RunsLiveState = {
  cursor: null,
  lastHeartbeatAt: null,
  retryAttempt: 0,
  status: "connecting",
};

function withProducerTerminal(
  event: RunsLiveStreamEvent,
  terminal: unknown,
): RunsLiveStreamEvent {
  return typeof terminal === "boolean" ? { ...event, terminal } : event;
}

export function reduceRunsLiveState(
  state: RunsLiveState,
  action: RunsLiveAction,
): RunsLiveState {
  switch (action.type) {
    case "offline":
      return {
        ...initialRunsLiveState,
        status: "offline",
      };
    case "connect":
      return {
        ...state,
        retryAttempt: action.retryAttempt,
        status: action.retryAttempt === 0 ? "connecting" : "degraded",
      };
    case "stream-open":
      return {
        ...state,
        retryAttempt: 0,
        status: "live",
      };
    case "stream-event":
      return {
        ...state,
        cursor: action.event.cursor ?? state.cursor,
        lastHeartbeatAt: action.now,
        status: "live",
      };
    case "stream-error":
      return {
        ...state,
        retryAttempt: action.retryAttempt,
        status: "degraded",
      };
    case "heartbeat-timeout":
      return {
        ...state,
        lastHeartbeatAt: action.now,
        status: "degraded",
      };
    case "polling-started":
      return {
        ...state,
        status: "polling",
      };
  }
}

export function parseRunsLiveEvent(input: {
  data?: string;
  lastEventId?: string;
}): RunsLiveStreamEvent {
  const fallbackCursor = input.lastEventId?.trim()
    ? input.lastEventId.trim()
    : null;
  const raw = input.data?.trim();
  if (!raw) {
    return {
      cursor: fallbackCursor,
      kind: "heartbeat",
    };
  }

  try {
    const parsed = JSON.parse(raw) as {
      cursor?: unknown;
      entity?: unknown;
      event?: unknown;
      generated_at?: unknown;
      id?: unknown;
      kind?: string;
      payload?: {
        run_id?: unknown;
        status?: unknown;
      };
      run_id?: unknown;
      runs?: unknown;
      status?: unknown;
      terminal?: unknown;
      type?: string;
    };
    const cursor =
      typeof parsed.cursor === "string" && parsed.cursor.trim()
        ? parsed.cursor.trim()
        : typeof parsed.generated_at === "string" && parsed.generated_at.trim()
          ? parsed.generated_at.trim()
          : fallbackCursor;
    const eventKind = parsed.event ?? parsed.kind ?? parsed.type ?? "snapshot";
    const entity =
      typeof parsed.entity === "string" && parsed.entity.trim()
        ? parsed.entity.trim()
        : Array.isArray(parsed.runs)
          ? "runs"
          : "run";
    const runId =
      typeof parsed.run_id === "string"
        ? parsed.run_id
        : typeof parsed.payload?.run_id === "string"
          ? parsed.payload.run_id
          : typeof parsed.id === "string" && entity === "run"
            ? parsed.id
            : undefined;
    const status =
      typeof parsed.status === "string"
        ? parsed.status
        : typeof parsed.payload?.status === "string"
          ? parsed.payload.status
          : null;
    if (eventKind === "heartbeat") {
      return {
        cursor,
        kind: "heartbeat",
      };
    }
    if (Array.isArray(parsed.runs)) {
      return {
        cursor,
        entity: "runs",
        event: typeof eventKind === "string" ? eventKind : "snapshot",
        kind: "runs.snapshot",
      };
    }
    if (runId) {
      if (
        eventKind === "governance.waiting" ||
        eventKind === "human_gate.waiting"
      ) {
        return withProducerTerminal(
          {
            cursor,
            entity,
            event: eventKind,
            kind: "governance.waiting",
            runId,
            status,
          },
          parsed.terminal,
        );
      }
      if (eventKind === "node.progress" || eventKind === "node.updated") {
        return withProducerTerminal(
          {
            cursor,
            entity,
            event: eventKind,
            kind: "run.node",
            runId,
            status,
          },
          parsed.terminal,
        );
      }
      if (eventKind === "status.updated" || eventKind === "status") {
        return withProducerTerminal(
          {
            cursor,
            entity,
            event: eventKind,
            kind: "run.status",
            runId,
            status,
          },
          parsed.terminal,
        );
      }
      return withProducerTerminal(
        {
          cursor,
          entity,
          event: typeof eventKind === "string" ? eventKind : "snapshot",
          kind: "run.snapshot",
          runId,
          status,
        },
        parsed.terminal,
      );
    }
    return {
      cursor,
      entity: typeof entity === "string" ? entity : null,
      event: typeof eventKind === "string" ? eventKind : null,
      kind: "unknown",
    };
  } catch {
    return {
      cursor: fallbackCursor,
      kind: "unknown",
    };
  }
}

export function shouldInvalidateRunsForEvent(event: RunsLiveStreamEvent) {
  return event.kind !== "heartbeat";
}
