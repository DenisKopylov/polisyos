import { render, screen } from "@testing-library/react";

import { DisputedMarker } from "@/shared/charts/DisputedMarker";

describe("DisputedMarker", () => {
  it("includes dispute attribution in the trigger label", () => {
    render(
      <DisputedMarker
        disputes={[
          {
            who: "Policy lab",
            why: "Bootstrap assumptions were challenged.",
            asOf: "2026-04-22",
          },
        ]}
      />,
    );

    expect(
      screen.getByRole("button", { name: /policy lab/i }),
    ).toBeInTheDocument();
  });

  it("dispute marker carries owner fact without a local Glyph intent", () => {
    render(
      <DisputedMarker
        disputes={[
          {
            who: "Review board",
            why: "Owner-recorded disagreement remains open.",
            asOf: "2026-07-31",
          },
        ]}
      />,
    );

    const trigger = screen.getByRole("button", {
      name: /review board.*disagreement/i,
    });
    const factLabel = screen.getByText("Disputed", { selector: "span" });
    expect(trigger).toBeInTheDocument();
    expect(trigger.style.borderColor).not.toBe("");
    expect(trigger.style.color).toBe("");
    expect(factLabel.style.color).toBe(trigger.style.borderColor);
    const glyph = screen.getByRole("img", { name: "Disputed" });
    expect(glyph).not.toHaveAttribute("data-glyph-intent");
    expect(glyph.style.color).toBe("");
  });
});
