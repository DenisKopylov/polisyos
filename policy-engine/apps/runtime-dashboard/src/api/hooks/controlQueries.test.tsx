import { onlineManager } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  capabilitiesQueryOptions,
  fetchCapabilities,
  isIssuedCapabilityDiscovery,
  useCapabilities,
  useCapabilityManifestAvailability,
} from "@/api/hooks/useCapabilities";
import {
  connectorsQueryOptions,
  useConnectors,
} from "@/api/hooks/useConnectors";
import {
  dataIndexStatsQueryOptions,
  useDataIndexStats,
} from "@/api/hooks/useDataIndexStats";
import {
  dataPromotionCandidatesQueryOptions,
  useDataPromotionCandidates,
} from "@/api/hooks/useDataPromotionCandidates";
import { healthQueryOptions, useHealth } from "@/api/hooks/useHealth";
import {
  llmProfilesQueryOptions,
  useLlmProfiles,
} from "@/api/hooks/useLlmProfiles";
import {
  sourceProfilesQueryOptions,
  useSourceProfiles,
} from "@/api/hooks/useSourceProfiles";
import { queryKeys } from "@/api/queryKeys";
import {
  HEALTH_REFETCH_MS,
  RUNS_SAMPLE_STALE_MS,
} from "@/shared/lib/constants";
import {
  createQueryHookHarness,
  createQueryHookWrapper,
} from "@/test/queryHook";
import {
  mockRuntimeGetFailure,
  mockRuntimeGetSuccess,
} from "@/test/runtimeApi";

const capabilitiesPayload = {
  meta: {
    request_id: "owner-capability-manifest",
    generated_at: "2026-08-09T00:00:00Z",
    source_kinds: ["core_run"],
  },
  runtime_api_version: "2.0.0",
  shell_flavor: "atlas",
  default_execution_profile: "dev",
  default_locale: "en",
  supported_execution_profiles: ["dev"],
  supported_locales: ["en"],
  state_store_backend: "sqlite",
  worker_backend: "embedded",
  fallback_rules: {},
  security_posture: {},
  workspaces: [],
  features: [],
  constraints: {},
};

const healthPayload = {
  service: "runtime",
  status: "ok",
  ts: "2026-03-09T10:00:00Z",
};

const connectorsPayload = {
  connectors: [
    {
      connector_id: "bigquery",
      label: "BigQuery",
      status: "healthy",
    },
  ],
};

const llmProfilesPayload = {
  profiles: [
    {
      model_variant_id: "gpt-5.4-mini",
      label: "GPT-5.4 mini",
      provider: "openai",
    },
  ],
};

const sourceProfilesPayload = {
  profiles: [
    {
      profile_id: "statcan",
      label: "Statistics Canada",
      source_lane: "public",
    },
  ],
};

const dataIndexStatsPayload = {
  bindings_total: 12,
  datasets_total: 7,
  sources_total: 3,
};

const promotionCandidatesPayload = {
  meta: {
    generated_at: "2026-03-09T10:00:00Z",
    request_id: "req-promotions",
    source_kinds: ["core_run"],
  },
  candidates: [
    {
      promotion_id: "promo-1",
      metric_id: "inflation",
      connector_id: "bigquery",
      dataset_id: "macro",
    },
  ],
};

