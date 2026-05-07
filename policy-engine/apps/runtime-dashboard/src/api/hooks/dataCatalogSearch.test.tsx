import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { useDataCatalogSearch } from "@/api/hooks/useDataCatalogSearch";
import { queryKeys } from "@/api/queryKeys";
import {
  createQueryHookHarness,
  createQueryHookWrapper,
} from "@/test/queryHook";
import {
  mockRuntimeGetFailure,
  mockRuntimeGetSuccess,
} from "@/test/runtimeApi";

describe("data catalog search hook", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("trims the metric query and calls the catalog search endpoint with params", async () => {
    const payload = {
      candidates: [
        {
          connector_id: "world-bank",
          dataset_id: "inflation-dataset",
          metric_id: "inflation",
        },
      ],
    };
    const getSpy = mockRuntimeGetSuccess(payload);
    const { queryClient, wrapper } = createQueryHookHarness();
    const { result } = renderHook(
      () =>
        useDataCatalogSearch({
          geography: "CA",
          limit: 10,
          metricQuery: "  inflation  ",
        }),
      {
        wrapper,
      },
    );

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.data).toEqual(payload);
    expect(
      queryClient.getQueryData(
        queryKeys.dataCatalogSearch("inflation", "CA", 10),
      ),
    ).toEqual(payload);
    expect(
      queryClient.getQueryState(
        queryKeys.dataCatalogSearch("inflation", "CA", 10),
      )?.status,
    ).toBe("success");
    expect(getSpy).toHaveBeenCalledWith("/api/v1/control/data/catalog/search", {
      params: {
        query: {
          geo: "CA",
          limit: 10,
          metric: "inflation",
        },
      },
    });
  });

  it("stays idle for blank queries or explicit disable", () => {
    const getSpy = mockRuntimeGetSuccess({ candidates: [] });

    const { result: blankResult } = renderHook(
      () =>
        useDataCatalogSearch({
          metricQuery: "   ",
        }),
      {
        wrapper: createQueryHookWrapper(),
      },
    );
    const { result: disabledResult } = renderHook(
      () =>
        useDataCatalogSearch({
          enabled: false,
          metricQuery: "inflation",
        }),
      {
        wrapper: createQueryHookWrapper(),
      },
    );

    expect(blankResult.current.fetchStatus).toBe("idle");
    expect(disabledResult.current.fetchStatus).toBe("idle");
    expect(getSpy).not.toHaveBeenCalled();
  });

  it("surfaces runtime API errors when search fails", async () => {
    mockRuntimeGetFailure(500, {
      code: "catalog_search_failed",
      detail: "Search failed",
      status: 500,
    });
    const { result } = renderHook(
      () =>
        useDataCatalogSearch({
          metricQuery: "inflation",
        }),
      {
        wrapper: createQueryHookWrapper(),
      },
    );

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });

    expect(result.current.error).toMatchObject({
      code: "catalog_search_failed",
      status: 500,
    });
  });
});
