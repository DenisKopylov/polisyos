import { render, screen } from "@testing-library/react";

import { LocaleProvider } from "@/shared/i18n/LocaleProvider";

import { ConnectorAcquisitionScorecard } from "./ConnectorAcquisitionScorecard";

describe("ConnectorAcquisitionScorecard", () => {
  it("renders measured tier decay as degraded rather than healthy", () => {
    render(
      <LocaleProvider>
        <ConnectorAcquisitionScorecard
          carrierLiveness={{
            carrier_disposition: "carrier_current_source_profile_mismatch",
            connector_id: "worldbank.wdi",
            execution_tier: "transport_ready",
            tier_decay_findings: [
              "execution_tier_decay:transport_ready:carrier_current_source_profile_mismatch",
            ],
          }}
          familyCount={12}
        />
      </LocaleProvider>,
    );

    const card = screen.getByTestId("connector-acquisition-scorecard");
    expect(card).toHaveAttribute("data-connector-health", "degraded");
    expect(card).toHaveTextContent("carrier_current_source_profile_mismatch");
    expect(card).toHaveTextContent("transport_ready");
    expect(card).not.toHaveTextContent(/healthy/iu);
  });
});
