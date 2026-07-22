import { screen } from "@testing-library/react";

import { renderWithProviders } from "@/test/render";

import { GovernancePassGrid } from "./GovernancePassGrid";

describe("GovernancePassGrid", () => {
  it("preserves mixed blocked contested partial and review-required outcomes without flattening", () => {
    const passes = [
      {
        id: "blocked",
        label: "Preflight",
        status: "blocked",
        vocabulary: "preflight_diagnostic" as const,
      },
      {
        id: "contested",
        label: "Evaluator",
        status: "contested",
        vocabulary: "evaluator_verdict" as const,
      },
      {
        id: "partial",
        label: "Reproducibility",
        status: "partial",
        vocabulary: "reproducibility_readiness" as const,
      },
      {
        id: "review-required",
        label: "Owner review",
        status: "review_required",
        vocabulary: "owner_diagnostic" as const,
      },
    ];

    renderWithProviders(<GovernancePassGrid passes={passes} />);

    for (const pass of passes) {
      expect(
        screen.getByRole("button", {
          name: `${pass.label}: ${pass.status}`,
        }),
      ).toHaveAttribute("data-owner-status", pass.status);
    }
    expect(
      screen.getByTestId("governance-pass-grid-owner-states"),
    ).toHaveTextContent("blocked · contested · partial · review_required");
    expect(screen.getByText("4 diagnostics")).toBeInTheDocument();
  });

  it("keeps heterogeneous owner vocabularies out of decision-grade presentation", () => {
    const passes = [
      {
        id: "preflight",
        label: "Preflight",
        status: "future_preflight_severity",
        vocabulary: "preflight_diagnostic" as const,
      },
      {
        id: "evaluator",
        label: "Evaluator",
        status: "future_evaluator_verdict",
        vocabulary: "evaluator_verdict" as const,
      },
      {
        id: "reproducibility",
        label: "Reproducibility",
        status: "future_reproducibility_readiness",
        vocabulary: "reproducibility_readiness" as const,
      },
    ];

    renderWithProviders(<GovernancePassGrid passes={passes} />);

    for (const pass of passes) {
      const item = screen.getByRole("button", {
        name: `${pass.label}: ${pass.status}`,
      });
      expect(item).toHaveAttribute("data-owner-status", pass.status);
      expect(item).toHaveAttribute("data-owner-vocabulary", pass.vocabulary);
      expect(item).not.toHaveAttribute("data-decision-grade-presentation");
    }
    expect(screen.getByText("3 diagnostics")).toBeInTheDocument();
    expect(
      screen.getByTestId("governance-pass-grid-owner-states"),
    ).toHaveTextContent(
      "future_preflight_severity · future_evaluator_verdict · future_reproducibility_readiness",
    );
    expect(
      screen.getByTestId("governance-pass-grid-owner-states"),
    ).toHaveAttribute("data-governance-source", "diagnostic-summary");
  });
});
