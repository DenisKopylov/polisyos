import type { ConnectorsListResponse } from "@/api/hooks/useConnectors";
import type { SourceProfilesListResponse } from "@/api/hooks/useSourceProfiles";
import type { RunEvidenceContext } from "@/shared/lib/domain/evidence";

export type FreshnessState = "ok" | "warn" | "fail" | "unknown";

export type FreshnessBraidThread = {
  connectorId: string;
  derivedFactCount: number;
  governing: boolean;
  label: string;
  lagMs: number | null;
  lastObservedAt: string | null;
  profileIds: string[];
  slaMs: number;
  state: FreshnessState;
  volume: number;
};

export type FreshnessBraidView = {
  generatedAt: string | null;
  governingLagMs: number | null;
  governingThreadId: string | null;
  joinNodes: Array<{
    id: string;
    label: string;
    sourceCount: number;
  }>;
  threads: FreshnessBraidThread[];
};

export type ConnectorCharacterCard = {
  connectorId: string;
  costTier: "low" | "medium" | "high";
  datasetCount: number;
  errorBudgetBurn: number;
  factsThroughConnector: number;
  lastGreenPull: string | null;
  latencyP50Ms: number | null;
  latencyP95Ms: number | null;
  loaded: boolean;
  namespace: string;
  profileCount: number;
  profileIds: string[];
  retryProfile: "steady" | "watch" | "exhausted";
  version: string;
};

type ConnectorProjection = {
  connectorId: string;
  datasetCount: number;
  lastHealthCheck: string | null;
  loaded: boolean;
  namespace: string;
  profileIds: string[];
  version: string;
};

const DEFAULT_SLA_MS = 6 * 60 * 60 * 1000;
const SLOW_SLA_MS = 24 * 60 * 60 * 1000;

function timestampLagMs(
  timestamp: string | null | undefined,
  now: Date,
): number | null {
  if (!timestamp) {
    return null;
  }
  const parsed = Date.parse(timestamp);
  if (!Number.isFinite(parsed)) {
    return null;
  }
  return Math.max(0, now.getTime() - parsed);
}

function freshnessState(lagMs: number | null, slaMs: number): FreshnessState {
  if (lagMs === null) {
    return "unknown";
  }
  if (lagMs <= slaMs) {
    return "ok";
  }
  if (lagMs <= slaMs * 2) {
    return "warn";
  }
  return "fail";
}

function connectorProfiles(
  connectorId: string,
  namespace: string | null | undefined,
  profiles: SourceProfilesListResponse["profiles"] = [],
) {
  return profiles.filter(
    (profile) =>
      profile.connector_family === namespace ||
      profile.connector_family === connectorId,
  );
}

function uniqueStrings(values: Array<string | null | undefined>) {
  return values.filter(
    (value, index): value is string =>
      Boolean(value) && values.indexOf(value) === index,
  );
}

function connectorProjections(
  connectors: ConnectorsListResponse["connectors"] = [],
  profiles: SourceProfilesListResponse["profiles"] = [],
): ConnectorProjection[] {
  if (connectors.length > 0) {
    return connectors.map((connector) => {
      const connectorNamespace = connector.namespace || connector.connector_id;
      const matchedProfiles = connectorProfiles(
        connector.connector_id,
        connectorNamespace,
        profiles,
      );

      return {
        connectorId: connector.connector_id,
        datasetCount:
          connector.known_datasets?.length ??
          matchedProfiles.reduce(
            (total, profile) => total + (profile.estimated_datasets ?? 0),
            0,
          ),
        lastHealthCheck: connector.last_health_check ?? null,
        loaded: connector.loaded,
        namespace: connectorNamespace,
        profileIds: uniqueStrings([
          ...(connector.available_profiles ?? []),
          ...matchedProfiles.map((profile) => profile.profile_id),
        ]),
        version: connector.version || "unknown",
      };
    });
  }

  const groupedProfiles = new Map<string, ConnectorProjection>();
  for (const profile of profiles) {
    const connectorId = profile.connector_family || profile.profile_id;
    const current = groupedProfiles.get(connectorId) ?? {
      connectorId,
      datasetCount: 0,
      lastHealthCheck: null,
      loaded: false,
      namespace: connectorId,
      profileIds: [],
      version: "profile",
    };

    groupedProfiles.set(connectorId, {
      ...current,
      datasetCount: current.datasetCount + (profile.estimated_datasets ?? 0),
      loaded: current.loaded || profile.connector_available,
      profileIds: uniqueStrings([...current.profileIds, profile.profile_id]),
    });
  }

  return Array.from(groupedProfiles.values());
}

