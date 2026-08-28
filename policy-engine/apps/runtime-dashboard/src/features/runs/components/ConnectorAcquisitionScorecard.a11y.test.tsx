import { render } from "@testing-library/react";
import { axe } from "vitest-axe";

import { LocaleProvider } from "@/shared/i18n/LocaleProvider";

import { ConnectorAcquisitionScorecard } from "./ConnectorAcquisitionScorecard";

describe("ConnectorAcquisitionScorecard accessibility", () => {
  it("has no violations while showing tier decay", async () => {
    const { container } = render(
      <LocaleProvider>
        <ConnectorAcquisitionScorecard
          carrierLiveness={{
            carrier_disposition: "carrier_current_source_profile_mismatch",
            connector_id: "worldbank.wdi",
            execution_tier: "transport_ready",
            tier_decay_findings: ["execution_tier_decay:transport_ready"],
          }}
          familyCount={12}
        />
      </LocaleProvider>,
    );

    expect((await axe(container)).violations).toHaveLength(0);
  });
});
