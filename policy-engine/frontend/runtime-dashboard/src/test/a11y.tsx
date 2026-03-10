import type { ReactElement } from "react";
import { axe } from "vitest-axe";

import { renderWithProviders } from "@/test/render";

export async function expectNoA11yViolations(
  ui: ReactElement,
  options?: {
    initialEntries?: string[];
  },
) {
  const view = renderWithProviders(ui, options);
  const results = await axe(view.container);

  expect(results.violations).toHaveLength(0);

  return view;
}
