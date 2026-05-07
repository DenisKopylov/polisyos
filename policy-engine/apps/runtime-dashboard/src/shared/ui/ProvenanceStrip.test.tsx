import { render, screen } from "@testing-library/react";

import type { ProvenanceItem } from "@/shared/brand/provenance-adapter";

import { ProvenanceStrip } from "./ProvenanceStrip";

const items: ProvenanceItem[] = [
  { id: "freshness", glyph: "freshness", label: "Fresh", intent: "verified" },
  {
    id: "governance",
    glyph: "governance-pass",
    label: "Governance pass",
    intent: "verified",
  },
  {
    id: "evidence",
    glyph: "evidence",
    label: "Strong evidence",
    intent: "verified",
  },
];

describe("ProvenanceStrip", () => {
  it("renders a labeled group with every glyph", () => {
    render(<ProvenanceStrip items={items} title="Provenance" />);
    const group = screen.getByRole("group", { name: /provenance/i });
    expect(group).toBeInTheDocument();
    expect(screen.getAllByRole("img")).toHaveLength(items.length);
  });

  it("supports compact density", () => {
    render(<ProvenanceStrip items={items} density="compact" />);
    expect(
      screen.getByTestId("provenance-strip").getAttribute("data-density"),
    ).toBe("compact");
  });

  it("renders trailing content", () => {
    render(<ProvenanceStrip items={items} trailing={<span>trailing</span>} />);
    expect(screen.getByText("trailing")).toBeInTheDocument();
  });
});
