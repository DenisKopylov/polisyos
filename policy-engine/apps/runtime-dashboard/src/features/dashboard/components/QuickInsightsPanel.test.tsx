import { screen } from "@testing-library/react";

import {
  createInteractionState,
  type InteractionState,
  presentAuthority,
} from "@/shared/lib/domain/statusOwnership";
import { renderWithProviders } from "@/test/render";

import { QuickInsightsPanel, type QuickInsight } from "./QuickInsightsPanel";

describe("QuickInsightsPanel", () => {
  it("preserves a novel candidate label in neutral clothing", () => {
    renderWithProviders(
      <QuickInsightsPanel
        insights={[
          {
            id: "future",
            level: createInteractionState(
              "future_candidate_signal",
              "candidate_display",
            ),
            title: "Candidate observation",
            body: "Not owner authority",
          },
        ]}
      />,
    );

    const label = screen.getByText("future_candidate_signal");
    expect(label).toHaveClass("text-muted");
    expect(screen.getByRole("article")).toHaveAttribute(
      "data-interaction-purpose",
      "candidate_display",
    );
  });

  it("rejects quick-insight presentation state at authority slots", () => {
    expectTypeOf<QuickInsight["level"]>().toEqualTypeOf<InteractionState>();
    const level = createInteractionState("future_insight", "candidate_display");
    const compileOnly = () => {
      // @ts-expect-error Candidate quick-insight state cannot enter authority.
      presentAuthority(level);
    };

    expect(compileOnly).toBeTypeOf("function");
  });
});
