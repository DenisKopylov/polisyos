import { render, screen } from "@testing-library/react";

import {
  buildUncertaintyPatternIds,
  resolveUncertaintyPatternFill,
  UncertaintyPatterns,
} from "@/shared/charts/patterns";

describe("UncertaintyPatterns", () => {
  it("builds deterministic ids and paint server references", () => {
    const ids = buildUncertaintyPatternIds("atlas");
    expect(ids).toEqual({
      assumed: "atlas-assumed",
      disputed: "atlas-disputed",
      estimated: "atlas-estimated",
      unknown: "atlas-unknown",
    });
    expect(resolveUncertaintyPatternFill("diagonal-lines", ids)).toBe(
      "url(#atlas-estimated)",
    );
    expect(resolveUncertaintyPatternFill("dots", ids)).toBe(
      "url(#atlas-assumed)",
    );
    expect(resolveUncertaintyPatternFill("crosshatch", ids)).toBe(
      "url(#atlas-unknown)",
    );
    expect(resolveUncertaintyPatternFill("none", ids)).toBe("none");
  });

  it("renders estimated, assumed, unknown, and disputed defs", () => {
    const ids = buildUncertaintyPatternIds("atlas");
    render(
      <svg>
        <UncertaintyPatterns ids={ids} />
      </svg>,
    );

    expect(screen.getByTestId("atlas-estimated")).toBeInTheDocument();
    expect(screen.getByTestId("atlas-assumed")).toBeInTheDocument();
    expect(screen.getByTestId("atlas-unknown")).toBeInTheDocument();
    expect(screen.getByTestId("atlas-disputed")).toBeInTheDocument();
  });
});
