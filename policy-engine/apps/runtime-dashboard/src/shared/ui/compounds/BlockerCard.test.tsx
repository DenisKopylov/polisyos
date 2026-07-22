import type { ComponentProps } from "react";
import type { PolicyDesignCaseProjectionBlocker } from "@polisyos/runtime-api-client";
import { screen } from "@testing-library/react";

import { renderWithProviders } from "@/test/render";

import { BlockerCard } from "./BlockerCard";

describe("BlockerCard", () => {
  it("preserves the producer blocker and cannot be overridden by local severity", () => {
    const blocker = {
      code: "missing_grounded_effect",
      message: "No grounded effect supports the publication claim.",
      owner: "runtime-quality",
      severity: "advisory",
    } satisfies PolicyDesignCaseProjectionBlocker;
    const attemptedLocalOverride = {
      blocker,
      severity: "ok",
    } as ComponentProps<typeof BlockerCard> & { severity: string };

    renderWithProviders(<BlockerCard {...attemptedLocalOverride} />);

    const card = screen.getByTestId("blocker-card");
    expect(card).toHaveAttribute("data-producer-blocker-code", blocker.code);
    expect(card).toHaveAttribute(
      "data-producer-blocker-severity",
      blocker.severity,
    );
    expect(card).not.toHaveAttribute("data-local-severity");
    expect(screen.getByText(blocker.message)).toBeInTheDocument();
    expect(screen.getAllByText(blocker.code)).not.toHaveLength(0);
    expect(screen.getByText(blocker.owner)).toBeInTheDocument();
  });
});
