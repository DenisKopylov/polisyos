import { screen } from "@testing-library/react";

import {
  createInteractionState,
  type InteractionState,
  presentAuthority,
} from "@/shared/lib/domain/statusOwnership";
import { renderWithProviders } from "@/test/render";

import { InsightCallout, type InsightLevel } from "./InsightCallout";

describe("InsightCallout", () => {
  it("preserves a novel candidate label without authority coloring", () => {
    renderWithProviders(
      <InsightCallout
        level={createInteractionState(
          "future_narrative_signal",
          "candidate_display",
        )}
      >
        Candidate text
      </InsightCallout>,
    );

    const label = screen.getByText("future_narrative_signal");
    expect(label).toHaveClass("text-muted");
    expect(screen.getByRole("note")).toHaveAttribute(
      "data-interaction-purpose",
      "candidate_display",
    );
    expect(screen.getByRole("note").className).not.toMatch(
      /chart-(?:success|warning|alert)/u,
    );
  });

  it("rejects narrative presentation state at authority slots", () => {
    expectTypeOf<InsightLevel>().toEqualTypeOf<InteractionState>();
    const level = createInteractionState("future_callout", "candidate_display");
    const compileOnly = () => {
      // @ts-expect-error Candidate narrative state cannot enter authority.
      presentAuthority(level);
    };

    expect(compileOnly).toBeTypeOf("function");
  });
});
