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
});
