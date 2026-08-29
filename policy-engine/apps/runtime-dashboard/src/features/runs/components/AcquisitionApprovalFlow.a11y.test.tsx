import { render } from "@testing-library/react";
import { axe } from "vitest-axe";
import type { AcquisitionRouteProjection } from "@polisyos/runtime-api-client";
import { MemoryRouter } from "react-router-dom";

import { LocaleProvider } from "@/shared/i18n/LocaleProvider";

const mocks = vi.hoisted(() => ({
  useAcquisitionGrowth: vi.fn(),
  useAcquisitionRoute: vi.fn(),
  useControlJobStatus: vi.fn(),
  useHumanDecisionGate: vi.fn(),
}));

vi.mock("@/api/hooks/useControlJobStatus", () => ({
  useControlJobStatus: (...args: unknown[]) =>
    mocks.useControlJobStatus(...args),
}));
vi.mock("@/features/runs/api/useAcquisitionRoutes", () => ({
  executeAcquisitionRoute: vi.fn(),
  requestAcquisitionDecision: vi.fn(),
  useAcquisitionGrowth: () => mocks.useAcquisitionGrowth(),
  useAcquisitionRoute: () => mocks.useAcquisitionRoute(),
}));
vi.mock("@/features/runs/api/useHumanDecisions", () => ({
  fetchHumanDecisionEvidence: vi.fn(),
  useCreateHumanDecision: () => ({ mutateAsync: vi.fn() }),
  useHumanDecisionGate: (...args: unknown[]) =>
    mocks.useHumanDecisionGate(...args),
  withoutHumanDecisionOwnedQuery: () => "",
}));

import { AcquisitionApprovalFlow } from "./AcquisitionApprovalFlow";

describe("AcquisitionApprovalFlow accessibility", () => {
  it("has no violations before review is requested", async () => {
    const hash = `sha256:${"a".repeat(64)}`;
    const route = {
      authority_badge: "behavioral_fixture_not_production",
      authority_capability: "ready",
      cell_id: "cell-1",
      cost_basis: {
        record_content_hash: hash,
        schema_version: "AcquisitionCostBasisRecord@1.0",
        total_amount: 100,
      },
      execution_capability: "ready",
      external_nonclosures: [],
      planner_record_id: "plan-1",
      planner_report_hash: hash,
      qualification_predicate: "not_established",
      qualification_reason: "policy_admission_missing",
      qualification_status: "pending_epoch_activation",
      recommended_strategy: "survey",
      replay_pins: {
        compiled_content_hash: hash,
        compiled_ref: hash,
        cost_basis_hash: hash,
        design_problem_ref: hash,
        source_job_id: "source-job-1",
        terminal_event_id: "terminal-event-1",
      },
      route_id: hash,
      route_projection_hash: hash,
      route_status: "costed_actionable",
      run_id: "run-1",
      schema_version: "AcquisitionRouteProjection@1.0",
      tenant_id: "tenant-1",
      world_growth: "no_growth",
    } satisfies AcquisitionRouteProjection;
    mocks.useAcquisitionRoute.mockReturnValue({
      data: { packet: route, rawPacketBytes: new TextEncoder().encode("{}") },
      refetch: vi.fn(),
    });
    mocks.useAcquisitionGrowth.mockReturnValue({
      data: undefined,
      refetch: vi.fn(),
    });
    mocks.useControlJobStatus.mockReturnValue({ data: undefined });
    mocks.useHumanDecisionGate.mockReturnValue({
      clear: vi.fn(),
      data: undefined,
      hasSelector: false,
      isError: false,
      isLoading: false,
      revalidate: vi.fn(),
    });

    const { container } = render(
      <LocaleProvider>
        <MemoryRouter>
          <AcquisitionApprovalFlow canMutate route={route} />
        </MemoryRouter>
      </LocaleProvider>,
    );

    expect((await axe(container)).violations).toHaveLength(0);
  });
});
