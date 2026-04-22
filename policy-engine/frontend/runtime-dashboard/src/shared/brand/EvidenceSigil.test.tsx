/* eslint-disable testing-library/no-node-access */
import { render, screen } from "@testing-library/react";

import { EvidenceSigil, sigilGeometryFromHash } from "./EvidenceSigil";

describe("EvidenceSigil", () => {
  it("produces identical markup for the same bundle hash", () => {
    const { container: a } = render(
      <EvidenceSigil bundleHash="deadbeefcafef00d" />,
    );
    const { container: b } = render(
      <EvidenceSigil bundleHash="deadbeefcafef00d" />,
    );
    const normalise = (html: string) =>
      html.replace(/evidence-sigil-hatch-[^"']+/g, "hatch");
    expect(normalise(a.innerHTML)).toBe(normalise(b.innerHTML));
  });

  it("produces unique geometry across 1000 random bundles (>= 99.9%)", () => {
    const shapes = new Set<string>();
    const seen: string[] = [];
    for (let index = 0; index < 1000; index += 1) {
      const hash = pseudoRandomHex(index);
      seen.push(hash);
      const geometry = sigilGeometryFromHash(hash);
      shapes.add(JSON.stringify(geometry));
    }
    const uniqueness = shapes.size / seen.length;
    expect(uniqueness).toBeGreaterThanOrEqual(0.999);
  });

  it("differs between two distinct bundle hashes", () => {
    const a = sigilGeometryFromHash(
      "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    );
    const b = sigilGeometryFromHash(
      "111111111111111111111111111111111111111111111111",
    );
    expect(JSON.stringify(a)).not.toBe(JSON.stringify(b));
  });

  it("colors the perimeter by identifiability band", () => {
    const getStroke = (): string => {
      const svg = screen.getByRole("img");
      return svg.querySelector("g")?.getAttribute("stroke") ?? "";
    };
    const { unmount: unmountLow } = render(
      <EvidenceSigil bundleHash="deadbeef" identifiability={0.1} />,
    );
    expect(getStroke()).toMatch(/status-rejected|ember/);
    unmountLow();
    const { unmount: unmountMid } = render(
      <EvidenceSigil bundleHash="deadbeef" identifiability={0.5} />,
    );
    expect(getStroke()).toMatch(/status-pending|gold/);
    unmountMid();
    render(<EvidenceSigil bundleHash="deadbeef" identifiability={0.9} />);
    expect(getStroke()).toMatch(/status-approved|teal/);
  });

  it("reflects fresc profile via data attribute and dot count", () => {
    render(<EvidenceSigil bundleHash="deadbeef" frescProfile="replicated" />);
    const svg = screen.getByRole("img");
    expect(svg.getAttribute("data-fresc-profile")).toBe("replicated");
    expect(svg.querySelectorAll("circle").length).toBe(4);
  });
});

function pseudoRandomHex(seed: number): string {
  const mix = (value: number) => {
    let x = Math.imul(value ^ (value >>> 16), 0x85ebca6b);
    x = Math.imul(x ^ (x >>> 13), 0xc2b2ae35);
    return (x ^ (x >>> 16)) >>> 0;
  };
  const words = [
    mix(seed),
    mix(seed ^ 0xdeadbeef),
    mix(seed ^ 0xcafef00d),
    mix(seed ^ 0xba5eba11),
  ];
  return words.map((w) => w.toString(16).padStart(8, "0")).join("");
}
