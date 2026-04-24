import type { ReactElement } from "react";
import { axe } from "vitest-axe";

import { renderWithProviders } from "@/test/render";
import { WCAG_AA_TAGS } from "@/test/a11yTags";

export async function expectNoA11yViolations(
  ui: ReactElement,
  options?: {
    includeDocumentBody?: boolean;
    initialEntries?: string[];
    interactiveProviders?: boolean;
  },
) {
  const view = renderWithProviders(ui, options);
  const results = await axe(
    options?.includeDocumentBody ? document.body : view.container,
    {
      runOnly: {
        type: "tag",
        values: [...WCAG_AA_TAGS],
      },
    },
  );

  expect(results.violations).toHaveLength(0);

  return view;
}
