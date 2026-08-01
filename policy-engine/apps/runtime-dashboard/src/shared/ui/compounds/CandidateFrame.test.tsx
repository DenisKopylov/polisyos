import type {
  DecisionPacketAuthoredBlock,
  PolicyDesignCaseProjection,
} from "@polisyos/runtime-api-client";
import { screen, within } from "@testing-library/react";

import { renderWithProviders } from "@/test/render";

import { CandidateFrame } from "./CandidateFrame";

describe("CandidateFrame", () => {
  it("never promotes model prose without the generated authority purpose", () => {
    const block = {
      author: "drafter",
      content: "Adopt the model-proposed eligibility threshold.",
      reviewed_by_human: true,
    } satisfies DecisionPacketAuthoredBlock;
    const authorityPurpose = undefined satisfies
      | PolicyDesignCaseProjection["authoritative_for"]
      | undefined;

    renderWithProviders(
      <CandidateFrame
        authorityPurpose={authorityPurpose}
        block={block}
        title="Model proposal"
      />,
    );

    expect(screen.getByTestId("candidate-frame")).toHaveAttribute(
      "data-authority-posture",
      "candidate",
    );
    expect(screen.getByTestId("candidate-frame")).toHaveAttribute(
      "data-authority-purpose",
      "absent",
    );
    expect(
      within(screen.getByTestId("candidate-frame")).getByText(block.content),
    ).toBeVisible();
    expect(screen.queryByText("Human reviewed")).not.toBeInTheDocument();
    expect(screen.queryByText("Authoritative")).not.toBeInTheDocument();
    expect(screen.queryByText("Candidate material")).not.toBeInTheDocument();
    expect(screen.getByTestId("decision-card-candidate")).not.toHaveAttribute(
      "data-owner-decision-grade",
    );
  });
});
