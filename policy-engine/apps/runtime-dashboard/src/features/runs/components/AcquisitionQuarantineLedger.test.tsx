import { render, screen } from "@testing-library/react";
import type { AcquisitionGrowthPayload } from "@polisyos/runtime-api-client";

import { LocaleProvider } from "@/shared/i18n/LocaleProvider";

import { AcquisitionQuarantineLedger } from "./AcquisitionQuarantineLedger";

function history(): AcquisitionGrowthPayload["n13b_history"] {
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

describe("AcquisitionQuarantineLedger", () => {
  it("keeps raw responses quarantined when no passport admission exists", () => {
    render(
      <LocaleProvider>
        <AcquisitionQuarantineLedger history={history()} />
      </LocaleProvider>,
    );

    const ledger = screen.getByTestId("acquisition-quarantine-ledger");
    expect(ledger).toHaveTextContent(/2 raw responses.*0 admitted/iu);
    expect(ledger).toHaveTextContent("raw_terminal");
    expect(ledger).toHaveTextContent("no_growth");
    expect(ledger).toHaveTextContent("deeper_terminal");
    expect(ledger).not.toHaveTextContent(/\bgrew\b/iu);
  });
});
