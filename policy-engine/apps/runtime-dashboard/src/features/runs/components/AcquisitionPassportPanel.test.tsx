import { render, screen } from "@testing-library/react";
import type { AcquisitionGrowthPayload } from "@polisyos/runtime-api-client";

import { LocaleProvider } from "@/shared/i18n/LocaleProvider";

import { AcquisitionPassportPanel } from "./AcquisitionPassportPanel";

function negativeAcquisitionHistory(): AcquisitionGrowthPayload["n13b_history"] {
  return {
    admission: "not_reached",
    attempt_count: 5,
    epoch_qualification: {
      appointment_state: "unappointed",
      appointment_would_establish:
        "authority to qualify native semantic production, append its history head and permit overlay activation",
      appointment_would_not_establish: [
        "gap shape",
        "passport validity",
        "positive delta",
        "re-entry",
      ],
      authority_owner_ref: null,
      authority_role: "semantic epoch policy-admission qualifier",
      code: "policy_admission_missing",
      epoch_state: "pending_epoch_activation",
      status: "not_established",
    },
    execution_phase: "terminal",
    overlay_epoch_count: 0,
    quarantine: "raw_terminal",
    quarantine_count: 2,
    raw_response_count: 2,
    reentry: "deeper_terminal",
    response_admitted_count: 0,
    terminal_count: 5,
    world_growth: "no_growth",
  };
}

describe("AcquisitionPassportPanel", () => {
  it("renders the pending institutional qualification disclosure without upgrade copy", () => {
    render(
      <LocaleProvider>
        <AcquisitionPassportPanel history={negativeAcquisitionHistory()} />
      </LocaleProvider>,
    );

    const panel = screen.getByTestId("acquisition-passport-panel");
    expect(panel).toHaveTextContent("pending_epoch_activation");
    expect(panel).toHaveTextContent("not_established");
    expect(panel).toHaveTextContent("policy_admission_missing");
    expect(panel).toHaveTextContent(
      /unappointed.*semantic epoch policy-admission qualifier/iu,
    );
    expect(panel).toHaveTextContent(
      /authority to qualify native semantic production/iu,
    );
    expect(panel).toHaveTextContent("positive delta");
    expect(panel).not.toHaveTextContent(/\bactive\b|\bqualified\b/iu);
  });
});
