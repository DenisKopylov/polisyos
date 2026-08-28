import { render } from "@testing-library/react";
import { axe } from "vitest-axe";
import type { AcquisitionRouteProjection } from "@polisyos/runtime-api-client";

import { LocaleProvider } from "@/shared/i18n/LocaleProvider";

import { AcquisitionExecutionTimeline } from "./AcquisitionExecutionTimeline";

describe("AcquisitionExecutionTimeline accessibility", () => {
  it("has no violations for the honest pending-production state", async () => {
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
        source_job_id: "job-source",
        terminal_event_id: "event-terminal",
      },
      route_id: hash,
      route_projection_hash: hash,
      route_status: "costed_actionable",
      run_id: "run-1",
      schema_version: "AcquisitionRouteProjection@1.0",
      tenant_id: "tenant-1",
      world_growth: "no_growth",
    } satisfies AcquisitionRouteProjection;
    const { container } = render(
      <LocaleProvider>
        <AcquisitionExecutionTimeline route={route} />
      </LocaleProvider>,
    );

    expect((await axe(container)).violations).toHaveLength(0);
  });
});
