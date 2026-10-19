import { screen, within } from "@testing-library/react";

/** Return the exact Unknown action from the expanded semantic Trust View. */
export function unknownTrustViewStatusButton(): HTMLElement {
  const trustView = screen.getByRole("group", {
    name: exactAccessibleName("Trust View"),
  });
  return within(trustView).getByRole("button", {
    name: exactAccessibleName("Unknown"),
  });
}

function exactAccessibleName(name: string): RegExp {
  const escaped = name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return new RegExp(`^${escaped}$`, "u");
}
