import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  capabilitySearchQueryOptions,
  fetchCapabilitySearch,
  useCapabilitySearch,
} from "@/api/hooks/useCapabilitySearch";
import { runtimeApiClient } from "@/api/client";
import { queryKeys } from "@/api/queryKeys";
import { createQueryHookHarness } from "@/test/queryHook";

const request = {
  audience: "REVIEWER" as const,
  resource_kinds: ["legal_norm"] as const,
  search: {
    allowed_modes: ["lexical"] as const,
    authority_purpose: "capability_discovery",
    construct_refs: [],
    intent: "capability_discovery",
    query_text: "housing",
    request_id: "capability-search-test",
    required_layers: [],
    rule_version: "policyos.test.v1",
    schema_version: "policyos.core.contracts.search.v1" as const,
  },
};

const response = {
  audience: "REVIEWER",
  authority_purpose: "capability_discovery",
  frontier: {
    actual_cutoff: null,
    candidates: [],
    completeness_status: "complete_no_match",
    corpus_kind: "fixture",
    corpus_path: "fixture://capabilities",
    corpus_ref: "fixture-capabilities",
    corpus_snapshot_hash: "snapshot",
    evaluated_count: 1,
    incompleteness_reasons: [],
    index_version_refs: ["epoch-42"],
    indexes_used: ["owner-index"],
    no_hit_frontier: ["housing"],
    query_expansion_traces: [],
    rejected_candidates: [],
    replay_command: "replay capability-search-test",
    replay_expected_output_hash: "output-hash",
    replay_key: "replay-key",
    request_ref: "request-ref",
    requested_count: 10,
    returned_count: 0,
    schema_version: "policyos.core.contracts.search.v1",
  },
  meta: {
    generated_at: "2026-08-26T00:00:00Z",
    request_id: "capability-search-test",
    source_kinds: ["core_run"],
  },
  provenance_refs: ["owner-index"],
  request,
  request_digest: "request-digest",
  results: [],
  rule_version: "policyos.test.v1",
  schema_version: "policyos.capability_discovery.v1",
  time: {
    freshness: "current",
    observed_at: "2026-08-26T00:00:00Z",
    valid_from: "2026-08-26T00:00:00Z",
    valid_until: null,
  },
};

describe("capability search hook", () => {
  afterEach(() => vi.restoreAllMocks());

  it("can defer an unopened search surface without changing its generic key", () => {
    const options = capabilitySearchQueryOptions(request, undefined, false);
    expect(options.enabled).toBe(false);
    expect(options.queryKey).toEqual(queryKeys.capabilitySearch(request));
  });

  it("uses the generic POST endpoint and captures exact bytes plus the server epoch", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify(response), {
          headers: { "Content-Type": "application/json" },
          status: 200,
        }),
      ),
    );
    const postSpy = vi
      .spyOn(runtimeApiClient, "POST")
      .mockImplementation(async (_path, options) => {
        const captured = await (
          options as { fetch: (request: Request) => Promise<Response> }
        ).fetch(
          new Request("http://runtime.test/api/v1/control/capabilities/search"),
        );
        return {
          data: response,
          error: undefined,
          response: captured,
        } as never;
      });
    const { queryClient, wrapper } = createQueryHookHarness();
    const { result } = renderHook(() => useCapabilitySearch(request), {
      wrapper,
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(postSpy).toHaveBeenCalledWith(
      "/api/v1/control/capabilities/search",
      {
        body: request,
        fetch: expect.any(Function),
        parseAs: "json",
      },
    );
    expect(result.current.data?.rawBytes).toBeInstanceOf(Uint8Array);
    expect(result.current.data?.serverEpoch).toBe("epoch-42");
    expect(
      queryClient.getQueryData(queryKeys.capabilitySearch(request)),
    ).toMatchObject({ response });
  });

  it("rejects a malformed discovery response before it reaches consumers", async () => {
    vi.spyOn(runtimeApiClient, "POST").mockResolvedValue({
      data: { ...response, schema_version: "wrong" },
      error: undefined,
      response: new Response(JSON.stringify(response), { status: 200 }),
    } as never);

    await expect(fetchCapabilitySearch(request)).rejects.toThrow();
  });
});
