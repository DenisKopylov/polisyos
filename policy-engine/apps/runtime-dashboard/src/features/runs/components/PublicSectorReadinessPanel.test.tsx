import { render, screen } from "@testing-library/react";
import { LocaleProvider } from "@/shared/i18n/LocaleProvider";

import { PublicSectorReadinessPanel } from "./PublicSectorReadinessPanel";

describe("PublicSectorReadinessPanel", () => {
  it("is a no-input surface that emits only explicit unavailable", () => {
    render(
      <LocaleProvider>
        <PublicSectorReadinessPanel />
      </LocaleProvider>,
    );

    expect(
      screen.getByTestId("public-sector-readiness-panel").textContent?.trim(),
    ).toBe("Unavailable");
    for (const retiredContent of [
      "fairness",
      "harm",
      "embargo",
      "revocation",
      "review",
      "finding",
      "hash",
    ]) {
      expect(screen.queryByText(new RegExp(retiredContent, "i"))).not.toBeInTheDocument();
    }
  });
});
