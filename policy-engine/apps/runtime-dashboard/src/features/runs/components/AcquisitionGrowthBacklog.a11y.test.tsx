import { render } from "@testing-library/react";
import { axe } from "vitest-axe";

import { LocaleProvider } from "@/shared/i18n/LocaleProvider";

import { AcquisitionGrowthBacklog } from "./AcquisitionGrowthBacklog";

describe("AcquisitionGrowthBacklog accessibility", () => {
  it("has no violations while disclosing ranking authority", async () => {
    const { container } = render(
      <LocaleProvider>
        <AcquisitionGrowthBacklog
          backlog={[
            {
              authority_boundary: "ranking_only_not_voi",
              binding_confidence: 0,
              classification_basis: "not_established",
              gap_class: "not_established",
              rank: 1,
              ranking_method: "interim_binding_confidence_x_route_demand",
              ranking_score: 0,
              route_demand: 1,
              variable_id: "residual.one",
              voi_owner_fit: "metric_residual_granularity_not_supported",
              voi_owner_integration: "routed_to_gy_n13b",
              voi_owner_ref:
                "polisyos.runtime.quality.acquisition_planner.plan_evidence_acquisition",
            },
          ]}
        />
      </LocaleProvider>,
    );

    expect((await axe(container)).violations).toHaveLength(0);
  });
});
