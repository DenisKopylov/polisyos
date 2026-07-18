import { render } from "@testing-library/react";
import { axe } from "vitest-axe";

import {
  Checkbox,
  Input,
  Label,
  Radio,
  SegmentedControl,
  Select,
  Slider,
  Switch,
  Textarea,
  ToggleButton,
} from "../src/index";

describe("form primitive accessibility", () => {
  it("has no detectable accessibility violations", async () => {
    const { container } = render(
      <form aria-label="Evidence review">
        <Label htmlFor="evidence-query">Evidence query</Label>
        <Input id="evidence-query" />
        <Checkbox aria-label="Include contested evidence" />
        <fieldset>
          <legend>Candidate source</legend>
          <Radio aria-label="Runtime source" name="source" value="runtime" />
        </fieldset>
        <SegmentedControl
          ariaLabel="Review posture"
          value="candidate"
          onValueChange={() => undefined}
          options={[
            { label: "Candidate", value: "candidate" },
            { label: "Review required", value: "review_required" },
          ]}
        />
        <Select aria-label="Disposition" defaultValue="hold">
          <option value="hold">Hold</option>
          <option value="publish">Publish</option>
        </Select>
        <Slider
          aria-label="Confidence"
          defaultValue={[50]}
          thumbLabels={["Confidence"]}
        />
        <Switch aria-label="Live evidence" />
        <Textarea aria-label="Rationale" />
        <ToggleButton label="Reading view" pressed={false} />
      </form>,
    );

    const results = await axe(container);
    expect(results.violations).toHaveLength(0);
  });
});
