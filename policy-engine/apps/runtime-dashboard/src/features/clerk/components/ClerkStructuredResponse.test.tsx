import { screen } from "@testing-library/react";

import { renderWithProviders } from "@/test/render";

import { ClerkStructuredResponse } from "./ClerkStructuredResponse";

describe("ClerkStructuredResponse", () => {
  it("preserves an unseen candidate confidence label verbatim", () => {
    renderWithProviders(
      <ClerkStructuredResponse
        data={{
          confidence: 0.61,
          confidenceLevel: "future_candidate_confidence",
        }}
      />,
    );

    expect(screen.getByText("future_candidate_confidence")).toHaveClass(
      "text-muted",
    );
  });
});
