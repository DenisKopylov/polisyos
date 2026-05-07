import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { queryKeys } from "@/api/queryKeys";
import { createQueryHookWrapper } from "@/test/queryHook";
import { mockRuntimeGetSuccess } from "@/test/runtimeApi";

import {
  runFabricDecisionDataQueryOptions,
  useRunFabricDecisionData,
} from "./useRunFabricDecisionData";

const runId = "R_core_api_001";
const payload = {
  meta: {
    generated_at: "2026-02-11T12:00:00Z",
    request_id: "req_fixture",
    source_kinds: ["core_run"],
  },
  run_id: runId,
  source_kind: "core_run",
  temporal_scope: null,
  decision_data: [
    {
      id: "fabric_decision_data:policy_cost",
      kind: "quantity",
      value: {
        label: "Policy cost",
        metric_id: "policy_cost",
        point: 100,
        unit: { code: "[USD]", display: "USD", system: "ucum" },
      },
      source_contract: { id: "worldbank.wdi.generic", version: "1.1.0" },
      quality: { status: "passed", score: 1 },
      lineage: {
        id: "lin_policy_cost",
        status: "verified",
        hash: "sha256:abc",
      },
      access: {
        classification: "public",
        pii_tier: "none",
        redaction: "none",
        tenant_scope: "shared_public",
      },
      time: null,
      replay: { status: "replayable" },
      gaps: [],
      metadata: { quantity_class: "decision" },
    },
  ],
};

afterEach(() => {
  vi.restoreAllMocks();
});

describe("useRunFabricDecisionData", () => {
  it("loads Fabric envelopes and exposes renderable quantities", async () => {
    const getSpy = mockRuntimeGetSuccess(payload);
    const { result } = renderHook(() => useRunFabricDecisionData(runId), {
      wrapper: createQueryHookWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data?.decision_data).toHaveLength(1);
    expect(result.current.data?.quantities[0]?.metric_id).toBe("policy_cost");
    expect(
      result.current.data?.quantities[0]?.lineage.trust_metadata,
    ).toMatchObject({
      verification_method: "fabric_trust_envelope",
      verification_status: "verified",
    });
    expect(getSpy).toHaveBeenCalledWith(
      "/api/v1/runs/{run_id}/fabric-decision-data",
      {
        params: {
          path: { run_id: runId },
          query: {},
        },
      },
    );
  });

  it("uses a temporal cache key for Fabric decision data", () => {
    const temporalScope = { validAt: "2026-02-11T12:00:00Z" };

    expect(
      runFabricDecisionDataQueryOptions(runId, temporalScope).queryKey,
    ).toEqual(queryKeys.runFabricDecisionData(runId, temporalScope));
  });
});
