import { render, screen } from "@testing-library/react";

import { Glyph } from "./Glyph";
import { GLYPH_NAMES } from "./glyph-vocabulary";

describe("Glyph", () => {
  it("renders every radical with accessible name", () => {
    for (const name of GLYPH_NAMES) {
      const { unmount } = render(<Glyph name={name} />);
      const svg = screen.getByRole("img");
      expect(svg.getAttribute("aria-label")).toBe(name);
      expect(svg.getAttribute("data-glyph-name")).toBe(name);
      unmount();
    }
  });

  it("uses fine stroke for 12/14 and heavy stroke for 16/24", () => {
    const { rerender } = render(<Glyph name="intervention" size={12} />);
    expect(screen.getByRole("img").getAttribute("stroke-width")).toBe("1.25");
    rerender(<Glyph name="intervention" size={24} />);
    expect(screen.getByRole("img").getAttribute("stroke-width")).toBe("1.5");
  });

  it("applies dashed stroke-dasharray when strokeStyle=dashed", () => {
    render(<Glyph name="counterfactual" strokeStyle="dashed" />);
    expect(screen.getByRole("img").getAttribute("stroke-dasharray")).toBe(
      "2 1.5",
    );
  });

  it("is aria-hidden when decorative", () => {
    render(<Glyph name="evidence" decorative />);
    const svg = screen.getByRole("presentation", { hidden: true });
    expect(svg.getAttribute("aria-hidden")).toBe("true");
    expect(svg.getAttribute("role")).toBe("presentation");
  });

  it("exposes diacritic via data attribute", () => {
    render(<Glyph name="identifiability" diacritic="strict" />);
    expect(screen.getByRole("img").getAttribute("data-glyph-diacritic")).toBe(
      "strict",
    );
  });
});
