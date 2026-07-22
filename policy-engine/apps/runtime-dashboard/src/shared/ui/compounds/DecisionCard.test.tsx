import type { AvailableGovernedProjectionPacket } from "@polisyos/runtime-api-client";
import { createGovernedAuthorityPurpose } from "@polisyos/atlas-ui";
import { screen } from "@testing-library/react";

import { renderWithProviders } from "@/test/render";

import { DecisionCard } from "./DecisionCard";

const GOVERNED_PACKET = {
  authoritative_for: ["publication_review"],
  availability: "available",
  payload: {},
} as unknown as AvailableGovernedProjectionPacket;

const FIXTURE_PACKET = {
  authoritative_for: ["publication_review"],
  availability: "available",
  payload: { fixture_authority: "fixture_only" },
  projection_id: "legacy-proving-ground",
} as unknown as AvailableGovernedProjectionPacket;

describe("DecisionCard", () => {
  it("keeps candidate and authority postures visually distinct for the same copy", () => {
    const authorityPurpose = createGovernedAuthorityPurpose(
      GOVERNED_PACKET,
      "publication_review",
    );

    renderWithProviders(
      <>
        <DecisionCard title="Candidate" verdict="publishable" />
        <DecisionCard
          authorityPurpose={authorityPurpose}
          title="Governed"
          verdict="publishable"
        />
      </>,
    );

    const candidate = screen.getByTestId("decision-card-candidate");
    const governed = screen.getByTestId("decision-card-governed");

    expect(candidate).toHaveAttribute("data-authority-posture", "candidate");
    expect(governed).toHaveAttribute(
      "data-authority-posture",
      "governed-authority",
    );
    expect(candidate.className).not.toBe(governed.className);
    expect(screen.getAllByText("publishable")).toHaveLength(2);
    expect(candidate).toHaveAttribute(
      "data-decision-grade-presentation",
      "unrecognized",
    );
    expect(governed).toHaveAttribute(
      "data-decision-grade-presentation",
      "unrecognized",
    );
  });

  it("bars fixture-backed packets from governed authority clothing", () => {
    const authorityPurpose = createGovernedAuthorityPurpose(
      FIXTURE_PACKET,
      "publication_review",
    );

    renderWithProviders(
      <DecisionCard
        authorityPurpose={authorityPurpose}
        title="Fixture packet"
        verdict="future-owner-grade"
      />,
    );

    const card = screen.getByTestId("decision-card-fixture");
    expect(card).toHaveAttribute("data-authority-posture", "fixture-only");
    expect(card).toHaveAttribute("data-fixture-authority", "fixture_only");
    expect(card).not.toHaveAttribute(
      "data-authority-posture",
      "governed-authority",
    );
    expect(card.className).toContain("border-dashed");
  });

  it("preserves owner diagnostic labels without caller-controlled authority clothing", () => {
    renderWithProviders(
      <DecisionCard
        title="Opaque diagnostics"
        verdict="future-owner-grade"
        diagnostics={[
          { kind: "publishable", label: "Owner says publishable" },
          { kind: "blocked", label: "Owner says blocked" },
        ]}
      />,
    );

    const publishable = screen.getByText("Owner says publishable");
    const blocked = screen.getByText("Owner says blocked");

    expect(publishable).toHaveAttribute(
      "data-owner-diagnostic-kind",
      "publishable",
    );
    expect(blocked).toHaveAttribute("data-owner-diagnostic-kind", "blocked");
    expect(publishable.className).toBe(blocked.className);
  });
});
