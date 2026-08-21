import { onlineManager, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { createElement, type ReactNode } from "react";
import { afterEach, describe, expect, it } from "vitest";

type Packet = Readonly<{
  meta?: Readonly<{ generated_at: string }>;
  source?: Readonly<{ as_of: string }>;
  packet?: Readonly<{ as_of?: unknown }>;
}>;

function createWrapper(queryClient: QueryClient) {
  return function QueryWrapper({ children }: { children: ReactNode }) {
    return createElement(QueryClientProvider, { client: queryClient }, children);
  };
}

describe("governed query policy", () => {
  afterEach(() => {
    onlineManager.setOnline(true);
  });

  it("test_governed_query_wrapper_forbids_retained_authority_without_owner_as_of", async () => {
    const policyModule = await import("./governedQueryPolicy").catch(() => null);

    // This assertion is intentionally the named RED witness while the wrapper
    // does not exist. The remaining assertions run only once it is available.
    expect(policyModule).not.toBeNull();
    if (!policyModule) {
      return;
    }

    const { governedQueryOptions, useGovernedQuery } = policyModule;
    const policy = {
      kind: "owner_as_of" as const,
    };
    const invalidPackets: Packet[] = [
      {},
      { meta: { generated_at: "2026-08-10T10:00:00Z" } },
      { source: { as_of: "2026-08-10T10:00:00Z" } },
      {
        meta: { generated_at: "2026-08-10T10:00:00Z" },
        source: { as_of: "2026-08-10T10:00:00Z" },
      },
      { packet: { as_of: "not-an-owner-time" } },
      { packet: { as_of: "2026-02-30T10:00:00Z" } },
      { packet: { as_of: "2026-08-10T10:00:00+99:99" } },
    ];

    for (const [index, packet] of invalidPackets.entries()) {
      const queryClient = new QueryClient({
        defaultOptions: { queries: { gcTime: Infinity, retry: false } },
      });
      const options = governedQueryOptions(
        {
          queryKey: ["invalid-owner-as-of", index] as const,
          queryFn: async () =>
            packet as unknown as Readonly<{ packet: Readonly<{ as_of: unknown }> }>,
        },
        policy,
      );
      const { result } = renderHook(() => useGovernedQuery(options), {
        wrapper: createWrapper(queryClient),
      });

      await waitFor(() => {
        expect(result.current.isError).toBe(true);
      });
      expect(queryClient.getQueryData(options.queryKey)).toBeUndefined();
    }

    const validClient = new QueryClient({
      defaultOptions: { queries: { gcTime: Infinity, retry: false } },
    });
    const validPacket = { packet: { as_of: "2026-08-10T10:00:00Z" } };
    const validOptions = governedQueryOptions(
      { queryKey: ["valid-owner-as-of"] as const, queryFn: async () => validPacket },
      policy,
    );
    const { result: validResult } = renderHook(() => useGovernedQuery(validOptions), {
      wrapper: createWrapper(validClient),
    });
    await waitFor(() => {
      expect(validResult.current.data).toEqual(validPacket);
    });

    expect(() =>
      governedQueryOptions(
        {
          queryKey: ["forbidden-infinite-stale"] as const,
          queryFn: async () => validPacket,
          staleTime: Infinity,
        },
        policy,
      ),
    ).toThrow(/retention/u);

    const neverCacheClient = new QueryClient({
      defaultOptions: { queries: { gcTime: Infinity, retry: false } },
    });
    let failRefetch = false;
    const neverCacheOptions = governedQueryOptions(
      {
        queryKey: ["never-cache-authority"] as const,
        queryFn: async () => {
          if (failRefetch) {
            throw new Error("refetch failed");
          }
          return { authority: "packet" };
        },
      },
      { kind: "never_cache_authority" as const },
    );
    expect(neverCacheOptions.gcTime).toBe(0);
    expect(neverCacheOptions.initialData).toBeUndefined();
    expect(neverCacheOptions.placeholderData).toBeUndefined();
    expect(Object.isFrozen(neverCacheOptions)).toBe(true);
    function issuedMutationWitness() {
      // @ts-expect-error issued never-cache retention is immutable.
      neverCacheOptions.gcTime = Infinity;
    }
    void issuedMutationWitness;
    const spreadNeverCacheOptions = {
      ...neverCacheOptions,
      gcTime: Infinity,
      initialData: { authority: "forged" },
      staleTime: Infinity,
    };
    // @ts-expect-error a spread cannot retain the issued never-cache policy.
    const spreadBypassWitness: Parameters<typeof useGovernedQuery>[0] =
      spreadNeverCacheOptions;
    void spreadBypassWitness;
    expect(() =>
      renderHook(() =>
        useGovernedQuery(
          spreadNeverCacheOptions as unknown as typeof neverCacheOptions,
        ),
      ),
    ).toThrow(/unissued/u);
    const { result: neverCacheResult } = renderHook(
      () => useGovernedQuery(neverCacheOptions),
      { wrapper: createWrapper(neverCacheClient) },
    );
    await waitFor(() => {
      expect(neverCacheResult.current.data).toEqual({ authority: "packet" });
    });
    await act(async () => {
      onlineManager.setOnline(false);
      await neverCacheResult.current.refetch();
    });
    await waitFor(() => {
      expect(neverCacheClient.getQueryCache().find({ queryKey: neverCacheOptions.queryKey })).toBeUndefined();
    });
    onlineManager.setOnline(true);

    const refetchClient = new QueryClient({
      defaultOptions: { queries: { gcTime: Infinity, retry: false } },
    });
    failRefetch = false;
    const failedRefetchOptions = governedQueryOptions(
      {
        queryKey: ["failed-never-cache-refetch"] as const,
        queryFn: async () => {
          if (failRefetch) {
            throw new Error("refetch failed");
          }
          return { authority: "packet" };
        },
      },
      { kind: "never_cache_authority" as const },
    );
    const { result: failedRefetchResult } = renderHook(
      () => useGovernedQuery(failedRefetchOptions),
      { wrapper: createWrapper(refetchClient) },
    );
    await waitFor(() => {
      expect(failedRefetchResult.current.data).toEqual({ authority: "packet" });
    });
    failRefetch = true;
    await act(async () => {
      await failedRefetchResult.current.refetch();
    });
    await waitFor(() => {
      expect(refetchClient.getQueryCache().find({ queryKey: failedRefetchOptions.queryKey })).toBeUndefined();
    });

    const operational = governedQueryOptions(
      {
        initialData: { control: true },
        queryKey: ["operational-control"] as const,
        queryFn: async () => ({ control: true }),
        staleTime: Infinity,
      },
      { kind: "operational" as const },
    );
    expect(operational.initialData).toEqual({ control: true });
    expect(operational.staleTime).toBe(Infinity);

    const rawNeverCacheOptions = {
      gcTime: Infinity,
      initialData: { authority: "unissued" },
      policy: { kind: "never_cache_authority" as const },
      queryKey: ["structural-bypass"] as const,
      queryFn: async () => ({ authority: "unissued" }),
    };
    // @ts-expect-error raw structural options must never enter the governed hook.
    const structuralBypassWitness: Parameters<typeof useGovernedQuery>[0] =
      rawNeverCacheOptions;
    void structuralBypassWitness;
  });
});
