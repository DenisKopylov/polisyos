import { screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { renderWithProviders } from "@/test/render";
import { GuidedTour } from "./GuidedTour";

const visibleRect = {
  bottom: 68,
  height: 48,
  left: 12,
  right: 172,
  top: 20,
  width: 160,
  x: 12,
  y: 20,
  toJSON: () => ({}),
};

describe("GuidedTour", () => {
  it("skips missing targets and advances to the next visible step", async () => {
    vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockImplementation(
      function getBoundingClientRect(this: HTMLElement) {
        if (this.id === "visible-target") {
          return visibleRect as DOMRect;
        }
        return {
          ...visibleRect,
          bottom: 0,
          height: 0,
          left: 0,
          right: 0,
          top: 0,
          width: 0,
          x: 0,
          y: 0,
        } as DOMRect;
      },
    );

    renderWithProviders(
      <>
        <div id="visible-target">Visible target</div>
        <GuidedTour
          tour={{
            id: "tour-1",
            name: "Tour",
            steps: [
              {
                description: "Missing step description",
                id: "missing",
                target: "#missing-target",
                title: "Missing step",
              },
              {
                description: "Visible step description",
                id: "visible",
                target: "#visible-target",
                title: "Visible step",
              },
            ],
          }}
          onComplete={() => undefined}
          onDismiss={() => undefined}
        />
      </>,
    );

    await waitFor(() =>
      expect(screen.getByRole("dialog")).toHaveTextContent("Visible step"),
    );
  });

  it("dismisses the tour when no remaining targets can be found", async () => {
    const onDismiss = vi.fn();

    renderWithProviders(
      <GuidedTour
        tour={{
          id: "tour-2",
          name: "Tour",
          steps: [
            {
              description: "Missing step description",
              id: "missing",
              target: "#missing-target",
              title: "Missing step",
            },
          ],
        }}
        onComplete={() => undefined}
        onDismiss={onDismiss}
      />,
    );

    await waitFor(() => expect(onDismiss).toHaveBeenCalledTimes(1));
  });
});
