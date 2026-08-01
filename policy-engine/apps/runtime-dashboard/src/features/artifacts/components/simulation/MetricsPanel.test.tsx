import { screen } from "@testing-library/react";

import MetricsPanel from "@/features/artifacts/components/simulation/MetricsPanel";
import type { SimulationMetric } from "@/shared/lib/domain/simulation";
import { renderWithProviders } from "@/test/render";

describe("MetricsPanel", () => {
  it("renders metric quantity without local severity metadata", () => {
    const metric: SimulationMetric = {
      assumptionWarnings: [],
      ciLevel: null,
      ciLower: null,
      ciUpper: null,
      formatted: "+67.00",
      key: "observed",
      label: "Observed",
      unit: "%",
      value: 67,
    };

    const view = renderWithProviders(
      <MetricsPanel
        metricComparisons={[]}
        metricValidationFamilyAdjustment={null}
        metrics={[metric]}
        showUncertainty={false}
        timeSeries={[]}
      />,
    );

    expect(screen.getByText("+67.00 %")).toBeInTheDocument();
    expect(view.baseElement.innerHTML).not.toMatch(
      /data-(interaction-purpose|severity|intent)=/u,
    );
  });
});
