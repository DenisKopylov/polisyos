import { render } from "@testing-library/react";
import { axe } from "vitest-axe";
import { LocaleProvider } from "@/shared/i18n/LocaleProvider";

import { ScientificDepthPanel } from "./ScientificDepthPanel";

describe("ScientificDepthPanel accessibility", () => {
  it("has no accessibility violations for unavailable", async () => {
    const { container } = render(
      <LocaleProvider>
        <ScientificDepthPanel />
      </LocaleProvider>,
    );

    expect((await axe(container)).violations).toHaveLength(0);
  });
});
