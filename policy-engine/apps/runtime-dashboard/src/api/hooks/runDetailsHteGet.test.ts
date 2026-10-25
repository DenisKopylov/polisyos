import { r5RunHteSelectedProjection } from "@/features/runs/domain/__test__/runExecutionHteFixtures";
import { mockRuntimeGetSuccess } from "@/test/runtimeApi";
import { runDetailsQueryOptions } from "./useRunDetails";

describe("RunDetails GET with a synthetic DTO response", () => {
  it("parses the synthetic R5 projection fixture, not producer evidence", async () => {
    const runId = "run-hte-fixture";
    const payload = {
      meta: {
        generated_at: "2026-10-21T12:00:00Z",
        request_id: "req-hte",
        source_kinds: ["core_run"],
      },
      run: {
        run_id: runId,
        source_kind: "core_run",
        status: "completed",
        method_execution_selection: r5RunHteSelectedProjection(),
      },
    };
    const getSpy = mockRuntimeGetSuccess(payload);
    const result = await runDetailsQueryOptions(runId).queryFn();

    expect(getSpy).toHaveBeenCalledWith(
      "/api/v1/runs/{run_id}",
      expect.objectContaining({
        params: expect.objectContaining({
          path: { run_id: runId },
        }),
      }),
    );
    expect(result.run.method_execution_selection?.selection?.hte).toMatchObject(
      {
        kind: "point_estimate",
        point_estimate: 0.42,
        materialization_binding_ref: {
          kind: "foundry.hte.physical_source_materialization_binding",
        },
        resource_evidence: { owner_policy_revision: "r5" },
        target_relation: {
          estimand_status: "not_established",
          overall_disposition: "not_established",
        },
      },
    );
  });
});
