import { screen } from "@testing-library/react";

import { renderWithProviders } from "@/test/render";

import { StatusTimeline } from "./StatusTimeline";

describe("StatusTimeline", () => {
  it("renders recorded events without inventing a DecisionTimeline authority", () => {
    renderWithProviders(
      <StatusTimeline
        emptyBody="No recorded events."
        emptyTitle="No events"
        items={[
          {
            id: "event-1",
            recordedState: "future_owner_event",
            timestamp: "2026-07-22T10:00:00Z",
            title: "Producer event",
          },
        ]}
      />,
    );

    const timeline = screen.getByTestId("status-timeline");
    expect(timeline).toHaveAttribute(
      "data-timeline-authority",
      "recorded-events-only",
    );
    expect(timeline).not.toHaveAttribute("data-decision-timeline");
    expect(screen.getByText("future_owner_event")).toHaveAttribute(
      "data-authority-presentation",
      "opaque",
    );
  });
});