function promotionCountForConnector(
  connectorId: string,
  runContext: RunEvidenceContext | null | undefined,
) {
  return (
    runContext?.promotionCandidates.filter(
      (candidate) => candidate.connectorId === connectorId,
    ).length ?? 0
  );
}

function planCountForConnector(
  connectorId: string,
  runContext: RunEvidenceContext | null | undefined,
) {
  return (
    runContext?.fetchPlans.filter((plan) => plan.connectorId === connectorId)
      .length ?? 0
  );
}

export function buildFreshnessBraidView(input: {
  connectors?: ConnectorsListResponse["connectors"];
  generatedAt?: string | null;
  now?: Date;
  profiles?: SourceProfilesListResponse["profiles"];
  runContext?: RunEvidenceContext | null;
}): FreshnessBraidView {
  const now = input.now ?? new Date();
  const connectors = connectorProjections(
    input.connectors ?? [],
    input.profiles ?? [],
  );

  const threads = connectors.map<FreshnessBraidThread>((connector) => {
    const derivedFactCount =
      promotionCountForConnector(connector.connectorId, input.runContext) +
      planCountForConnector(connector.connectorId, input.runContext);
    const lastObservedAt =
      connector.lastHealthCheck ?? input.generatedAt ?? null;
    const lagMs = timestampLagMs(lastObservedAt, now);
    const slaMs = connector.loaded ? DEFAULT_SLA_MS : SLOW_SLA_MS;

    return {
      connectorId: connector.connectorId,
      derivedFactCount,
      governing: false,
      label: connector.namespace,
      lagMs,
      lastObservedAt,
      profileIds: connector.profileIds,
      slaMs,
      state: connector.loaded ? freshnessState(lagMs, slaMs) : "fail",
      volume: Math.max(1, connector.datasetCount + derivedFactCount),
    };
  });

  const governingThread =
    threads
      .filter((thread) => thread.lagMs !== null)
      .sort((a, b) => (b.lagMs ?? 0) - (a.lagMs ?? 0))[0] ?? null;

  return {
    generatedAt: input.generatedAt ?? null,
    governingLagMs: governingThread?.lagMs ?? null,
    governingThreadId: governingThread?.connectorId ?? null,
    joinNodes: [
      {
        id: "run-evidence-join",
        label: input.runContext ? "run evidence context" : "evidence fabric",
        sourceCount: threads.length,
      },
    ],
    threads: threads.map((thread) => ({
      ...thread,
      governing: thread.connectorId === governingThread?.connectorId,
    })),
  };
}

export function buildConnectorCharacterCards(input: {
  connectors?: ConnectorsListResponse["connectors"];
  profiles?: SourceProfilesListResponse["profiles"];
  runContext?: RunEvidenceContext | null;
}): ConnectorCharacterCard[] {
  const connectors = connectorProjections(
    input.connectors ?? [],
    input.profiles ?? [],
  );

  return connectors.map((connector) => {
    const datasetCount = connector.datasetCount;
    const factsThroughConnector =
      promotionCountForConnector(connector.connectorId, input.runContext) +
      planCountForConnector(connector.connectorId, input.runContext);
    const profilePressure = Math.min(1, connector.profileIds.length / 8);
    const datasetPressure = Math.min(1, datasetCount / 20);
    const errorBudgetBurn = connector.loaded
      ? Math.min(0.92, 0.08 + profilePressure * 0.24 + datasetPressure * 0.18)
      : 1;
    const latencyP50Ms = connector.loaded
      ? Math.round(90 + profilePressure * 140 + datasetPressure * 80)
      : null;
    const latencyP95Ms =
      latencyP50Ms === null ? null : Math.round(latencyP50Ms * 2.6);

    return {
      connectorId: connector.connectorId,
      costTier:
        datasetCount > 16 || connector.profileIds.length > 6
          ? "high"
          : datasetCount > 6 || connector.profileIds.length > 2
            ? "medium"
            : "low",
      datasetCount,
      errorBudgetBurn,
      factsThroughConnector,
      lastGreenPull: connector.loaded ? connector.lastHealthCheck : null,
      latencyP50Ms,
      latencyP95Ms,
      loaded: connector.loaded,
      namespace: connector.namespace,
      profileCount: connector.profileIds.length,
      profileIds: connector.profileIds,
      retryProfile: connector.loaded
        ? errorBudgetBurn > 0.7
          ? "watch"
          : "steady"
        : "exhausted",
      version: connector.version,
    };
  });
}
