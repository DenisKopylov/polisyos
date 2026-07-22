import { screen } from "@testing-library/react";

import { AnimatedProgress } from "./AnimatedProgress";
import { FrequencyDots } from "./FrequencyDots";
import { renderWithProviders } from "@/test/render";

describe("chart confidence presentation", () => {
  it("does not change frequency-dot authority color at confidence thresholds", () => {
    const { rerender } = renderWithProviders(
      <FrequencyDots highlighted={10} total={100} />,
    );
    const firstFill = screen
      .getAllByTestId("frequency-dot")[0]
      .getAttribute("style");
    rerender(<FrequencyDots highlighted={90} total={100} />);
    const secondFill = screen
      .getAllByTestId("frequency-dot")[0]
      .getAttribute("style");
    expect(secondFill).toBe(firstFill);
    expect(secondFill).not.toMatch(/confidence-(?:high|medium|low)/u);
  });

  it("keeps progress color neutral as values cross confidence thresholds", () => {
    const { rerender } = renderWithProviders(
      <AnimatedProgress value={10} max={100} />,
    );
    const firstColor = screen
      .getByTestId("animated-progress-fill")
      .getAttribute("style")
      ?.replace(/width:[^;]+;?/u, "");
    rerender(<AnimatedProgress value={90} max={100} />);
    const secondColor = screen
      .getByTestId("animated-progress-fill")
      .getAttribute("style")
      ?.replace(/width:[^;]+;?/u, "");
    expect(secondColor).toBe(firstColor);
    expect(secondColor).not.toMatch(/confidence-(?:high|medium|low)/u);
  });
});
