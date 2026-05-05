import {
  buildConnectorCharacterCards,
  buildFreshnessBraidView,
} from "./productionSlice";

import type { ConnectorsListResponse } from "@/api/hooks/useConnectors";
import type { SourceProfilesListResponse } from "@/api/hooks/useSourceProfiles";
import type { RunEvidenceContext } from "@/shared/lib/domain/evidence";

const connectors = [
  {
    connector_id: "world-bank",
    known_datasets: ["cpi", "gdp", "jobs"],
    last_health_check: "2026-03-10T06:00:00Z",
    loaded: true,
    namespace: "warehouse",
    version: "1.4.0",
  },
  {
    connector_id: "tax-ledger",
    known_datasets: ["appeals"],
    last_health_check: "2026-03-09T08:00:00Z",
    loaded: true,
    namespace: "tax-ledger",
    version: "2.0.0",
  },
] satisfies NonNullable<ConnectorsListResponse["connectors"]>;

const profiles = [
  {
    auth_policy: "none",
    base_url: "https://example.test/world-bank",
    connector_available: true,
    connector_family: "warehouse",
    description: "Macro indicators",
    display_name: "World Bank",
    estimated_datasets: 4,
    profile_id: "macro-profile",
    source_organization: "World Bank",
  },
  {
    auth_policy: "oauth",
    base_url: "https://example.test/tax-ledger",
    connector_available: true,
    connector_family: "tax-ledger",
    description: "Appeals ledger",
    display_name: "Tax ledger",
    estimated_datasets: 1,
    profile_id: "appeals-profile",
    source_organization: "Revenue",
  },
] satisfies NonNullable<SourceProfilesListResponse["profiles"]>;

const runContext = {
  dataNeeds: [],
  dataSnapshotRef: null,
  evidenceBundleRef: null,
  executionPlanRef: null,
  fetchPlans: [
    {
      connectorId: "world-bank",
      datasetId: "cpi",
      dateEnd: null,
      dateStart: null,
      fallbackCount: 0,
      filters: {},
      granularity: "annual",
      matchedNeedIds: [],
      metricId: "inflation",
      notes: [],
      planId: "plan-1",
      profileId: "macro-profile",
      qualityMin: 0.8,
      sourceLane: "fastlane",
    },
    {
      connectorId: "tax-ledger",
      datasetId: "appeals",
      dateEnd: null,
      dateStart: null,
      fallbackCount: 0,
      filters: {},
      granularity: "daily",
      matchedNeedIds: [],
      metricId: "appeals",
      notes: [],
      planId: "plan-2",
      profileId: "appeals-profile",
      qualityMin: 0.7,
      sourceLane: "fastlane",
    },
  ],
  inputBindingsRef: null,
  promotionCandidates: [
    {
      confidence: 0.91,
      connectorId: "world-bank",
      createdAt: null,
      datasetId: "gdp",
      matchedPlanId: "plan-1",
      metadata: {},
      metricId: "growth",
      profileId: "macro-profile",
      promotionId: "promotion-1",
      signals: [],
      sourceLane: "explorelane",
      status: "pending",
    },
  ],
  relatedArtifacts: [],
  runId: "run-1",
  sourceKind: "core_run",
  warnings: [],
} satisfies RunEvidenceContext;

describe("Phase 3.2 production slice adapters", () => {
  it("builds a freshness braid with a governing lag and derived fact pressure", () => {
    const view = buildFreshnessBraidView({
      connectors,
      generatedAt: "2026-03-10T12:00:00Z",
      now: new Date("2026-03-10T12:00:00Z"),
      profiles,
      runContext,
    });

    expect(view.threads).toHaveLength(2);
    expect(view.governingThreadId).toBe("tax-ledger");
    expect(view.governingLagMs).toBe(28 * 60 * 60 * 1000);
    expect(view.joinNodes[0]).toMatchObject({
      id: "run-evidence-join",
      sourceCount: 2,
    });
    expect(
      view.threads.find((thread) => thread.connectorId === "world-bank"),
    ).toMatchObject({
      derivedFactCount: 2,
      governing: false,
      profileIds: ["macro-profile"],
      state: "ok",
    });
    expect(
      view.threads.find((thread) => thread.connectorId === "tax-ledger"),
    ).toMatchObject({
      derivedFactCount: 1,
      governing: true,
      state: "fail",
    });
  });

  it("builds connector character cards with latency, cost, retry and lineage counts", () => {
    const cards = buildConnectorCharacterCards({
      connectors,
      profiles,
      runContext,
    });

    expect(cards).toHaveLength(2);
    expect(cards[0]).toMatchObject({
      connectorId: "world-bank",
      costTier: "low",
      factsThroughConnector: 2,
      lastGreenPull: "2026-03-10T06:00:00Z",
      loaded: true,
      profileCount: 1,
      retryProfile: "steady",
    });
    expect(cards[0].latencyP50Ms).toBeGreaterThan(0);
    expect(cards[0].latencyP95Ms).toBeGreaterThan(cards[0].latencyP50Ms ?? 0);
  });

  it("marks unavailable connectors as exhausted and fully burned", () => {
    const cards = buildConnectorCharacterCards({
      connectors: [
        {
          connector_id: "offline",
          known_datasets: [],
          last_health_check: null,
          loaded: false,
          namespace: "offline",
          version: "0.0.0",
        },
      ],
      profiles: [],
      runContext,
    });

    expect(cards[0]).toMatchObject({
      errorBudgetBurn: 1,
      lastGreenPull: null,
      latencyP50Ms: null,
      latencyP95Ms: null,
      retryProfile: "exhausted",
    });
  });

  it("falls back to source-profile threads and cards when connector inventory is empty", () => {
    const braid = buildFreshnessBraidView({
      generatedAt: "2026-03-10T12:00:00Z",
      now: new Date("2026-03-10T12:00:00Z"),
      profiles,
      runContext,
    });
    const cards = buildConnectorCharacterCards({
      profiles,
      runContext,
    });

    expect(braid.threads.map((thread) => thread.connectorId)).toEqual([
      "warehouse",
      "tax-ledger",
    ]);
    expect(braid.threads[0]).toMatchObject({
      profileIds: ["macro-profile"],
      state: "ok",
      volume: 4,
    });
    expect(cards[0]).toMatchObject({
      connectorId: "warehouse",
      datasetCount: 4,
      factsThroughConnector: 0,
      loaded: true,
      version: "profile",
    });
  });
});
