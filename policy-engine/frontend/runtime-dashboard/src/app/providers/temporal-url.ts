import {
  hasTemporalScope,
  normalizeTemporalScope,
  type TemporalScope,
} from "./temporal-scope";

const CANONICAL_PARAMS = [
  "valid_at",
  "tx_at",
  "branch",
  "snapshot_id",
  "scenario_id",
  "t",
] as const;

export function readTemporalScopeFromSearchParams(
  params: URLSearchParams,
): TemporalScope | null {
  const shorthand = params.get("t");
  const validAt = params.get("valid_at") ?? shorthand;
  return normalizeTemporalScope({
    validAt,
    txAt: params.get("tx_at"),
    branch: params.get("branch"),
    snapshotId: params.get("snapshot_id"),
    scenarioId: params.get("scenario_id"),
  });
}

export function writeTemporalScopeToSearchParams(
  params: URLSearchParams,
  scope: TemporalScope | null | undefined,
  options: { shorthand?: boolean } = {},
) {
  for (const key of CANONICAL_PARAMS) {
    params.delete(key);
  }
  const normalized = normalizeTemporalScope(scope);
  if (!normalized || !hasTemporalScope(normalized)) {
    return params;
  }
  if (options.shorthand && normalized.validAt && !normalized.txAt) {
    params.set("t", normalized.validAt);
  } else if (normalized.validAt) {
    params.set("valid_at", normalized.validAt);
  }
  if (normalized.txAt) {
    params.set("tx_at", normalized.txAt);
  }
  if (normalized.branch) {
    params.set("branch", normalized.branch);
  }
  if (normalized.snapshotId) {
    params.set("snapshot_id", normalized.snapshotId);
  }
  if (normalized.scenarioId) {
    params.set("scenario_id", normalized.scenarioId);
  }
  return params;
}

export function serializeTemporalUrlParams(
  scope: TemporalScope | null | undefined,
) {
  return writeTemporalScopeToSearchParams(
    new URLSearchParams(),
    scope,
  ).toString();
}

export function readTemporalScopeFromLocation(location: Location | URL) {
  return readTemporalScopeFromSearchParams(
    new URLSearchParams(location.search),
  );
}

export function replaceTemporalScopeInCurrentUrl(
  scope: TemporalScope | null | undefined,
) {
  if (typeof window === "undefined") {
    return;
  }
  const url = new URL(window.location.href);
  writeTemporalScopeToSearchParams(url.searchParams, scope);
  window.history.replaceState(window.history.state, "", url);
}
