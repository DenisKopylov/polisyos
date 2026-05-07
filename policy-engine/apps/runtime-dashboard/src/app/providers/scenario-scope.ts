export type CounterfactualMode =
  | "actual"
  | "actual_vs_scenario"
  | "scenario_only";

export type ScenarioScope = {
  scenarioId?: string | null;
  mode?: CounterfactualMode | null;
};

export type ScenarioScopeKey = {
  mode: CounterfactualMode;
  scenarioId: string | null;
};

const DEFAULT_MODE: CounterfactualMode = "actual";
const MODES = new Set<CounterfactualMode>([
  "actual",
  "actual_vs_scenario",
  "scenario_only",
]);

export function normalizeCounterfactualMode(
  value: string | null | undefined,
): CounterfactualMode {
  return MODES.has(value as CounterfactualMode)
    ? (value as CounterfactualMode)
    : DEFAULT_MODE;
}

export function normalizeScenarioScope(
  scope: ScenarioScope | null | undefined,
): ScenarioScope {
  return {
    scenarioId: normalizeOptionalString(scope?.scenarioId),
    mode: normalizeCounterfactualMode(scope?.mode),
  };
}

export function scenarioScopeKey(
  scope: ScenarioScope | null | undefined,
): ScenarioScopeKey {
  const normalized = normalizeScenarioScope(scope);
  return {
    scenarioId: normalized.scenarioId ?? null,
    mode: normalized.mode ?? DEFAULT_MODE,
  };
}

export function compareScenarioScopes(
  left: ScenarioScope | null | undefined,
  right: ScenarioScope | null | undefined,
) {
  return (
    JSON.stringify(scenarioScopeKey(left)) ===
    JSON.stringify(scenarioScopeKey(right))
  );
}

export function toApiScenarioParams(scope: ScenarioScope | null | undefined) {
  const normalized = normalizeScenarioScope(scope);
  return normalized.scenarioId ? { scenario_id: normalized.scenarioId } : {};
}

export function readScenarioScopeFromSearchParams(
  params: URLSearchParams,
): ScenarioScope {
  return {
    scenarioId: normalizeOptionalString(params.get("scenario_id")),
    mode: normalizeCounterfactualMode(params.get("cf_mode")),
  };
}

export function writeScenarioScopeToSearchParams(
  params: URLSearchParams,
  scope: ScenarioScope | null | undefined,
) {
  const normalized = normalizeScenarioScope(scope);
  params.delete("cf_mode");
  params.delete("scenario_id");
  if (normalized.scenarioId) {
    params.set("scenario_id", normalized.scenarioId);
  }
  if (normalized.mode && normalized.mode !== DEFAULT_MODE) {
    params.set("cf_mode", normalized.mode);
  }
  return params;
}

export function serializeScenarioUrlParams(
  scope: ScenarioScope | null | undefined,
) {
  return writeScenarioScopeToSearchParams(
    new URLSearchParams(),
    scope,
  ).toString();
}

export function readScenarioScopeFromLocation(location: Location | URL) {
  return readScenarioScopeFromSearchParams(
    new URLSearchParams(location.search),
  );
}

export function replaceScenarioScopeInCurrentUrl(
  scope: ScenarioScope | null | undefined,
) {
  if (typeof window === "undefined") {
    return;
  }
  const url = new URL(window.location.href);
  writeScenarioScopeToSearchParams(url.searchParams, scope);
  window.history.replaceState(window.history.state, "", url);
}

function normalizeOptionalString(value: string | null | undefined) {
  const trimmed = value?.trim();
  return trimmed ? trimmed : null;
}
