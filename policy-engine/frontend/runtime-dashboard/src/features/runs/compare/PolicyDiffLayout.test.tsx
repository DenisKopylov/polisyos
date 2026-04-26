import { fireEvent, screen } from "@testing-library/react";

import { renderWithProviders } from "@/test/render";

import { PolicyDiffLayout } from "./PolicyDiffLayout";

describe("PolicyDiffLayout", () => {
  it("keeps both run panes in the same scroll position while sync is enabled", () => {
    renderWithProviders(
      <PolicyDiffLayout
        leftPane={<div style={{ height: 1000 }}>Left pane</div>}
        deltaRail={<div>Delta rail</div>}
        rightPane={<div style={{ height: 2000 }}>Right pane</div>}
      />,
    );

    const left = screen.getByTestId("policy-diff-left-pane");
    const right = screen.getByTestId("policy-diff-right-pane");
    Object.defineProperties(left, {
      clientHeight: { configurable: true, value: 500 },
      scrollHeight: { configurable: true, value: 1000 },
    });
    Object.defineProperties(right, {
      clientHeight: { configurable: true, value: 1000 },
      scrollHeight: { configurable: true, value: 2000 },
    });

    left.scrollTop = 250;
    fireEvent.scroll(left);

    expect(right.scrollTop).toBe(500);
  });
});
