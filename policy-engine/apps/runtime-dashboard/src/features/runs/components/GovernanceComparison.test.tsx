import { screen } from "@testing-library/react";

import { renderWithProviders } from "@/test/render";

import { GovernanceComparison } from "./GovernanceComparison";

describe("GovernanceComparison", () => {
  it("presents both owner grades neutrally without reviving local statuses", () => {
    renderWithProviders(
      <GovernanceComparison
        items={[
          {
            baseDecisionGrade: "novel_owner_grade",
            label: "Eligibility review",
            passId: "eligibility",
            targetDecisionGrade: "review_required",
          },
        ]}
      />,
    );

    for (const grade of ["novel_owner_grade", "review_required"]) {
      const badge = screen.getByText(grade);
      expect(badge).toHaveAttribute(
        "data-decision-grade-presentation",
        "unrecognized",
      );
      expect(badge).toHaveAttribute("data-owner-grade", grade);
      expect(badge).toHaveAttribute("data-kind", "neutral");
    }
  });

  it("exposes the three-column comparison with table semantics", () => {
    renderWithProviders(
      <GovernanceComparison
        items={[
          {
            baseDecisionGrade: "one",
            label: "Eligibility review",
            passId: "eligibility",
            targetDecisionGrade: "two",
          },
        ]}
      />,
    );

    expect(screen.getByRole("table")).toBeVisible();
    expect(screen.getAllByRole("columnheader")).toHaveLength(3);
    expect(screen.getAllByRole("row")).toHaveLength(2);
    expect(screen.getAllByRole("cell")).toHaveLength(3);
  });
});
