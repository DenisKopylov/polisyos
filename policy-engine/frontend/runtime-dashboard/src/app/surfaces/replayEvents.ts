import { getSurfaceById, type SurfaceId } from "./surfaceRegistry";

export const REPLAY_EVENT_SCHEMA = "polisyos.atlas.replay_event.v1" as const;

const REPLAY_EVENT_KINDS = [
  "annotation.created",
  "drilldown.opened",
  "evidence.saved",
  "onboarding.step.completed",
  "scenario.explored",
  "surface.opened",
  "surface.tab.changed",
  "threshold.changed",
] as const;

const REPLAY_ACTOR_LENSES = [
  "appellant",
  "data_scientist",
  "operator",
  "regulator",
] as const;

export type ReplayEventKind = (typeof REPLAY_EVENT_KINDS)[number];

export type ReplayEventRoute = {
  fullPath: string;
  path: string;
  routeId?: string;
  search?: string;
};

export type ReplayEventActor = {
  id?: string;
  lens?: "appellant" | "data_scientist" | "operator" | "regulator";
  role?: string;
};

export type ReplayEventEnvelope<
  Payload extends Record<string, unknown> = Record<string, unknown>,
> = {
  actor?: ReplayEventActor;
  context?: {
    runId?: string;
    sessionId?: string;
    temporalScope?: {
      txAt?: string | null;
      validAt?: string | null;
    };
  };
  eventId: string;
  kind: ReplayEventKind;
  occurredAt: string;
  payload: Payload;
  route: ReplayEventRoute;
  schema: typeof REPLAY_EVENT_SCHEMA;
  sequence: number;
  surfaceId: SurfaceId;
};

export type CreateReplayEventInput<
  Payload extends Record<string, unknown> = Record<string, unknown>,
> = Omit<ReplayEventEnvelope<Payload>, "eventId" | "schema"> & {
  eventId?: string;
};

function normalizeForHash(value: unknown): string {
  if (Array.isArray(value)) {
    return `[${value.map((item) => normalizeForHash(item)).join(",")}]`;
  }
  if (value && typeof value === "object") {
    return `{${Object.entries(value as Record<string, unknown>)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(
        ([key, nested]) => `${JSON.stringify(key)}:${normalizeForHash(nested)}`,
      )
      .join(",")}}`;
  }
  return JSON.stringify(value);
}

function fnv1a(input: string) {
  let hash = 0x811c9dc5;
  for (let index = 0; index < input.length; index += 1) {
    hash ^= input.charCodeAt(index);
    hash = Math.imul(hash, 0x01000193);
  }
  return (hash >>> 0).toString(16).padStart(8, "0");
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function isOptionalString(value: unknown): value is string | undefined {
  return value === undefined || typeof value === "string";
}

function isOptionalNullableString(
  value: unknown,
): value is string | null | undefined {
  return value === undefined || value === null || typeof value === "string";
}

function isReplayEventKind(value: unknown): value is ReplayEventKind {
  return (
    typeof value === "string" &&
    REPLAY_EVENT_KINDS.includes(value as ReplayEventKind)
  );
}

function isReplayActorLens(
  value: unknown,
): value is NonNullable<ReplayEventActor["lens"]> | undefined {
  return (
    value === undefined ||
    (typeof value === "string" &&
      REPLAY_ACTOR_LENSES.includes(
        value as NonNullable<ReplayEventActor["lens"]>,
      ))
  );
}

function isKnownSurfaceId(value: unknown): value is SurfaceId {
  return (
    typeof value === "string" && Boolean(getSurfaceById(value as SurfaceId))
  );
}

function isReplayEventRoute(value: unknown): value is ReplayEventRoute {
  return (
    isRecord(value) &&
    typeof value.fullPath === "string" &&
    typeof value.path === "string" &&
    isOptionalString(value.routeId) &&
    isOptionalString(value.search)
  );
}

function isReplayEventActor(value: unknown): value is ReplayEventActor {
  return (
    isRecord(value) &&
    isOptionalString(value.id) &&
    isReplayActorLens(value.lens) &&
    isOptionalString(value.role)
  );
}

function isReplayEventContext(
  value: unknown,
): value is NonNullable<ReplayEventEnvelope["context"]> {
  if (!isRecord(value)) {
    return false;
  }
  if (!isOptionalString(value.runId) || !isOptionalString(value.sessionId)) {
    return false;
  }
  if (value.temporalScope === undefined) {
    return true;
  }
  return (
    isRecord(value.temporalScope) &&
    isOptionalNullableString(value.temporalScope.txAt) &&
    isOptionalNullableString(value.temporalScope.validAt)
  );
}

export function createReplayEventId(
  input: Omit<CreateReplayEventInput, "eventId">,
) {
  return `replay_evt_${fnv1a(normalizeForHash(input))}`;
}

export function createReplayEventEnvelope<
  Payload extends Record<string, unknown>,
>(input: CreateReplayEventInput<Payload>): ReplayEventEnvelope<Payload> {
  const eventWithoutId = {
    actor: input.actor,
    context: input.context,
    kind: input.kind,
    occurredAt: input.occurredAt,
    payload: input.payload,
    route: input.route,
    sequence: input.sequence,
    surfaceId: input.surfaceId,
  };

  return {
    ...eventWithoutId,
    eventId: input.eventId ?? createReplayEventId(eventWithoutId),
    schema: REPLAY_EVENT_SCHEMA,
  };
}

export function isReplayEventEnvelope(
  value: unknown,
): value is ReplayEventEnvelope {
  return (
    isRecord(value) &&
    value.schema === REPLAY_EVENT_SCHEMA &&
    typeof value.eventId === "string" &&
    isReplayEventKind(value.kind) &&
    typeof value.occurredAt === "string" &&
    Number.isFinite(Date.parse(value.occurredAt)) &&
    isRecord(value.payload) &&
    isReplayEventRoute(value.route) &&
    typeof value.sequence === "number" &&
    Number.isInteger(value.sequence) &&
    value.sequence >= 0 &&
    isKnownSurfaceId(value.surfaceId) &&
    (value.actor === undefined || isReplayEventActor(value.actor)) &&
    (value.context === undefined || isReplayEventContext(value.context))
  );
}

export function parseReplayEventEnvelope(value: unknown) {
  return isReplayEventEnvelope(value) ? value : null;
}

export function createSurfaceOpenedReplayEvent(input: {
  fullPath: string;
  occurredAt: string;
  path: string;
  routeId?: string;
  runId?: string;
  sequence: number;
  sessionId?: string;
  surfaceId: SurfaceId;
}) {
  return createReplayEventEnvelope({
    context: {
      runId: input.runId,
      sessionId: input.sessionId,
    },
    kind: "surface.opened",
    occurredAt: input.occurredAt,
    payload: {},
    route: {
      fullPath: input.fullPath,
      path: input.path,
      routeId: input.routeId,
    },
    sequence: input.sequence,
    surfaceId: input.surfaceId,
  });
}