describe("control-plane query hooks", () => {
  afterEach(() => {
    onlineManager.setOnline(true);
    vi.restoreAllMocks();
  });

  it("loads the owner capability manifest without a placeholder", async () => {
    const getSpy = mockRuntimeGetSuccess(capabilitiesPayload);
    const { result } = renderHook(() => useCapabilities(), {
      wrapper: createQueryHookWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.data?.features).toEqual(capabilitiesPayload.features);
    expect(getSpy).toHaveBeenCalledWith("/api/v1/control/capabilities", {
      parseAs: "json",
    });

    const options = capabilitiesQueryOptions();
    expect(options.queryKey).toEqual(queryKeys.capabilities());
    expect(options.placeholderData).toBeUndefined();
    expect(options.retry).toBe(1);
    expect(options.staleTime).toBe(0);
    expect(options.refetchOnMount).toBe("always");
  });

  it("issues unavailable discovery during loading and runtime failures", async () => {
    mockRuntimeGetFailure(500, {
      code: "capabilities_unavailable",
      detail: "Capability manifest is unavailable",
      status: 500,
    });
    const { result } = renderHook(() => useCapabilityManifestAvailability(), {
      wrapper: createQueryHookWrapper(),
    });

    expect(result.current).toMatchObject({
      reason: "loading",
      state: "unavailable",
    });
    expect(isIssuedCapabilityDiscovery(result.current)).toBe(true);

    await waitFor(
      () => {
        expect(result.current).toMatchObject({
          reason: "error",
          state: "unavailable",
        });
      },
      { timeout: 3_000 },
    );
  });

  it("issues offline discovery while the capability query is paused", () => {
    onlineManager.setOnline(false);
    const { result } = renderHook(() => useCapabilityManifestAvailability(), {
      wrapper: createQueryHookWrapper(),
    });

    expect(result.current).toMatchObject({
      reason: "offline",
      state: "unavailable",
    });
  });

  it("issues missing-data discovery when a settled query has no owner response", async () => {
    mockRuntimeGetSuccess(capabilitiesPayload);
    const { queryClient, wrapper } = createQueryHookHarness();
    const { result } = renderHook(() => useCapabilityManifestAvailability(), {
      wrapper,
    });

    await waitFor(() => {
      expect(result.current).toMatchObject({ state: "available" });
    });

    const capabilityQuery = queryClient
      .getQueryCache()
      .find({ queryKey: queryKeys.capabilities() });
    if (!capabilityQuery) {
      throw new Error("Capability query was not created");
    }
    capabilityQuery.setState({
      ...capabilityQuery.state,
      data: undefined,
      fetchStatus: "idle",
      status: "success",
    });

    await waitFor(() => {
      expect(result.current).toMatchObject({
        reason: "missing_data",
        state: "unavailable",
      });
    });
  });

  it("issues manifest availability only after an owner response", async () => {
    mockRuntimeGetSuccess(capabilitiesPayload);
    const { result } = renderHook(() => useCapabilityManifestAvailability(), {
      wrapper: createQueryHookWrapper(),
    });

    await waitFor(() => {
      expect(result.current).toMatchObject({ state: "available" });
    });

    expect(isIssuedCapabilityDiscovery(result.current)).toBe(true);
    expect(result.current).toMatchObject({
      manifest: capabilitiesPayload,
      state: "available",
    });
  });

  it("surfaces capability manifest failures as runtime API errors", async () => {
    mockRuntimeGetFailure(500, {
      code: "capabilities_unavailable",
      detail: "Capability manifest is unavailable",
      status: 500,
    });

    await expect(fetchCapabilities()).rejects.toMatchObject({
      code: "capabilities_unavailable",
      status: 500,
    });
  });

  it("parses capability manifest payloads through the fetch helper", async () => {
    mockRuntimeGetSuccess(capabilitiesPayload);

    await expect(fetchCapabilities()).resolves.toEqual(capabilitiesPayload);
  });

  it("loads runtime health with refetch cadence", async () => {
    const getSpy = mockRuntimeGetSuccess(healthPayload);
    const { result } = renderHook(() => useHealth(), {
      wrapper: createQueryHookWrapper(),
    });

    await waitFor(() => {
      expect(result.current.data).toEqual(healthPayload);
    });

    expect(getSpy).toHaveBeenCalledWith("/api/v1/health");

    const options = healthQueryOptions();
    expect(options.queryKey).toEqual(queryKeys.health());
    expect(options.staleTime).toBe(HEALTH_REFETCH_MS);
    expect(options.refetchInterval).toBe(HEALTH_REFETCH_MS);
  });

  it("loads control-plane catalogs and indexes through shared query wrappers", async () => {
    const scenarios = [
      {
        endpoint: "/api/v1/control/data/connectors",
        expected: connectorsPayload,
        getQueryKey: () => queryKeys.connectors(),
        getStaleTime: () => undefined,
        hook: useConnectors,
        queryOptions: connectorsQueryOptions,
      },
      {
        endpoint: "/api/v1/control/llm/profiles",
        expected: llmProfilesPayload,
        getQueryKey: () => queryKeys.llmProfiles(),
        getStaleTime: () => undefined,
        hook: useLlmProfiles,
        queryOptions: llmProfilesQueryOptions,
      },
      {
        endpoint: "/api/v1/control/data/profiles",
        expected: sourceProfilesPayload,
        getQueryKey: () => queryKeys.sourceProfiles(),
        getStaleTime: () => undefined,
        hook: useSourceProfiles,
        queryOptions: sourceProfilesQueryOptions,
      },
      {
        endpoint: "/api/v1/control/data/index/stats",
        expected: dataIndexStatsPayload,
        getQueryKey: () => queryKeys.dataIndexStats(),
        getStaleTime: () => RUNS_SAMPLE_STALE_MS,
        hook: useDataIndexStats,
        queryOptions: dataIndexStatsQueryOptions,
      },
      {
        endpoint: "/api/v1/control/data/promotion/candidates",
        expected: promotionCandidatesPayload,
        getQueryKey: () => queryKeys.dataPromotionCandidates(),
        getStaleTime: () => RUNS_SAMPLE_STALE_MS,
        hook: useDataPromotionCandidates,
        queryOptions: dataPromotionCandidatesQueryOptions,
      },
    ] as const;

    for (const scenario of scenarios) {
      const getSpy = mockRuntimeGetSuccess(scenario.expected);
      const { result, unmount } = renderHook(() => scenario.hook(), {
        wrapper: createQueryHookWrapper(),
      });

      await waitFor(() => {
        expect(result.current.data).toEqual(scenario.expected);
      });

      expect(getSpy.mock.calls[0]?.[0]).toBe(scenario.endpoint);

      const options = scenario.queryOptions();
      expect(options.queryKey).toEqual(scenario.getQueryKey());
      expect(options.staleTime).toBe(scenario.getStaleTime());

      unmount();
      vi.restoreAllMocks();
    }
  });
});
