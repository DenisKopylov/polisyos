import { expectNoA11yViolations } from "@/test/a11y";
import { fireEvent, screen } from "@testing-library/react";

import { ReasoningChainDisplay } from "./ReasoningChainDisplay";

describe("ReasoningChainDisplay accessibility", () => {
  it("has no WCAG AA violations", async () => {
    await expectNoA11yViolations(
      <ReasoningChainDisplay
        steps={[
          {
            detail: "The operator asked for a policy comparison.",
            durationMs: 400,
            id: "question",
            summary: "Compare two interventions.",
            title: "Policy question",
            type: "question",
          },
          {
            detail: "The producer supplied a diagnostic result.",
            durationMs: 900,
            id: "conclusion",
            summary: "Intervention A dominates on the primary metric.",
            title: "Recommendation",
            type: "conclusion",
          },
        ]}
      />,
    );

    const questionDetails = screen.getByRole("button", {
      name: "Show details for Policy question",
    });
    const conclusionDetails = screen.getByRole("button", {
      name: "Show details for Recommendation",
    });
    expect(questionDetails).toHaveAttribute("aria-expanded", "false");
    expect(questionDetails).toHaveAttribute("aria-controls");

    fireEvent.click(questionDetails);
    expect(questionDetails).toHaveAttribute("aria-expanded", "true");
    expect(
      screen.getByRole("button", { name: "Expand all reasoning details" }),
    ).toBeInTheDocument();

    fireEvent.click(
      screen.getByRole("button", { name: "Expand all reasoning details" }),
    );
    expect(conclusionDetails).toHaveAttribute("aria-expanded", "true");
    expect(
      screen.getByRole("button", { name: "Collapse all reasoning details" }),
    ).toBeInTheDocument();
  });
});
