import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { useScenarioManifest } from "@/api/hooks/useScenarioManifest";
import { createQueryHookWrapper } from "@/test/queryHook";
import { mockRuntimeGetSuccess } from "@/test/runtimeApi";

const meta = {
  generated_at: "2026-04-16T09:20:00Z",
  request_id: "req-scenario",
  source_kinds: ["core_run"],
};

const temporalScope = {
  branch: "main",
  scenarioId: "scn_rate_cut_25bps",
  snapshotId: "snap_wave2",
  txAt: "2026-04-16T09:20:00Z",
  validAt: "2026-04-15T12:00:00Z",
};

const apiTemporalScope = {
  branch: "main",
  scenario_id: "scn_rate_cut_25bps",
  snapshot_id: "snap_wave2",
  tx_at: "2026-04-16T09:20:00Z",
  valid_at: "2026-04-15T12:00:00Z",
};

const lineage = {
  freshness: "current",
  hash: "sha256:scenario",
  id: "lin_scenario",
  status: "verified",
};

const quantity = {
  lineage,
  metric_id: "policy_rate",
  point: 0.25,
  quantity_class: "decision",
  time: apiTemporalScope,
  unit: {
    code: "%",
    display: "percent",
    system: "ucum",
  },
};

const manifestPayload = {
  meta,
  scenario: {
    affected_population: "national_workforce",
    assumptions: [
      {
        id: "asm_no_external_shock",
        label: "No external shock",
        lineage,
        status: "operator_assumption",
      },
    ],
    author: "PolicyOS",
    baseline_hash: "sha256:baseline",
    baseline_lineage: lineage,
    baseline_run_id: "run_actual",
    constraints: [],
    interventions: [
      {
        field: "policy_rate",
        operator: "set",
        value: quantity,
      },
    ],
    known_limitations: [],
    lifecycle_status: "saved",
    manifest_hash: "sha256:manifest",
    model_family: "counterfactual_fixture",
    model_lineage: lineage,
    policy_question: "What if rates move?",
    revision: 1,
    stale_reasons: [],
    status: "computed",
    temporal_scope: apiTemporalScope,
    temporal_window: {
      earliest: "2026-04-15T12:00:00Z",
      latest: "2026-04-16T09:20:00Z",
    },
    validity_window: {
      earliest: "2026-04-15T12:00:00Z",
      latest: "2026-04-16T09:20:00Z",
    },
  },
  temporal_scope: apiTemporalScope,
};

describe("useScenarioManifest", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("sends the same temporal scope used by the query identity", async () => {
    const getSpy = mockRuntimeGetSuccess(manifestPayload);
    renderHook(
      () =>
        useScenarioManifest("scn_rate_cut_25bps", {
          temporalScope,
        }),
      { wrapper: createQueryHookWrapper() },
    );

    await waitFor(() => {
      expect(getSpy).toHaveBeenCalled();
    });

    expect(getSpy).toHaveBeenCalledWith("/api/v1/scenarios/{scenario_id}", {
      params: {
        path: {
          scenario_id: "scn_rate_cut_25bps",
        },
        query: {
          branch: "main",
          snapshot_id: "snap_wave2",
          tx_at: "2026-04-16T09:20:00.000Z",
          valid_at: "2026-04-15T12:00:00.000Z",
        },
      },
    });
  });
});
