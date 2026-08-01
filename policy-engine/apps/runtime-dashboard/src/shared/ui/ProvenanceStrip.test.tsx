import { render, screen, within } from "@testing-library/react";
import type { VerificationMetadata } from "@polisyos/runtime-api-client";

import type { ProvenanceItem } from "@/shared/brand/provenance-adapter";
import { LocaleProvider } from "@/shared/i18n/LocaleProvider";

import { ProvenanceStrip } from "./ProvenanceStrip";

const items: ProvenanceItem[] = [
  { id: "freshness", glyph: "freshness", label: "Fresh" },
  {
    id: "governance",
    glyph: "governance-pass",
    label: "Governance pass",
  },
  {
    id: "evidence",
    glyph: "evidence",
    label: "Strong evidence",
  },
];

const verifiedMetadata = {
  dispute_status: "none",
  freshness: "current",
  verification_method: "content_hash",
  verification_status: "verified",
  verified_at: "2026-07-31T10:00:00Z",
  verified_by: "runtime-verifier",
} satisfies VerificationMetadata;

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

  it("missing VerificationMetadata produces no posture", () => {
    render(
      <LocaleProvider>
        <ProvenanceStrip
          items={[
            {
              ...items[0],
              detail: "verified=true at 2026-07-31T10:00:00Z",
              label: "verified",
            },
          ]}
        />
      </LocaleProvider>,
    );

    const item = screen.getByRole("listitem");
    expect(item).not.toHaveAttribute("data-intent");
    expect(within(item).getByRole("img")).not.toHaveAttribute(
      "data-glyph-intent",
    );
    expect(within(item).getAllByLabelText("verified")).toHaveLength(1);
  });

  it("generated VerificationMetadata alone changes trust posture", () => {
    const base = {
      glyph: "evidence" as const,
      label: "Same owner label",
    };
    render(
      <LocaleProvider>
        <ProvenanceStrip
          items={[
            { ...base, id: "without-metadata" },
            {
              ...base,
              id: "with-metadata",
              trustMetadata: verifiedMetadata,
            },
          ]}
        />
      </LocaleProvider>,
    );

    const [withoutMetadata, withMetadata] = screen.getAllByRole("listitem");
    expect(
      within(withoutMetadata).queryByLabelText("verified"),
    ).not.toBeInTheDocument();
    const verification = within(withMetadata).getByLabelText("verified");
    expect(verification).toHaveAttribute(
      "data-verification-presentation",
      "verified",
    );
    expect(verification).toHaveAttribute(
      "data-verification-source",
      "generated-owner",
    );
  });
});
