import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { renderWithProviders } from "@/test/render";

import { BSTSVisualization } from "./BSTSVisualization";
import { RDDVisualization } from "./RDDVisualization";
import { SyntheticControlViz } from "./SyntheticControlViz";

describe("shared chart hardening", () => {
  it("does not mutate fitted line inputs when rendering RDD visualizations", () => {
    const fittedBelow = [
      { x: 2, y: 4 },
      { x: 1, y: 3 },
    ];
    const donorWeights = [
      { unit: "B", weight: 0.2 },
      { unit: "A", weight: 0.6 },
    ];

    renderWithProviders(
      <>
        <RDDVisualization
          cutoff={1.5}
          dataBelow={[{ x: 1, y: 2 }]}
          dataAbove={[{ x: 2, y: 3 }]}
          fittedBelow={fittedBelow}
          fittedAbove={[{ x: 2, y: 3 }]}
        />
        <SyntheticControlViz
          data={[
            { actual: 1, synthetic: 0.8, time: 1 },
            { actual: 1.2, synthetic: 1, time: 2 },
          ]}
          donorWeights={donorWeights}
          treatmentTime={2}
        />
      </>,
    );

    expect(fittedBelow).toEqual([
      { x: 2, y: 4 },
      { x: 1, y: 3 },
    ]);
    expect(donorWeights).toEqual([
      { unit: "B", weight: 0.2 },
      { unit: "A", weight: 0.6 },
    ]);
  });

  it("renders empty states instead of broken SVGs for empty datasets", () => {
    renderWithProviders(
      <>
        <RDDVisualization cutoff={0} dataBelow={[]} dataAbove={[]} />
        <SyntheticControlViz data={[]} treatmentTime={0} />
        <BSTSVisualization data={[]} interventionTime={0} />
      </>,
    );

    expect(screen.getAllByText("No data available.")).toHaveLength(3);
  });
});
