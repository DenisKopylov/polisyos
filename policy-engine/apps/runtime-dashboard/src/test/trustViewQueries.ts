import { screen, within } from "@testing-library/react";

/** Return the exact Unknown action from the expanded semantic Trust View. */
export function unknownTrustViewStatusButton(): HTMLElement {
  const trustView = screen.getByRole("group", {
    name: "Trust View",
    exact: true,
  });
  return within(trustView).getByRole("button", {
    name: "Unknown",
    exact: true,
  });
}
