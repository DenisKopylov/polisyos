import { render, screen } from "@testing-library/react";
import type { OperatorDiagnostic } from "@polisyos/runtime-api-client";

import { createFixtureProvenance, EvidenceLink } from "../src/index";
import { FIXTURE_PAYLOAD } from "./evidenceTestData";

describe("EvidenceLink", () => {
  it("renders a typed evidence reference without claiming verification", () => {
    const evidenceRef =
      "https://evidence.example/policy-grounding" satisfies NonNullable<
        OperatorDiagnostic["evidence_refs"]
      >[number];

    render(<EvidenceLink evidenceRef={evidenceRef} href={evidenceRef} />);

    const link = screen.getByRole("link", { name: evidenceRef });
    expect(link).toHaveAttribute("href", evidenceRef);
    expect(link).toHaveAttribute("data-evidence-claim", "reference-only");
    expect(link).not.toHaveAttribute("data-verification-status");
  });

  it("keeps an explicitly empty href in the linked presentation", () => {
    render(
      <EvidenceLink
        anchorProps={{ target: "_blank" }}
        evidenceRef="evidence:pending"
        href=""
      />,
    );

    const link = screen.getByText("evidence:pending").closest("a");
    expect(link).not.toBeNull();
    expect(link).toHaveAttribute("href", "");
    expect(link).toHaveAttribute("target", "_blank");
  });

  it("renders a non-navigable owner reference as text when href is absent", () => {
    const href: string | undefined = undefined;
    render(<EvidenceLink evidenceRef="sha256:decision" href={href} />);

    const reference = screen.getByText("sha256:decision");
    expect(reference.tagName).toBe("SPAN");
    expect(reference).not.toHaveAttribute("href");
  });

  it("keeps the exact producer reference visible beside a custom prefix", () => {
    render(<EvidenceLink evidenceRef="sha256:owner" label="Decision:" />);

    expect(screen.getByText("Decision:")).toBeVisible();
    expect(screen.getByText("sha256:owner")).toBeVisible();
    expect(screen.getByText("sha256:owner").parentElement).toHaveAttribute(
      "data-evidence-ref",
      "sha256:owner",
    );
  });

  it("does not expose conflicting or visual anchor escape hatches", () => {
    const compileOnly = () => (
      <EvidenceLink
        anchorProps={{
          // @ts-expect-error EvidenceLink owns children and visual presentation.
          dangerouslySetInnerHTML: { __html: "hidden" },
        }}
        evidenceRef="https://evidence.example/item"
        href="https://evidence.example/item"
      />
    );

    expect(compileOnly).toBeTypeOf("function");
  });

  it("rejects a cloned fixture provenance token", () => {
    const fixture = createFixtureProvenance(FIXTURE_PAYLOAD);
    const forgedFixture = { ...fixture };

    expect(() =>
      render(
        <EvidenceLink
          evidenceRef="fixture:evidence"
          fixtureProvenance={forgedFixture}
        />,
      ),
    ).toThrow(/generated payload/i);
  });
});
