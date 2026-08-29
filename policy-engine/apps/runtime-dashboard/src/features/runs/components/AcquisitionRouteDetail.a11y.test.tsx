import { render } from "@testing-library/react";
import { axe } from "vitest-axe";

import { LocaleProvider } from "@/shared/i18n/LocaleProvider";

import { AcquisitionRouteDetail } from "./AcquisitionRouteDetail";

describe("AcquisitionRouteDetail accessibility", () => {
  it("has no violations for a structural refusal", async () => {
    const { container } = render(
      <LocaleProvider>
        <AcquisitionRouteDetail
          kind="structural"
          route={{
            action_eligibility: "not_applicable",
            gap_class: "structural_gap",
            missing_link: "owner_grounding_relation_missing",
            route_class: "not_a_data_gap",
            route_id: "capstone:education",
            witness_kind: "estimand_binding_refusal",
          }}
        />
      </LocaleProvider>,
    );

    expect((await axe(container)).violations).toHaveLength(0);
  });
});
