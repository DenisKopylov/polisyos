import { expectNoA11yViolations } from "@/test/a11y";

import { Slider } from "./Slider";

describe("Slider accessibility", () => {
  it("has no detectable accessibility violations", async () => {
    await expectNoA11yViolations(
      <div className="space-y-3">
        <p className="text-sm font-medium">Confidence threshold</p>
        <Slider
          aria-label="Confidence threshold"
          defaultValue={[70]}
          max={100}
          min={0}
          step={5}
          thumbLabels={["Confidence threshold"]}
        />
      </div>,
    );
  });
});
