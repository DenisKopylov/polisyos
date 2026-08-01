import { render, screen } from "@testing-library/react";

import { JanusGlyph } from "./JanusGlyph";

describe("JanusGlyph", () => {
  it("renders an accessible mark by default", () => {
    render(<JanusGlyph size={24} />);
    const svg = screen.getByRole("img");
    expect(svg.getAttribute("aria-label")).toBe("PolicyOS Janus mark");
    expect(svg.getAttribute("data-variant")).toBe("mark");
    expect(svg.getAttribute("data-size")).toBe("24");
  });

  it("supports line and serif-punctuation variants", () => {
    const { rerender } = render(<JanusGlyph variant="line" size={16} />);
    expect(screen.getByRole("img").getAttribute("data-variant")).toBe("line");
    rerender(<JanusGlyph variant="serif-punctuation" size={32} />);
    expect(screen.getByRole("img").getAttribute("data-variant")).toBe(
      "serif-punctuation",
    );
  });

  it("marks svg decorative when requested", () => {
    render(<JanusGlyph decorative />);
    const svg = screen.getByRole("presentation", { hidden: true });
    expect(svg.getAttribute("aria-hidden")).toBe("true");
  });

  it("exposes inverted state via data attribute", () => {
    render(<JanusGlyph inverted />);
    expect(screen.getByRole("img").getAttribute("data-inverted")).toBe("true");
  });

  it("has no status intent or authority-colored palette", () => {
    render(<JanusGlyph />);
    const svg = screen.getByRole("img");
    expect(svg).not.toHaveAttribute("data-intent");
    expect(svg.getAttribute("style")).not.toMatch(
      /status-(?:approved|rejected|pending)/u,
    );
  });
});
