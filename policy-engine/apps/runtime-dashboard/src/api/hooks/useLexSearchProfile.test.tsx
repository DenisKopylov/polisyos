import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { queryKeys } from "@/api/queryKeys";
import { createQueryHookWrapper } from "@/test/queryHook";
import { mockRuntimeGetSuccess } from "@/test/runtimeApi";

import {
  lexSearchProfileQueryOptions,
  useLexSearchProfile,
} from "./useLexSearchProfile";

const outputDir = "/tmp/legal-search-profile";
const profilePayload = {
  meta: {
    generated_at: "2026-10-09T00:00:00Z",
    request_id: "req-legal-profile",
    source_kinds: [],
  },
  status: "available",
  output_dir: outputDir,
  query_generation_intent: [
    {
      basis_kind: "legal_lex_facts_embedding",
      generation_id: "a".repeat(32),
      inventory_json: '{"basis":{"basis_kind":"legal_lex_facts_embedding"}}',
    },
  ],
};

afterEach(() => {
  vi.restoreAllMocks();
});

describe("useLexSearchProfile", () => {
  it("reads the selected snapshot for the exact output directory", async () => {
    const getSpy = mockRuntimeGetSuccess(profilePayload);
    const { result } = renderHook(() => useLexSearchProfile(outputDir), {
      wrapper: createQueryHookWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.data).toMatchObject({
      output_dir: outputDir,
      query_generation_intent: profilePayload.query_generation_intent,
      status: "available",
    });
    expect(getSpy).toHaveBeenCalledWith("/api/v1/control/lex/search-profile", {
      params: { query: { output_dir: outputDir } },
    });
    expect(lexSearchProfileQueryOptions(outputDir).queryKey).toEqual(
      queryKeys.lexSearchProfile(outputDir),
    );
  });
});
