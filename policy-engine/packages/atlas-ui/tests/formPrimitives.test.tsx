import { fireEvent, render, screen } from "@testing-library/react";
import { createRef } from "react";
import { vi } from "vitest";

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

describe("form primitives", () => {
  it("preserves native labels, validity, values, and forwarded refs", () => {
    const checkboxRef = createRef<HTMLInputElement>();
    const inputRef = createRef<HTMLInputElement>();
    const selectRef = createRef<HTMLSelectElement>();
    const textareaRef = createRef<HTMLTextAreaElement>();
    const onCheckboxChange = vi.fn();
    const onRadioChange = vi.fn();

    render(
      <form aria-label="Governed decision">
        <Label htmlFor="decision-title">Decision title</Label>
        <Input id="decision-title" ref={inputRef} required />
        <Checkbox
          ref={checkboxRef}
          aria-label="Include evidence"
          defaultChecked
          onChange={onCheckboxChange}
        />
        <Radio
          aria-label="Primary candidate"
          defaultChecked
          name="candidate"
          value="one"
        />
        <Radio
          aria-label="Alternative candidate"
          name="candidate"
          value="two"
          onChange={onRadioChange}
        />
        <Select
          ref={selectRef}
          aria-label="Disposition"
          defaultValue=""
          required
        >
          <option value="">Choose a disposition</option>
          <option value="hold">Hold</option>
          <option value="publish">Publish</option>
        </Select>
        <Textarea ref={textareaRef} aria-label="Rationale" required />
      </form>,
    );

    const input = screen.getByRole("textbox", { name: "Decision title" });
    expect(input).toBeInvalid();
    fireEvent.change(input, { target: { value: "Publish candidate" } });
    expect(input).toBeValid();
    expect(inputRef.current).toBe(input);
    expect(checkboxRef.current).toBe(
      screen.getByRole("checkbox", { name: "Include evidence" }),
    );
    fireEvent.click(checkboxRef.current!);
    expect(checkboxRef.current).not.toBeChecked();
    expect(onCheckboxChange).toHaveBeenCalledOnce();

    const primaryRadio = screen.getByRole("radio", {
      name: "Primary candidate",
    });
    const alternativeRadio = screen.getByRole("radio", {
      name: "Alternative candidate",
    });
    fireEvent.click(alternativeRadio);
    expect(primaryRadio).not.toBeChecked();
    expect(alternativeRadio).toBeChecked();
    expect(onRadioChange).toHaveBeenCalledOnce();

    expect(selectRef.current).toBeInvalid();
    fireEvent.change(selectRef.current!, { target: { value: "hold" } });
    expect(selectRef.current).toBeValid();
    expect(selectRef.current).toHaveValue("hold");
    expect(textareaRef.current).toBeInvalid();
    fireEvent.change(textareaRef.current!, {
      target: { value: "Needs review" },
    });
    expect(textareaRef.current).toBeValid();
    expect(textareaRef.current).toHaveValue("Needs review");
  });

  it("preserves generic segmented option values and disabled option behavior", () => {
    type ReviewPosture = "candidate" | "novel_owner_value" | "blocked";
    const onValueChange = vi.fn<(value: ReviewPosture) => void>();

    render(
      <SegmentedControl<ReviewPosture>
        ariaLabel="Review posture"
        value="candidate"
        onValueChange={onValueChange}
        options={[
          { label: "Candidate", value: "candidate" },
          { label: "Novel owner value", value: "novel_owner_value" },
          { disabled: true, label: "Blocked", value: "blocked" },
        ]}
      />,
    );

    const blockedOption = screen.getByRole("radio", { name: "Blocked" });
    expect(blockedOption).toBeDisabled();
    blockedOption.click();
    expect(onValueChange).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("radio", { name: "Novel owner value" }));
    expect(onValueChange).toHaveBeenCalledWith("novel_owner_value");
  });

  it("preserves Radix switch and slider props", () => {
    const onCheckedChange = vi.fn();

    render(
      <>
        <Switch
          aria-label="Live evidence"
          defaultChecked
          onCheckedChange={onCheckedChange}
        />
        <Slider
          aria-label="Confidence interval"
          defaultValue={[25, 75]}
          min={0}
          max={100}
          step={5}
          thumbLabels={["Lower confidence", "Upper confidence"]}
          trackGradient="linear-gradient(to right, red, green)"
        />
      </>,
    );

    fireEvent.click(screen.getByRole("switch", { name: "Live evidence" }));
    expect(onCheckedChange).toHaveBeenCalledWith(false);
    expect(
      screen.getByRole("slider", { name: "Lower confidence" }),
    ).toHaveAttribute("aria-valuenow", "25");
    expect(
      screen.getByRole("slider", { name: "Upper confidence" }),
    ).toHaveAttribute("aria-valuenow", "75");
    expect(document.querySelector("[data-radix-slider-track]")).toBeNull();
    expect(document.querySelector("[style*='linear-gradient']")).toHaveStyle({
      background: "linear-gradient(to right, red, green)",
    });
  });

  it("preserves toggle cancellation before pressed-state notification", () => {
    const cancelledChange = vi.fn();
    const acceptedChange = vi.fn();

    render(
      <>
        <ToggleButton
          label="Cancelled toggle"
          pressed={false}
          onClick={(event) => event.preventDefault()}
          onPressedChange={cancelledChange}
        />
        <ToggleButton
          label="Accepted toggle"
          pressed={false}
          onPressedChange={acceptedChange}
        />
      </>,
    );

    fireEvent.click(screen.getByRole("button", { name: "Cancelled toggle" }));
    const acceptedToggle = screen.getByRole("button", {
      name: "Accepted toggle",
    });
    expect(acceptedToggle).toHaveAttribute("type", "button");
    expect(acceptedToggle).toHaveAttribute("aria-pressed", "false");
    fireEvent.click(acceptedToggle);

    expect(cancelledChange).not.toHaveBeenCalled();
    expect(acceptedChange).toHaveBeenCalledWith(true);
  });
});
