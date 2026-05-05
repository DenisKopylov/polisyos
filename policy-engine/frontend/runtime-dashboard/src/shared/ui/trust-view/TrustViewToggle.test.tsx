import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { TrustViewProvider } from "@/app/providers/TrustViewProvider";
import { LocaleProvider } from "@/shared/i18n/LocaleProvider";

import { TrustViewToggle } from "./TrustViewToggle";

describe("TrustViewToggle", () => {
  it("cycles off, compact and expanded modes", async () => {
    window.history.replaceState(null, "", "/runs/run_1");
    const user = userEvent.setup();

    render(
      <LocaleProvider>
        <TrustViewProvider>
          <TrustViewToggle />
        </TrustViewProvider>
      </LocaleProvider>,
    );

    expect(screen.getByRole("button")).toHaveAttribute("data-mode", "off");

    await user.click(screen.getByRole("button"));
    expect(screen.getByRole("button")).toHaveAttribute("data-mode", "compact");

    await user.click(screen.getByRole("button"));
    expect(screen.getByRole("button")).toHaveAttribute("data-mode", "expanded");
  });
});
