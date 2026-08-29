import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { AcquisitionBacklogProjection } from "@polisyos/runtime-api-client";

import { LocaleProvider } from "@/shared/i18n/LocaleProvider";

import { AcquisitionGrowthBacklog } from "./AcquisitionGrowthBacklog";

function row(
  variableId: string,
  rank: number,
  routeDemand: number,
): AcquisitionBacklogProjection {
  return {
    authority_boundary: "ranking_only_not_voi",
    binding_confidence: 0,
    classification_basis: "not_established",
    gap_class: "not_established",
    rank,
    ranking_method: "interim_binding_confidence_x_route_demand",
    ranking_score: 0,
    route_demand: routeDemand,
    variable_id: variableId,
    voi_owner_fit: "metric_residual_granularity_not_supported",
    voi_owner_integration: "routed_to_gy_n13b",
    voi_owner_ref:
      "polisyos.runtime.quality.acquisition_planner.plan_evidence_acquisition",
  };
}

describe("AcquisitionGrowthBacklog", () => {
  it("discloses the zero-score basis and named VOI owner refusal", () => {
    render(
      <LocaleProvider>
        <AcquisitionGrowthBacklog
          backlog={[row("z.variable", 1, 1), row("a.variable", 2, 2)]}
        />
      </LocaleProvider>,
    );

    const board = screen.getByTestId("acquisition-growth-backlog");
    expect(board).toHaveTextContent(/2 of 2 ranking scores are 0\.0/iu);
    expect(board).toHaveTextContent(/ranking only, not VOI/iu);
    expect(board).toHaveTextContent(
      "metric_residual_granularity_not_supported",
    );
    expect(board).toHaveTextContent(
      "polisyos.runtime.quality.acquisition_planner.plan_evidence_acquisition",
    );
  });

  it("labels local ordering without changing source ordinals", async () => {
    const user = userEvent.setup();
    render(
      <LocaleProvider>
        <AcquisitionGrowthBacklog
          backlog={[row("z.variable", 1, 1), row("a.variable", 2, 2)]}
        />
      </LocaleProvider>,
    );

    await user.selectOptions(
      screen.getByLabelText(/view order/iu),
      "variable_id",
    );
    expect(screen.getByText("local_order_override")).toBeInTheDocument();
    const renderedRows = screen.getAllByRole("listitem");
    expect(renderedRows.map((item) => item.dataset.variableId)).toEqual([
      "a.variable",
      "z.variable",
    ]);
    expect(within(renderedRows[0]!).getByText("2")).toBeInTheDocument();
  });
});
