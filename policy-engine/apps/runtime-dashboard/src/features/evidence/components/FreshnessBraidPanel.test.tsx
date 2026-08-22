import { screen, within } from "@testing-library/react";

import { createInteractionState } from "@/shared/lib/domain/statusOwnership";
import { renderWithProviders } from "@/test/render";

import { FreshnessBraidPanel } from "./FreshnessBraidPanel";

describe("FreshnessBraidPanel", () => {
  it("labels diagnostic state explicitly and keeps SLA clothing neutral", () => {
    renderWithProviders(
      <FreshnessBraidPanel
        view={{
          generatedAt: "2026-08-21T12:00:00Z",
          governingLagMs: 28 * 60 * 60 * 1000,
          governingThreadId: "tax-ledger",
          joinNodes: [],
          threads: [
            {
              connectorId: "tax-ledger",
              derivedFactCount: 1,
              governing: true,
              label: "tax-ledger",
              lagMs: 28 * 60 * 60 * 1000,
              lastObservedAt: "2026-08-20T08:00:00Z",
              profileIds: [],
              slaMs: 24 * 60 * 60 * 1000,
              state: createInteractionState("fail", "diagnostic_display"),
              volume: 1,
            },
          ],
        }}
      />,
    );

    const thread = screen.getByRole("listitem");
    expect(thread).toHaveAttribute(
      "data-interaction-purpose",
      "diagnostic_display",
    );
    expect(thread).toHaveAttribute("data-display-state", "fail");
    expect(thread).not.toHaveClass("border-warning/50", "bg-warning/5");
    expect(within(thread).getByText("fail")).toHaveClass("text-muted");
    expect(screen.getByTestId("freshness-thread-fill-tax-ledger")).toHaveClass(
      "bg-muted",
    );
    expect(
      screen.getByTestId("freshness-thread-fill-tax-ledger"),
    ).toHaveAttribute("aria-hidden", "true");
    expect(screen.getByText(/governing lag/i)).toHaveClass("text-muted");
  });
});
