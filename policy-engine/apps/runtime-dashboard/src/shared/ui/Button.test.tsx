/* eslint-disable testing-library/prefer-screen-queries */
import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import { Button } from "./Button";

describe("Button", () => {
  it("renders as router link when `to` is provided", () => {
    const view = render(
      <MemoryRouter>
        <Button to="/runs" variant="ghost">
          Open runs
        </Button>
      </MemoryRouter>,
    );

    expect(view.getByRole("link", { name: "Open runs" })).toHaveAttribute(
      "href",
      "/runs",
    );
  });

  it("renders as native button by default", () => {
    const view = render(
      <Button type="button" variant="primary">
        Launch
      </Button>,
    );

    expect(view.getByRole("button", { name: "Launch" })).toBeInTheDocument();
  });
});
