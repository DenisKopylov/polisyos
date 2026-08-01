import { screen } from "@testing-library/react";

import { renderWithProviders } from "@/test/render";
import { TooltipProvider } from "@polisyos/atlas-ui";

import { ComplianceBadge } from "./ComplianceBadge";

describe("ComplianceBadge", () => {
  it("documents applicable standards without declaring a local compliance status", () => {
    renderWithProviders(
      <TooltipProvider>
        <ComplianceBadge />
      </TooltipProvider>,
    );

    expect(screen.queryByText("Compliant")).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /compliance standards/iu }),
    ).toBeInTheDocument();
  });
});
