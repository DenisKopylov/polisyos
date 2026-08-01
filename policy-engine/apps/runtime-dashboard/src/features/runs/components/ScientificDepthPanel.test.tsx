import { render, screen } from "@testing-library/react";
import { LocaleProvider } from "@/shared/i18n/LocaleProvider";

import { ScientificDepthPanel } from "./ScientificDepthPanel";

describe("ScientificDepthPanel", () => {
  it("is a no-input surface that emits only explicit unavailable", () => {
    render(
      <LocaleProvider>
        <ScientificDepthPanel />
      </LocaleProvider>,
    );

    expect(
      screen.getByTestId("scientific-depth-panel").textContent?.trim(),
    ).toBe("Unavailable");
    for (const retiredContent of [
      "remedy",
      "e-value",
      "cohort",
      "stress",
      "ranking",
      "integrated",
    ]) {
      expect(screen.queryByText(new RegExp(retiredContent, "i"))).not.toBeInTheDocument();
    }
  });
});
