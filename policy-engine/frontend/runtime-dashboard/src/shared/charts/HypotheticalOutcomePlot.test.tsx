import { render, screen } from "@testing-library/react";

const reducedMotionMock = vi.hoisted(() => vi.fn());

vi.mock("motion/react", () => ({
  useReducedMotion: () => reducedMotionMock(),
}));

import { HypotheticalOutcomePlot } from "@/shared/charts/HypotheticalOutcomePlot";

const samples = [
  {
    id: "sample-a",
    points: [
      { x: "Q1", y: 10 },
      { x: "Q2", y: 11 },
      { x: "Q3", y: 13 },
    ],
  },
  {
    id: "sample-b",
    points: [
      { x: "Q1", y: 9 },
      { x: "Q2", y: 12 },
      { x: "Q3", y: 14 },
    ],
  },
];

describe("HypotheticalOutcomePlot", () => {
  beforeEach(() => {
    reducedMotionMock.mockReturnValue(false);
  });

  it("renders animated sample realizations by default", () => {
    render(<HypotheticalOutcomePlot label="Outcome plot" samples={samples} />);
    expect(screen.getByText("Outcome plot")).toBeInTheDocument();
    expect(screen.getByText("2.0 fps")).toBeInTheDocument();
  });

  it("falls back automatically when reduced motion is preferred", () => {
    reducedMotionMock.mockReturnValue(true);
    render(
      <HypotheticalOutcomePlot
        label="Outcome plot"
        samples={samples}
        reducedMotionFallback="fan-chart"
      />,
    );

    expect(screen.getByText("Outcome plot fallback")).toBeInTheDocument();
  });
});
