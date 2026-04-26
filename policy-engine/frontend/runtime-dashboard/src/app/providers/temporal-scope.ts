export type TemporalScope = {
  validAt?: string | null;
  txAt?: string | null;
  branch?: string | null;
  snapshotId?: string | null;
  scenarioId?: string | null;
};

export type TemporalScopeKey = {
  branch: string | null;
  scenarioId: string | null;
  snapshotId: string | null;
  txAt: string | null;
  validAt: string | null;
};

export type TemporalRange = {
  earliest: string | null;
  latest: string | null;
};

export type TemporalEventPoint = {
  id: string;
  timestamp: string;
  kind:
    | "run_start"
    | "run_finish"
    | "trace_event"
    | "policy_change"
    | "late_evidence"
    | "correction"
    | "snapshot"
    | "now";
  label: string;
  validAt?: string | null;
  txAt?: string | null;
  observed?: boolean;
};

export type TemporalSurfaceCapability = {
  surface: string;
  supported: boolean;
  resolution: string;
  reasonCode?: string | null;
  validRange?: TemporalRange | null;
  txRange?: TemporalRange | null;
  nearestEventPoints?: TemporalEventPoint[];
  gaps?: Array<{
    start?: string | null;
    end?: string | null;
    reasonCode: string;
    label?: string | null;
  }>;
};

export type TemporalCapabilities = {
  runId?: string | null;
  defaultScope?: TemporalScope | null;
  validRange: TemporalRange;
  txRange: TemporalRange;
  resolution: string;
  surfaces: TemporalSurfaceCapability[];
  eventPoints: TemporalEventPoint[];
};

export function normalizeTemporalInstant(value: string | null | undefined) {
  if (!value) {
    return null;
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return null;
  }
  return date.toISOString();
}

export function normalizeTemporalScope(
  scope: TemporalScope | null | undefined,
): TemporalScope | null {
  if (!scope) {
    return null;
  }
  const normalized: TemporalScope = {
    validAt: normalizeTemporalInstant(scope.validAt),
    txAt: normalizeTemporalInstant(scope.txAt),
    branch: normalizeOptionalString(scope.branch),
    snapshotId: normalizeOptionalString(scope.snapshotId),
    scenarioId: normalizeOptionalString(scope.scenarioId),
  };
  return hasTemporalScope(normalized) ? normalized : null;
}

export function hasTemporalScope(scope: TemporalScope | null | undefined) {
  return Boolean(
    scope?.validAt ||
    scope?.txAt ||
    scope?.branch ||
    scope?.snapshotId ||
    scope?.scenarioId,
  );
}

export function temporalScopeKey(
  scope: TemporalScope | null | undefined,
): TemporalScopeKey {
  const normalized = normalizeTemporalScope(scope);
  return {
    validAt: normalized?.validAt ?? null,
    txAt: normalized?.txAt ?? null,
    branch: normalized?.branch ?? null,
    snapshotId: normalized?.snapshotId ?? null,
    scenarioId: normalized?.scenarioId ?? null,
  };
}

export function compareTemporalScopes(
  left: TemporalScope | null | undefined,
  right: TemporalScope | null | undefined,
) {
  return (
    JSON.stringify(temporalScopeKey(left)) ===
    JSON.stringify(temporalScopeKey(right))
  );
}

export function toApiTemporalParams(scope: TemporalScope | null | undefined) {
  const normalized = normalizeTemporalScope(scope);
  if (!normalized) {
    return {};
  }
  return withoutUndefined({
    valid_at: normalized.validAt ?? undefined,
    tx_at: normalized.txAt ?? undefined,
    branch: normalized.branch ?? undefined,
    snapshot_id: normalized.snapshotId ?? undefined,
    scenario_id: normalized.scenarioId ?? undefined,
  });
}

export function fromApiTemporalScope(
  scope:
    | {
        valid_at?: string | null;
        tx_at?: string | null;
        branch?: string | null;
        snapshot_id?: string | null;
        scenario_id?: string | null;
      }
    | null
    | undefined,
): TemporalScope | null {
  return normalizeTemporalScope(
    scope
      ? {
          validAt: scope.valid_at,
          txAt: scope.tx_at,
          branch: scope.branch,
          snapshotId: scope.snapshot_id,
          scenarioId: scope.scenario_id,
        }
      : null,
  );
}

export function toApiTemporalRange(
  range:
    | {
        earliest?: string | null;
        latest?: string | null;
      }
    | null
    | undefined,
): TemporalRange {
  return {
    earliest: normalizeTemporalInstant(range?.earliest) ?? null,
    latest: normalizeTemporalInstant(range?.latest) ?? null,
  };
}

export function clampTemporalInstant(
  value: string,
  range: TemporalRange | null | undefined,
) {
  const instant = normalizeTemporalInstant(value);
  if (!instant || !range) {
    return instant;
  }
  const time = new Date(instant).getTime();
  const earliest = range.earliest ? new Date(range.earliest).getTime() : null;
  const latest = range.latest ? new Date(range.latest).getTime() : null;
  if (earliest !== null && time < earliest) {
    return range.earliest;
  }
  if (latest !== null && time > latest) {
    return range.latest;
  }
  return instant;
}

export function stepTemporalInstant(
  value: string | null | undefined,
  amountMs: number,
  range?: TemporalRange | null,
) {
  const base =
    normalizeTemporalInstant(value) ?? normalizeTemporalInstant(range?.latest);
  const next = new Date(
    (base ? new Date(base).getTime() : Date.now()) + amountMs,
  );
  return clampTemporalInstant(next.toISOString(), range) ?? next.toISOString();
}

export function formatTemporalAnnouncement(
  scope: TemporalScope,
  locale = "en",
) {
  const valid = formatTemporalDate(scope.validAt, locale);
  const tx = formatTemporalDate(scope.txAt, locale);
  return `Policy time moved to ${valid}; knowledge as of ${tx}`;
}

export function formatTemporalDate(
  value: string | null | undefined,
  locale = "en",
) {
  const normalized = normalizeTemporalInstant(value);
  if (!normalized) {
    return "latest";
  }
  return new Intl.DateTimeFormat(locale, {
    day: "numeric",
    month: "long",
    year: "numeric",
  }).format(new Date(normalized));
}

function normalizeOptionalString(value: string | null | undefined) {
  const trimmed = value?.trim();
  return trimmed ? trimmed : null;
}

function withoutUndefined<T extends Record<string, unknown>>(value: T) {
  return Object.fromEntries(
    Object.entries(value).filter(
      (entry): entry is [string, unknown] => entry[1] !== undefined,
    ),
  ) as Partial<T>;
}
