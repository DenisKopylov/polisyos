import { render } from "@testing-library/react";
import { axe } from "vitest-axe";
import { LocaleProvider } from "@/shared/i18n/LocaleProvider";

import { PublicSectorReadinessPanel } from "./PublicSectorReadinessPanel";

describe("PublicSectorReadinessPanel accessibility", () => {
  it("has no accessibility violations for unavailable", async () => {
    const { container } = render(
      <LocaleProvider>
        <PublicSectorReadinessPanel />
      </LocaleProvider>,
    );

    expect((await axe(container)).violations).toHaveLength(0);
  });
});
