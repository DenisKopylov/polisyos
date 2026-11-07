import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { queryKeys } from "@/api/queryKeys";
import { createQueryHookHarness } from "@/test/queryHook";
import {
  mockRuntimeGetSuccess,
  mockRuntimePostSuccess,
} from "@/test/runtimeApi";

import {
  createNullablePredictiveCalibrationResponseFixture,
  predictiveCalibrationResponseFixture as response,
  predictiveCalibrationRunId as runId,
  responseWithoutSelectedRunManifestProfile,
  responseWithUnknownAssociationAuthority,
} from "@/test/fixtures/predictiveCalibrationResponse";

import {
  runPredictiveCalibrationQueryOptions,
  useCreateRunPredictiveCalibration,
  useRunPredictiveCalibration,
} from "./useRunPredictiveCalibration";

afterEach(() => {
  vi.restoreAllMocks();
});

const readableResponses = [
  { label: "historical v2", payload: response },
  {
    label: "nullable v5",
    payload: createNullablePredictiveCalibrationResponseFixture(),
  },
];

describe("run predictive calibration API hooks", () => {
  it.each(readableResponses)(
    "loads exact selected refs and bounded status from the fresh run endpoint ($label)",
    async ({ payload }) => {
      const getSpy = mockRuntimeGetSuccess(payload);
      const harness = createQueryHookHarness();
      const { result } = renderHook(() => useRunPredictiveCalibration(runId), {
        wrapper: harness.wrapper,
      });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));
      expect(result.current.data?.association.assessment).toBe("limited");
      expect(
        result.current.data?.association.counterfactual_credibility_status,
      ).toBe("not_established");
      expect(result.current.data?.association.empirical_evidence_ref).toEqual(
        payload.association.empirical_evidence_ref,
      );
      expect(result.current.data?.association.schema_version).toBe(
        payload.association.schema_version,
      );
      expect(result.current.data?.association.observed_hit_rate).toBe(
        payload.association.observed_hit_rate,
      );
      expect(getSpy).toHaveBeenCalledWith(
        "/api/v1/runs/{run_id}/predictive-calibration",
        { params: { path: { run_id: runId } } },
      );
      expect(runPredictiveCalibrationQueryOptions(runId).queryKey).toEqual(
        queryKeys.runPredictiveCalibration(runId),
      );
    },
  );

  it("rejects a fresh GET whose selected Core manifest profile is missing", async () => {
    mockRuntimeGetSuccess(responseWithoutSelectedRunManifestProfile());
    const harness = createQueryHookHarness();
    const { result } = renderHook(() => useRunPredictiveCalibration(runId), {
      wrapper: harness.wrapper,
    });

    await waitFor(() => expect(result.current.isError).toBe(true));
  });

  it.each(readableResponses)(
    "posts an explicit typed candidate request and invalidates the fresh reader ($label)",
    async ({ payload }) => {
      const getSpy = mockRuntimeGetSuccess(payload);
      const postSpy = mockRuntimePostSuccess(payload);
      const harness = createQueryHookHarness();
      const reader = renderHook(() => useRunPredictiveCalibration(runId), {
        wrapper: harness.wrapper,
      });
      await waitFor(() => expect(reader.result.current.isSuccess).toBe(true));

      const writer = renderHook(
        () => useCreateRunPredictiveCalibration(runId),
        {
          wrapper: harness.wrapper,
        },
      );
      const request = {
        intent_id: "intent-fixture",
        candidate_source_ref: response.association.candidate_source_ref,
        observed_source_ref: response.association.observed_source_ref,
        model_spec_ref: response.association.model_spec_ref,
        policy_spec_ref: response.association.policy_spec_ref,
        calibration_rule_ref: response.association.calibration_rule_ref,
        calibration_threshold: 0.9,
        split: {
          train_start: 0,
          train_end: 10,
          holdout_start: 10,
          holdout_end: 14,
          horizon: 4,
        },
        target_metric: "policy_outcome",
        method_params: { horizon: 4, alpha: 0.1, beta: 0.1 },
        temporal_roles: {
          data_valid_time: "2026-10-01T00:00:00Z",
          calibration_window_start: "2026-10-02T00:00:00Z",
          calibration_window_end: "2026-10-03T00:00:00Z",
          policy_effective_time: "2026-10-04T00:00:00Z",
          prediction_time: "2026-10-05T00:00:00Z",
          observation_time: "2026-10-06T00:00:00Z",
        },
        seed: 17,
      } as const;

      await act(async () => {
        const created = await writer.result.current.mutateAsync(request);
        expect(created.association.schema_version).toBe(
          payload.association.schema_version,
        );
        expect(created.association.observed_hit_rate).toBe(
          payload.association.observed_hit_rate,
        );
      });
      await waitFor(() => expect(getSpy).toHaveBeenCalledTimes(2));
      expect(reader.result.current.data?.association.schema_version).toBe(
        payload.association.schema_version,
      );
      expect(reader.result.current.data?.association.observed_hit_rate).toBe(
        payload.association.observed_hit_rate,
      );
      expect(postSpy).toHaveBeenCalledWith(
        "/api/v1/runs/{run_id}/predictive-calibration",
        {
          params: { path: { run_id: runId } },
          body: request,
        },
      );

      const invalidResponse = responseWithUnknownAssociationAuthority();
      postSpy.mockResolvedValue({
        data: invalidResponse,
        error: undefined,
        response: new Response(JSON.stringify(invalidResponse), {
          headers: { "Content-Type": "application/json" },
          status: 201,
        }),
      } as never);
      await act(async () => {
        await expect(
          writer.result.current.mutateAsync(request),
        ).rejects.toThrow();
      });
    },
  );
});
